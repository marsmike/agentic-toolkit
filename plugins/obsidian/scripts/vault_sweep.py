#!/usr/bin/env python3
"""Vault sweep — duplicates and contradictions across existing notes, report-only.

    uv run scripts/vault_sweep.py --json
    uv run scripts/vault_sweep.py --max-pairs 500 --exclude 03_Areas/Personal

A vault that grew for years holds notes that are the same work under two titles, and
claims that later notes quietly reversed. Neither shows up when a single capture is
distilled; both need a pass over pairs. Candidate pairs come from two free generators:

- notes whose `source:` resolves to the same address (a shared address is a candidate, not a
  verdict: one vault kept a whole methodology folder under its repository's URL);
- gaiafield's inferred edges, INFERRED and AMBIGUOUS, the vault's own "these two are about
  the same thing" list.

Each candidate pair is then asked two narrow questions in one request: are they write-ups of
the same original work, and do they make claims that cannot both be true. Nothing is written;
the report is a reading list with the flagged pairs first. Duplicates are for a human to
merge; a contradiction is where an L3 callout was never written.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict

import graph
import judge
from judgments import questions as Q
from judgments.state import in_chunks, note_payload
from vault_utils import discover_notes, read_frontmatter, require_vault

PAIRS_PER_REQUEST = 12
MAX_SOURCE_GROUP = 6  # more notes than this on one address is a collection (a repo, a site root), not duplicates
NOTE_CHARS = 1200
# Policy, per backend. Duplicates are cheap to review, so a moderate cut; contradictions
# are worth a human's attention only when the backend is fairly sure.
THRESHOLDS = {"jev": {"T_SAME_WORK": 0.70, "T_CONTRADICTS": 0.60}}


def canonical_url(url: str) -> str:
    u = url.strip().lower()
    u = re.sub(r"^(https?://)?(www\.)?", "", u)
    u = re.sub(r"[?#].*$", "", u)
    return u.rstrip("/")


def same_source_pairs(vault, rels: list[str]) -> list[tuple[str, str]]:
    by_url: dict[str, list[str]] = defaultdict(list)
    for rel in rels:
        fm, _ = read_frontmatter(vault / rel)
        src = str(fm.get("source") or "")
        if src.startswith("http"):
            by_url[canonical_url(src)].append(rel)
    return [(a, b) for group in by_url.values() if 1 < len(group) <= MAX_SOURCE_GROUP
            for i, a in enumerate(group) for b in group[i + 1:]]


def sweep(vault, max_pairs: int, exclude: list[str], include_graph: bool = True) -> dict:
    rels = [p.relative_to(vault).as_posix() for p in discover_notes(vault, exclude=exclude)]
    active = set(rels)
    by_source = same_source_pairs(vault, rels)
    pairs: list[tuple[str, str, str]] = [(a, b, "same-source") for a, b in by_source]
    seen = {tuple(sorted((a, b))) for a, b, _ in pairs}
    graph_rows = 0
    if include_graph and graph.available():
        rows = graph.surprise_candidates(vault, top=max_pairs, include_ambiguous=True)
        if not isinstance(rows, graph.GraphUnavailable):
            for r in rows:
                key = tuple(sorted((r["a"], r["b"])))
                if r["a"] in active and r["b"] in active and key not in seen:
                    seen.add(key)
                    pairs.append((r["a"], r["b"], r["label"].lower()))
                    graph_rows += 1
    pairs = pairs[:max_pairs]
    cache: dict[str, dict] = {}

    def payload(rel):
        if rel not in cache:
            cache[rel] = note_payload(vault / rel, vault, NOTE_CHARS)
        return cache[rel]

    usages = []

    def ask(chunk, start):
        state, questions = {"pairs": {}}, {}
        for i, (a, b, _) in enumerate(chunk, start=1):
            pid = f"P{i:02d}"
            state["pairs"][pid] = {"a": payload(a), "b": payload(b)}
            questions[f"same_{pid}"] = Q.same_work(pid)
            questions[f"contra_{pid}"] = Q.contradicts(pid)
        answers, used = judge.judge(vault, state, questions)
        usages.append(used)
        return {start + i - 1: (answers.get(f"same_P{i:02d}"), answers.get(f"contra_P{i:02d}")) for i in range(1, len(chunk) + 1)}

    results = in_chunks(pairs, PAIRS_PER_REQUEST, ask) if pairs else {}
    usage = usages[0] if usages else None
    for extra in usages[1:]:
        usage.requests += extra.requests
        usage.input_tokens += extra.input_tokens
        usage.usd += extra.usd
    t = THRESHOLDS[usage.backend] if usage else THRESHOLDS["jev"]
    duplicates, contradictions, rows_out = [], [], []
    for i, (a, b, origin) in enumerate(pairs):
        same, contra = results.get(i, (None, None))
        row = {"a": a, "b": b, "origin": origin, "p_same_work": round(same.p, 3) if same else None,
               "p_contradicts": round(contra.p, 3) if contra else None}
        rows_out.append(row)
        if same and same.p >= t["T_SAME_WORK"]:
            duplicates.append(row)
        if contra and contra.p >= t["T_CONTRADICTS"]:
            contradictions.append(row)
    return {
        "advisory": True, "questions_version": Q.QUESTIONS_VERSION, "notes": len(rels), "pairs_judged": len(pairs),
        "pairs_from_same_source": len(by_source), "pairs_from_graph": graph_rows,
        "duplicates": sorted(duplicates, key=lambda r: -(r["p_same_work"] or 1.0)),
        "contradictions": sorted(contradictions, key=lambda r: -r["p_contradicts"]),
        "judgment": usage.as_dict() if usage else {},
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--max-pairs", type=int, default=2000)
    ap.add_argument("--exclude", action="append", default=[], help="vault-relative prefix never sent to the backend (repeatable)")
    ap.add_argument("--no-graph", action="store_true", help="only pairs with the same source address")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    vault = require_vault()
    reason = judge.unavailable_reason(vault)
    if reason:
        print(json.dumps({"skipped": reason}) if args.json else f"SKIPPED — judgment backend unavailable ({reason})")
        return 0
    try:
        report = sweep(vault, args.max_pairs, args.exclude, include_graph=not args.no_graph)
    except judge.JudgmentFailed as e:
        print(f"judgment backend failed: {e}")
        return 1
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"{report['notes']} notes, {report['pairs_judged']} pairs judged ({report['pairs_from_same_source']} same source, "
          f"{report['pairs_from_graph']} from the graph); ${report['judgment'].get('usd', 0)}")
    print(f"\nlikely the same work ({len(report['duplicates'])}):")
    for r in report["duplicates"]:
        print(f"  {r['p_same_work'] if r['p_same_work'] is not None else 'src':<5} {r['a']}\n        {r['b']}")
    print(f"\nlikely contradictions ({len(report['contradictions'])}):")
    for r in report["contradictions"]:
        print(f"  {r['p_contradicts']:<5} {r['a']}\n        {r['b']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
