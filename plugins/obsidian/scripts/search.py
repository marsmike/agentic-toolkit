#!/usr/bin/env python3
"""Vault search — keyword ranking over active notes, with an optional semantic boost.

    uv run scripts/search.py "hybrid retrieval scoring" --top 5 --json
    uv run scripts/search.py --rebuild-cache          # (re)build the optional embeddings cache

Always available: a BM25 ranking over each note's title, filename, Index.md summary (if
any), and body — this is the "filename + Index.md scan" fallback contract/PLAN.md asks
for, not a degraded afterthought; it needs no dependency beyond PyYAML and works on a
freshly cloned repo with zero setup.

Optional: if `sentence-transformers` and `numpy` are installed (`uv run --with
'.[semantic]' scripts/search.py ...` or `pip install -e '.[semantic]'`), a semantic
cosine layer is blended in, backed by a small cache this script builds and owns at
`00_Memory/.search-cache/embeddings.json` (never Smart Connections' `.smart-env/`
format — this script does not require or produce that store). Without those packages,
search.py says so once and returns BM25-only results; it never hangs or errors.

**farsight (docs/PLAN.md) replaces this whole file in R1** — a Rust hybrid BM25+vector
engine. This script is the R0 placeholder: correct and dependency-light, not the final
retrieval architecture.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from vault_utils import (
    ACTIVE_CONTENT_FOLDERS,
    discover_notes,
    parse_existing_index,
    profile_value,
    require_vault,
)

TOKEN_RE = re.compile(r"[a-z0-9]+")
BODY_HEAD = 2000  # chars of body considered per note — enough for topic signal, cheap to scan
STOPWORDS = {
    "the", "a", "an", "of", "to", "in", "and", "or", "is", "are", "for", "on", "with",
    "this", "that", "it", "as", "by", "at", "be", "was", "were", "from", "into",
}


def tokenize(text: str) -> list[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if len(t) > 1 and t not in STOPWORDS]


# ---------------------------------------------------------------------------
# Corpus
# ---------------------------------------------------------------------------


class Doc:
    __slots__ = ("folder", "length", "path", "rel", "term_counts", "text", "title", "tokens")

    def __init__(self, path: Path, vault: Path, index_entries: dict[str, tuple[str, str]]):
        self.path = path
        self.rel = path.relative_to(vault).as_posix()
        self.title = path.stem
        self.folder = path.relative_to(vault).parts[0]
        rel_key = path.relative_to(vault).with_suffix("").as_posix()
        summary = index_entries.get(rel_key, ("", ""))[0]
        try:
            body = path.read_text(encoding="utf-8", errors="replace")[:BODY_HEAD]
        except OSError:
            body = ""
        # Title and Index.md summary count for extra weight by repetition, not a separate
        # scoring path — keeps the ranker to one formula.
        self.text = f"{self.title} {self.title} {summary} {summary} {body}"
        self.tokens = tokenize(self.text)
        self.term_counts = Counter(self.tokens)
        self.length = len(self.tokens)


def build_corpus(vault: Path, scope: str | None = None) -> list[Doc]:
    index_entries = parse_existing_index(vault / "Index.md")
    notes = discover_notes(vault, scope=scope)
    return [Doc(p, vault, index_entries) for p in notes]


# ---------------------------------------------------------------------------
# BM25
# ---------------------------------------------------------------------------


def bm25_scores(query: str, corpus: list[Doc], k1: float = 1.5, b: float = 0.75) -> dict[str, float]:
    q_tokens = tokenize(query)
    if not q_tokens or not corpus:
        return {}

    n = len(corpus)
    avg_len = sum(d.length for d in corpus) / n
    df = Counter()
    for term in set(q_tokens):
        df[term] = sum(1 for d in corpus if term in d.term_counts)

    scores: dict[str, float] = {}
    for d in corpus:
        score = 0.0
        for term in q_tokens:
            f = d.term_counts.get(term, 0)
            if f == 0:
                continue
            idf = math.log((n - df[term] + 0.5) / (df[term] + 0.5) + 1)
            denom = f + k1 * (1 - b + b * d.length / avg_len)
            score += idf * (f * (k1 + 1)) / denom
        if score > 0:
            scores[d.rel] = score
    return scores


# ---------------------------------------------------------------------------
# Optional semantic layer — self-built cache, no Smart Connections dependency
# ---------------------------------------------------------------------------


def _cache_path(vault: Path) -> Path:
    return vault / "00_Memory" / ".search-cache" / "embeddings.json"


def semantic_available() -> bool:
    try:
        import numpy  # noqa: F401
        import sentence_transformers  # noqa: F401
    except ImportError:
        return False
    return True


def semantic_scores(query: str, corpus: list[Doc], vault: Path, rebuild: bool = False) -> dict[str, float] | None:
    """Cosine similarity between the query and each doc's cached embedding.

    Returns None (not {}) if the optional dependencies aren't installed — callers must
    distinguish "unavailable" from "available but no matches".
    """
    if not semantic_available():
        return None

    import numpy as np
    from sentence_transformers import SentenceTransformer

    cache_file = _cache_path(vault)
    cache: dict[str, Any] = {}
    if cache_file.is_file() and not rebuild:
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            cache = {}

    model_name = "TaylorAI/bge-micro-v2"
    stale = [d for d in corpus if cache.get(d.rel, {}).get("mtime") != d.path.stat().st_mtime]
    if stale:
        model = SentenceTransformer(model_name)
        vectors = model.encode([d.text[:1000] for d in stale], show_progress_bar=False)
        for d, vec in zip(stale, vectors, strict=False):
            cache[d.rel] = {"mtime": d.path.stat().st_mtime, "vector": vec.tolist()}
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cache), encoding="utf-8")

    model = SentenceTransformer(model_name)
    q_vec = np.array(model.encode([query], show_progress_bar=False)[0])
    q_norm = q_vec / (np.linalg.norm(q_vec) or 1.0)

    scores: dict[str, float] = {}
    for d in corpus:
        entry = cache.get(d.rel)
        if not entry:
            continue
        v = np.array(entry["vector"])
        v_norm = v / (np.linalg.norm(v) or 1.0)
        scores[d.rel] = float(np.dot(q_norm, v_norm))
    return scores


# ---------------------------------------------------------------------------
# Combined search
# ---------------------------------------------------------------------------


def search(query: str, vault: Path, top: int = 10, scope: str | None = None, rebuild_cache: bool = False) -> dict:
    corpus = build_corpus(vault, scope=scope)
    bm25 = bm25_scores(query, corpus)
    sem = semantic_scores(query, corpus, vault, rebuild=rebuild_cache)

    semantic_used = sem is not None
    if not semantic_used:
        note = (
            "semantic search unavailable (sentence-transformers/numpy not installed) — "
            "falling back to keyword + Index.md scan. farsight (R1) replaces this layer."
        )
    else:
        note = "keyword + semantic (cached) blend"

    # Normalize each channel to [0, 1] before blending so neither dominates by raw scale.
    def _normalize(d: dict[str, float]) -> dict[str, float]:
        if not d:
            return {}
        lo, hi = min(d.values()), max(d.values())
        if hi == lo:
            return {k: 1.0 for k in d}
        return {k: (v - lo) / (hi - lo) for k, v in d.items()}

    bm25_n, sem_n = _normalize(bm25), _normalize(sem or {})
    all_paths = set(bm25_n) | set(sem_n)
    weight_sem = 0.4 if semantic_used else 0.0
    weight_kw = 1.0 - weight_sem

    combined = {
        rel: weight_kw * bm25_n.get(rel, 0.0) + weight_sem * sem_n.get(rel, 0.0)
        for rel in all_paths
    }
    ranked = sorted(combined.items(), key=lambda kv: kv[1], reverse=True)[:top]
    by_rel = {d.rel: d for d in corpus}

    gate = float(profile_value(vault, "search_score_gate", 0.70))
    results = [
        {
            "path": rel, "title": by_rel[rel].title, "folder": by_rel[rel].folder,
            "score": round(score, 4), "above_enrichment_gate": score >= gate,
            "channels": [c for c, present in (("keyword", rel in bm25_n), ("semantic", rel in sem_n)) if present],
        }
        for rel, score in ranked
    ]
    return {"query": query, "semantic_available": semantic_used, "note": note, "score_gate": gate, "results": results}


def propose_placement(text: str, vault: Path, scope: str | None = None) -> dict:
    """Suggest a PARA folder for new content by keyword similarity to existing notes.

    Used by the distill skill's dry-run/placement step and by eval_distill_placement.
    Falls back to 04_Resources (the generic reference-material default) when nothing in
    the vault is similar enough to have an opinion.
    """
    result = search(text, vault, top=5, scope=scope)
    hits = [r for r in result["results"] if r["folder"] in ACTIVE_CONTENT_FOLDERS]
    if not hits:
        return {"folder": "04_Resources", "reason": "no similar existing note found", "top_matches": []}
    return {"folder": hits[0]["folder"], "reason": f"closest match: {hits[0]['title']} ({hits[0]['score']})", "top_matches": hits}


def main() -> int:
    parser = argparse.ArgumentParser(description="Vault search")
    parser.add_argument("query", nargs="?", default="")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--scope", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--rebuild-cache", action="store_true")
    args = parser.parse_args()

    vault = require_vault()

    if args.rebuild_cache and not args.query:
        corpus = build_corpus(vault)
        semantic_scores("", corpus, vault, rebuild=True)
        print("Embeddings cache rebuilt." if semantic_available() else "sentence-transformers/numpy not installed — nothing to cache.")
        return 0

    if not args.query:
        parser.error("query is required unless --rebuild-cache is passed alone")

    start = time.time()
    result = search(args.query, vault, top=args.top, scope=args.scope, rebuild_cache=args.rebuild_cache)
    result["took_ms"] = round((time.time() - start) * 1000, 1)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{result['note']}\n")
        for r in result["results"]:
            gate_mark = "*" if r["above_enrichment_gate"] else " "
            print(f"{gate_mark} {r['score']:.3f}  [[{r['title']}]]  ({r['path']})  via {'+'.join(r['channels'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
