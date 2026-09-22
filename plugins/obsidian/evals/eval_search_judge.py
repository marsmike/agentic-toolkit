"""Eval: search_judge.rerank() — typed judgments reorder search results, and the graph
widens what search alone can find.

Offline (stubbed `judge._post`, no network, no key):
1. order     — the candidate the stub scores highest comes first, whatever search said
2. widening  — with a gaiafield binary present, notes linked from the top hits join the
               candidates and are marked `via`; without one, the list is the search list
3. no key    — plain search order, no request
4. read-only — nothing in the vault changes

Opt-in live phase (TOOLKIT_EVAL_LIVE_JEV=1 with a key): twelve questions phrased in a
reader's words, one known answer note each. Plain search finds the answer first for 5 of
them and never finds 3 (2026-09-22). The widened rerank must put it in the top three for
at least 10 of 12 and find all 12.
"""
from __future__ import annotations

import os
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "search_judge"
KEY_ENVS = ("TOOLKIT_OBSIDIAN_JUDGMENT_API_KEY", "OPENROUTER_API_KEY")
C, G, T, P = "04_Resources/Concepts/", "04_Resources/Guides/", "04_Resources/Tools/", "02_Projects/"
QUERIES = [
    ("why did the first similarity gates flag almost every pair", C + "Calibration-Bias.md"),
    ("what stops an automated guess from silently changing my notes", C + "Inference-Write-Policy.md"),
    ("where do failures go when a script cannot decide", C + "Dead-Letter-Queues-for-Automation.md"),
    ("how do I check whether my summaries actually let me find the note again", C + "Retrieval-Verification-Loop.md"),
    ("does a long summary line make a note harder to find", C + "BM25-Dilution.md"),
    ("what is the rule about restoring before switching services over", P + "home-lab-migration/Backup-Strategy.md"),
    ("which publishers have I already contacted about the bird book", P + "field-guide/Publisher-Outreach-Log.md"),
    ("how is a subagent allowed to fan out and which model tier does bulk work", C + "Model-Tiering-for-Agent-Fleets.md"),
    ("what is a cross-domain connection between two distant note clusters called and how is it scored", C + "Surprise-Scoring.md"),
    ("how do I move an old plain markdown folder into this structure", G + "Migrating-Notes-From-Plain-Markdown.md"),
    ("how does a plugin learn who I am without hardcoding it", C + "Fill-From-Obsidian-Profiles.md"),
    ("which tool builds the link graph and which one does text search", T + "Gaiafield.md"),
]


def _snapshot(vault: Path) -> dict[str, tuple[int, int]]:
    return {p.relative_to(vault).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in vault.rglob("*") if p.is_file() and ".gaiafield" not in p.parts}


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import graph
    import judge
    import search_judge as sj
    from search import search

    problems: list[str] = []
    saved_env = {k: os.environ.pop(k, None) for k in (*KEY_ENVS, "TOOLKIT_OBSIDIAN_JUDGMENT_BACKEND")}
    real_post = judge._post
    sandbox = make_sandbox(vault)
    calls = []
    query = "hybrid retrieval scoring"

    def stub(url, payload, headers):
        calls.append(payload)
        notes = payload["state"]["notes"]
        last = max(notes)  # the stub prefers whichever candidate came last
        return {"model": "stub-1", "usage": {"input_tokens": 100},
                "answers": {qid: {"type": "noul", "noul": 0.95 if qid.endswith(last) else 0.1} for qid in payload["questions"]}}

    try:
        plain = search(query, sandbox, top=5)["results"]
        if judge.unavailable_reason(sandbox) != "no-key":
            problems.append("phase 3: expected no-key before a key is set")
        os.environ[KEY_ENVS[0]] = "stub-key-not-a-secret"
        judge._post = stub
        before = _snapshot(sandbox)
        result = sj.rerank(query, sandbox, 5, [], widen=False)
        if not result["reranked"] or result["results"][0]["path"] != plain[-1]["path"]:
            problems.append("phase 1: the highest-judged candidate did not come first")
        if result["results"][0]["search_rank"] != len(plain):
            problems.append("phase 1: search_rank was not preserved on the reordered row")
        widened = sj.rerank(query, sandbox, 5, [], widen=True)
        has_graph = graph.available() and not isinstance(graph.ensure_index(sandbox), graph.GraphUnavailable)
        via = [r for r in widened["results"] if r.get("via")]
        if has_graph and not via:
            problems.append("phase 2: gaiafield present but no linked neighbour joined the candidates")
        if not has_graph and (via or widened["candidates"] != len(plain)):
            problems.append("phase 2: without a graph the candidates must be exactly the search results")
        if any(r["path"] in {p["path"] for p in plain} for r in via):
            problems.append("phase 2: a search hit was re-added as a neighbour")
        if _snapshot(sandbox) != before:
            problems.append("phase 4: reranking changed files in the vault")

        live_detail = "live phase skipped (set TOOLKIT_EVAL_LIVE_JEV=1 with a key to run it)"
        if os.environ.get("TOOLKIT_EVAL_LIVE_JEV") == "1":
            judge._post = real_post
            key = next((saved_env[k] for k in KEY_ENVS if saved_env.get(k)), None)
            if key:
                os.environ[KEY_ENVS[0]] = key
                top3 = found = 0
                usd = 0.0
                for q, target in QUERIES:
                    r = sj.rerank(q, sandbox, 10, [], widen=True)
                    usd += r["judgment"]["usd"]
                    ranks = [i for i, row in enumerate(r["results"], start=1) if row["path"] == target]
                    found += bool(ranks)
                    top3 += bool(ranks) and ranks[0] <= 3
                if top3 < 10 or found < 12:
                    problems.append(f"live: widened rerank top-3 {top3}/12, found {found}/12")
                live_detail = f"live: top-3 {top3}/12, found {found}/12, ${usd:.4f}"
            else:
                live_detail = "live phase requested but no key in the environment"
    finally:
        judge._post = real_post
        for k, v in saved_env.items():
            os.environ.pop(k, None)
            if v is not None:
                os.environ[k] = v
        teardown_sandbox(sandbox)

    if problems:
        return {"eval": NAME, "pass": False, "detail": "; ".join(problems)}
    return {"eval": NAME, "pass": True, "detail": f"4 offline phases ok ({len(calls)} stubbed requests); {live_detail}"}
