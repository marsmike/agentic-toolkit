#!/usr/bin/env python3
"""Search, then judge: rerank the top results by whether each note answers the question.

    uv run scripts/search_judge.py "how does the toolkit decide which folder a note goes in" --top 10

Keyword search is fast and finds the right note somewhere in its top ten far more often than
it puts it first (the TypeSafe rerank cookbook measured 5% top-1 against 100% top-30 on a
legal corpus). One request asks a typed-judgment backend, per candidate, whether opening the
note would give the asker what they wanted, and reorders by that probability.

A note search did not find cannot be reranked into view, so with a gaiafield graph present
the candidates are widened first, deterministically and for free: every note the top hits
link to joins the list (`--no-expand` to switch that off). On the example vault this is what
finds the answers keyword search misses outright: a question phrased in the reader's words
often lands on the neighbour of the right note rather than on it.

Report-only; writes nothing. No key prints the plain search results.
"""
from __future__ import annotations

import argparse
import json

import graph
import judge
from judgments import questions as Q
from judgments.state import in_chunks, note_payload
from search import search
from vault_utils import require_vault

RERANK_CHARS = 1500
EXPAND_FROM = 3  # top search hits whose wikilink neighbours join the candidate list
MAX_CANDIDATES = 40
NOTES_PER_REQUEST = 12  # a real vault's 40 candidates at 1,500 chars each exceeded the backend's input limit
# Below this probability a candidate is shown but marked as not an answer. Policy, per backend.
THRESHOLDS = {"jev": {"T_ANSWERS": 0.50}}


def _excluded(rel: str, exclude: list[str]) -> bool:
    return any(rel == e or rel.startswith(e.rstrip("/") + "/") for e in exclude)


def expand(rows: list[dict], vault) -> list[dict]:
    """Add the depth-1 wikilink neighbours of the top hits (extracted edges only). Silent
    when there is no graph; the candidate list is then just the search results."""
    if not graph.available() or isinstance(graph.ensure_index(vault), graph.GraphUnavailable):
        return rows
    seen = {r["path"] for r in rows}
    added = []
    for hit in rows[:EXPAND_FROM]:
        links = graph.neighbors(vault, hit["path"], depth=1)
        if isinstance(links, graph.GraphUnavailable):
            break
        for n in links:
            if n["path"] not in seen and (vault / n["path"]).is_file():
                seen.add(n["path"])
                added.append({"path": n["path"], "title": n["title"], "folder": n["path"].split("/")[0],
                              "score": None, "above_enrichment_gate": None, "via": hit["path"]})
    return rows + added


def rerank(query: str, vault, top: int, exclude: list[str], widen: bool = True) -> dict:
    found = search(query, vault, top=top)
    rows = [dict(r) for r in found["results"] if not _excluded(r["path"], exclude)]
    if widen:
        rows = [r for r in expand(rows, vault) if not _excluded(r["path"], exclude)][:MAX_CANDIDATES]
    if not rows:
        return {**found, "results": rows, "reranked": False}
    usages = []

    def ask(chunk, start):
        state, questions = {"query": query, "notes": {}}, {}
        for i, r in enumerate(chunk, start=start + 1):
            nid = f"N{i:02d}"
            state["notes"][nid] = note_payload(vault / r["path"], vault, RERANK_CHARS)
            questions[f"ans_{nid}"] = Q.answers_query(nid)
        got, used = judge.judge(vault, state, questions)
        usages.append(used)
        return got

    answers = in_chunks(rows, NOTES_PER_REQUEST, ask)
    usage = usages[0]
    for used in usages[1:]:
        usage.requests += used.requests
        usage.input_tokens += used.input_tokens
        usage.usd += used.usd
    t = THRESHOLDS[usage.backend]
    for i, r in enumerate(rows, start=1):
        a = answers.get(f"ans_N{i:02d}")
        r["search_rank"] = i if r.get("score") is not None else None
        r["p_answers"] = round(a.p, 3) if a else None
        r["judged_answer"] = bool(a and a.p >= t["T_ANSWERS"])
    rows.sort(key=lambda r: -(r["p_answers"] if r["p_answers"] is not None else -1))
    return {**found, "results": rows, "reranked": True, "widened": widen, "candidates": len(rows),
            "questions_version": Q.QUESTIONS_VERSION, "judgment": usage.as_dict()}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("query")
    ap.add_argument("--top", type=int, default=10, help="search results to judge")
    ap.add_argument("--exclude", action="append", default=[], help="vault-relative prefix never sent to the backend (repeatable)")
    ap.add_argument("--no-expand", action="store_true", help="judge only the search results, not their linked neighbours")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    vault = require_vault()
    if judge.unavailable_reason(vault):
        result = {**search(args.query, vault, top=args.top), "reranked": False,
                  "note": f"judgment backend unavailable ({judge.unavailable_reason(vault)}); plain search order"}
    else:
        try:
            result = rerank(args.query, vault, args.top, args.exclude, widen=not args.no_expand)
        except judge.JudgmentFailed as e:
            print(f"judgment backend failed: {e}")
            return 1
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    if not result["reranked"]:
        print(result.get("note", ""))
    for r in result["results"]:
        mark = "*" if r.get("judged_answer") else " "
        p = f"{r['p_answers']:.2f}" if r.get("p_answers") is not None else "  --"
        origin = f"was #{r['search_rank']:<3}" if r.get("search_rank") else f"via {r.get('via', '?').rsplit('/', 1)[-1][:18]:<18}"[:8].ljust(8)
        print(f" {mark} {p}  {origin} {r['path']}")
    if result["reranked"]:
        print(f"\n${result['judgment']['usd']} · {result['judgment']['model']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
