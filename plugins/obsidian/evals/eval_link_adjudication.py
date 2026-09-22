"""Eval: graph.adjudicate_candidates() — typed judgments on gaiafield's suggested links.

Offline, against a stubbed `judge._post` (no network, no credential, no gaiafield binary:
the rows are synthetic, in both shapes graph.py produces):
1. attach      — every row gains `adjudication` with p, label, backend, model, questions_version
2. untouched   — gaiafield's own score, label and row order are exactly what went in
3. both shapes — pair-shaped `surprise` rows and note-relative `candidates` rows
4. no key      — GraphUnavailable("no-judgment"), no request, no DLQ note
5. failure     — a configured backend that answers nothing: "call-failed" and one DLQ note
6. read-only   — no file in the vault changes

Opt-in live phase (TOOLKIT_EVAL_LIVE_JEV=1 with a key): ground truth that needs no
annotator. Positives are pairs the vault's author linked by hand; negatives are unlinked
pairs across the two planted project clusters (birding vs home lab, per Test-Corpus-Map).
The backend must rank the first above the second (AUC >= 0.90) and may call at most
one of fifteen cross-cluster pairs a likely link (the 10% bar).
"""
from __future__ import annotations

import os
import random
import re
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "link_adjudication"
KEY_ENVS = ("TOOLKIT_OBSIDIAN_JUDGMENT_API_KEY", "OPENROUTER_API_KEY")
A, B, C = (
    "04_Resources/Concepts/Hybrid-Retrieval.md",
    "04_Resources/Tools/Farsight.md",
    "04_Resources/Concepts/BM25-Dilution.md",
)


def _snapshot(vault: Path) -> dict[str, tuple[int, int]]:
    return {p.relative_to(vault).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns) for p in vault.rglob("*") if p.is_file()}


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import graph
    import judge

    problems: list[str] = []
    saved_env = {k: os.environ.pop(k, None) for k in (*KEY_ENVS, "TOOLKIT_OBSIDIAN_JUDGMENT_BACKEND")}
    real_post = judge._post
    sandbox = make_sandbox(vault)
    calls = []

    def stub_ok(url, payload, headers):
        calls.append(payload)
        return {"model": "stub-1", "usage": {"input_tokens": 500},
                "answers": {qid: {"type": "noul", "noul": 0.9 if qid.startswith("link_") else 0.2} for qid in payload["questions"]}}

    def stub_fails(url, payload, headers):
        raise judge._CallError("HTTP 500: stub", retryable_by_split=True)

    surprise_rows = [
        {"a": A, "b": B, "score": 0.74, "surprise": 0.5, "det_distance": 3, "same_subtree": True, "label": "INFERRED", "model": "m"},
        {"a": A, "b": C, "score": 0.69, "surprise": 0.4, "det_distance": 2, "same_subtree": True, "label": "AMBIGUOUS", "model": "m"},
    ]
    candidate_rows = [{"path": B, "score": 0.74, "label": "INFERRED"}, {"path": C, "score": 0.69, "label": "AMBIGUOUS"}]
    dlq_dir = sandbox / "00_Memory" / "dlq"

    try:
        judge._post = stub_ok
        unavailable = graph.adjudicate_candidates(sandbox, surprise_rows)
        if not isinstance(unavailable, graph.GraphUnavailable) or unavailable.reason != "no-judgment" or calls:
            problems.append(f"phase 4: expected silent 'no-judgment' with no request, got {unavailable!r} ({len(calls)} requests)")
        if dlq_dir.is_dir() and any("adjudication" in p.name for p in dlq_dir.glob("*.md")):
            problems.append("phase 4: a missing key wrote a DLQ note")

        os.environ[KEY_ENVS[0]] = "stub-key-not-a-secret"
        before = _snapshot(sandbox)
        for shape, rows, note in (("surprise", surprise_rows, None), ("candidates", candidate_rows, A)):
            judged = graph.adjudicate_candidates(sandbox, rows, note=note)
            if isinstance(judged, graph.GraphUnavailable):
                problems.append(f"phase 3: {shape} rows came back unavailable: {judged.reason}")
                continue
            for original, row in zip(rows, judged, strict=True):
                verdict = row.get("adjudication") or {}
                if not {"p", "label", "p_same_mechanism", "backend", "model", "questions_version"} <= set(verdict):
                    problems.append(f"phase 1: {shape} row lacks adjudication fields: {sorted(verdict)}")
                if verdict.get("label") != "LIKELY-LINK":
                    problems.append(f"phase 1: p=0.9 should read LIKELY-LINK, got {verdict.get('label')}")
                if {k: v for k, v in row.items() if k != "adjudication"} != original:
                    problems.append(f"phase 2: {shape} row was altered beyond the added adjudication")
        if _snapshot(sandbox) != before:
            problems.append("phase 6: adjudication changed files in the vault")
        sent = calls[-1] if calls else {}
        for qid, q in sent.get("questions", {}).items():
            for dotted in re.findall(r"`([A-Za-z_][\w.]*)`", q["instructions"]):
                node = sent["state"]
                for part in dotted.split("."):
                    node = node.get(part) if isinstance(node, dict) else None
                if node is None:
                    problems.append(f"phase 1: {qid} references `{dotted}`, absent from the state")

        judge._post = stub_fails
        dlq_before = set(dlq_dir.glob("*.md")) if dlq_dir.is_dir() else set()
        failed = graph.adjudicate_candidates(sandbox, surprise_rows)
        new_dlq = (set(dlq_dir.glob("*.md")) if dlq_dir.is_dir() else set()) - dlq_before
        if not isinstance(failed, graph.GraphUnavailable) or failed.reason != "call-failed" or len(new_dlq) != 1:
            problems.append(f"phase 5: expected 'call-failed' and one DLQ note, got {failed!r} and {len(new_dlq)} notes")

        live_detail = "live phase skipped (set TOOLKIT_EVAL_LIVE_JEV=1 with a key to run it)"
        if os.environ.get("TOOLKIT_EVAL_LIVE_JEV") == "1":
            judge._post = real_post
            live_detail = _live_phase(graph, sandbox, saved_env, problems)
    finally:
        judge._post = real_post
        for k, v in saved_env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        teardown_sandbox(sandbox)

    if problems:
        return {"eval": NAME, "pass": False, "detail": "; ".join(problems)}
    return {"eval": NAME, "pass": True, "detail": f"6 offline phases ok; {live_detail}"}


def _cluster(rel: str) -> str | None:
    if rel.startswith("02_Projects/field-guide/") or rel == "03_Areas/Birding.md":
        return "birding"
    if rel.startswith("02_Projects/home-lab-migration/") or rel == "03_Areas/Home-Network-Administration.md":
        return "homelab"
    return None


def _live_phase(graph, sandbox: Path, saved_env: dict, problems: list[str]) -> str:
    from vault_utils import discover_notes

    key = next((saved_env[k] for k in KEY_ENVS if saved_env.get(k)), None)
    if not key:
        return "live phase requested but no key in the environment"
    os.environ[KEY_ENVS[0]] = key
    notes = [p.relative_to(sandbox).as_posix() for p in discover_notes(sandbox)]
    by_stem: dict[str, list[str]] = {}
    for rel in notes:
        by_stem.setdefault(Path(rel).stem, []).append(rel)
    linked = set()
    for rel in notes:
        for target in re.findall(r"\[\[([^\]|#]+)", (sandbox / rel).read_text(encoding="utf-8", errors="replace")):
            for other in by_stem.get(target.strip().split("/")[-1], []):
                if other != rel:
                    linked.add(tuple(sorted((rel, other))))
    rng = random.Random(20260922)
    positives = rng.sample(sorted(linked), 20)
    cross = [(a, b) for a in notes for b in notes
             if _cluster(a) == "birding" and _cluster(b) == "homelab" and tuple(sorted((a, b))) not in linked
             and Path(a).stem != Path(b).stem]
    negatives = rng.sample(cross, 15)
    verdicts, usage = graph.adjudicate_pairs(sandbox, positives + negatives)
    pos = [v["p"] for v in verdicts[:20] if v]
    neg = [v["p"] for v in verdicts[20:] if v]
    auc = sum((a > b) + 0.5 * (a == b) for a in pos for b in neg) / (len(pos) * len(neg))
    false_links = sum(1 for v in verdicts[20:] if v and v["label"] == "LIKELY-LINK")
    if auc < 0.90:
        problems.append(f"live: author-linked vs cross-cluster AUC {auc:.3f} is below 0.90")
    # The plan's bar is a cross-cluster false-positive rate of 10% or less; on 15 pairs that is
    # one. Pairs like two inventories in different projects sit on the boundary and cross it
    # between runs (order_gap and rerun drift, see Typed-Judgments), so zero would be a coin flip.
    if false_links > 1:
        problems.append(f"live: {false_links} unlinked cross-cluster pair(s) judged LIKELY-LINK (at most 1 of 15 allowed)")
    return (f"live: AUC {auc:.3f} (linked mean {sum(pos) / len(pos):.2f}, cross-cluster mean {sum(neg) / len(neg):.2f}), "
            f"model {usage['model']}, ${usage['usd']}")
