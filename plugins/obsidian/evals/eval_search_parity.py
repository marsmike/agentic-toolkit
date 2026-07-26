"""Eval: farsight (Rust BM25) parity against search.py's Python BM25 implementation.

This eval does NOT build the crate — that's cargo's job, not CI's Python lane. It only
checks that IF a farsight binary is available (`TOOLKIT_FARSIGHT_BIN` env var, else on
PATH), the top-3 results for a handful of fixed queries drawn from different clusters in
the example vault (see Test-Corpus-Map.md) overlap >=2/3 with the Python implementation's
own top-3 for the same query. Absence of a binary is not a failure in CI until release
binaries exist (docs/PLAN.md) — it reports pass with a detail saying so.

Both sides are compared on BM25 alone (no semantic blend): farsight is BM25-only in R1,
so the fair comparison is search.py's bm25_scores() ranking directly, not its (usually
semantic-unavailable-anyway) blended search() output.
"""
from __future__ import annotations

from pathlib import Path

FIXED_QUERIES = (
    "retrieval verification loop",
    "home lab migration backup strategy",
    "birding field guide project",
)
MIN_OVERLAP = 2
TOP_N = 3


def _python_top(search_mod, vault: Path, query: str, n: int) -> list[str]:
    corpus = search_mod.build_corpus(vault)
    scores = search_mod.bm25_scores(query, corpus)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [rel for rel, _ in ranked]


def _farsight_top(search_mod, vault: Path, query: str, n: int, binary: str) -> list[str] | None:
    result = search_mod.farsight_search(query, vault, n, binary)
    if result is None:
        return None
    return [r["path"] for r in result["results"]]


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import search as search_mod

    binary = search_mod.farsight_binary()
    if not binary:
        return {
            "eval": "search_parity", "pass": True,
            "detail": "farsight not present — python fallback only",
        }

    per_query = []
    problems = []
    for query in FIXED_QUERIES:
        python_top = _python_top(search_mod, vault, query, TOP_N)
        farsight_top = _farsight_top(search_mod, vault, query, TOP_N, binary)
        if farsight_top is None:
            problems.append(f"{query!r}: farsight binary present but query failed")
            continue
        overlap = len(set(python_top) & set(farsight_top))
        per_query.append({"query": query, "overlap": overlap, "python_top": python_top, "farsight_top": farsight_top})
        if overlap < MIN_OVERLAP:
            problems.append(f"{query!r}: overlap {overlap}/{TOP_N} < {MIN_OVERLAP} (python={python_top}, farsight={farsight_top})")

    if problems:
        return {"eval": "search_parity", "pass": False, "detail": "; ".join(problems)}
    detail = "; ".join(f"{r['query']!r} overlap={r['overlap']}/{TOP_N}" for r in per_query)
    return {"eval": "search_parity", "pass": True, "detail": f"farsight ({binary}): {detail}"}
