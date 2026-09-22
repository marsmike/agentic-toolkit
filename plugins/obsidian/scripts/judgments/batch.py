"""Pairwise uniqueness across a batch of captures: which pairs are worth asking, which are
duplicates by text or source alone, and the judged answer for the rest."""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import judge

from judgments import questions as Q
from judgments.capture import read_capture
from judgments.policy import thresholds
from judgments.state import in_chunks
from judgments.urls import _canonical

BATCH_CAPTURE_CHARS = 2000

MAX_BATCH = 12  # captures per full pairwise request; above that, pairs are blocked first

PAIR_BLOCK_JACCARD = 0.34  # title-token overlap at or above: a pair worth judging

NEAR_IDENTICAL = 0.85      # body similarity at or above (difflib, first 6000 chars): a duplicate, decided without a model

def _title_tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]{3,}", text.lower()) if w not in ("the", "and", "for", "with", "how", "why", "what")}

def candidate_pairs(caps: dict[str, dict]) -> list[tuple[str, str]]:
    """Which capture pairs are worth a uniqueness judgment. Up to MAX_BATCH captures, all of
    them. Above that, cheap blocking: the same own source, a shared URL, or title-token
    overlap at or above PAIR_BLOCK_JACCARD. [earned: 2026-09-22 acceptance run — the batch
    judged only the first twelve of 81 captures and missed a video Reader held twice]"""
    ids = list(caps)
    if len(ids) <= MAX_BATCH:
        return [(a, b) for i, a in enumerate(ids) for b in ids[i + 1:]]
    out = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            ca, cb = caps[a], caps[b]
            same_source = ca["own_source"] and _canonical(ca["own_source"]) == _canonical(cb["own_source"])
            shared_url = bool(set(map(_canonical, ca["source_urls"])) & set(map(_canonical, cb["source_urls"])))
            ta, tb = _title_tokens(ca["title"]), _title_tokens(cb["title"])
            jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
            if same_source or shared_url or jac >= PAIR_BLOCK_JACCARD:
                out.append((a, b))
    return out

def judge_batch(paths: list[Path], vault: Path, refs: list[str] | None = None) -> dict[str, Any]:
    """Pairwise uniqueness over a batch. `refs` name the captures in the output (default: file
    names); golden files pass their own. Pairs are asked in both directions, in chunks that
    carry only the captures they need."""
    ids = {f"C{i:02d}": p for i, p in enumerate(paths, start=1)}
    caps = {cid: read_capture(p) for cid, p in ids.items()}
    names = {cid: (refs[i] if refs else p.name) for i, (cid, p) in enumerate(ids.items())}
    pairs_to_ask = candidate_pairs(caps)
    usages: list = []

    def ask(chunk, start):
        members = sorted({c for pair in chunk for c in pair})
        state = {"captures": {c: {"title": caps[c]["title"], "description": caps[c]["description"],
                                  "body": caps[c]["body"][:BATCH_CAPTURE_CHARS]} for c in members}}
        questions = {}
        for a, b in chunk:
            questions[f"adds_{a}_{b}"] = Q.adds(a, b)
            questions[f"adds_{b}_{a}"] = Q.adds(b, a)
        got, used = judge.judge(vault, state, questions)
        usages.append(used)
        return got

    # Reader holding one item twice is a fact, not a judgment: the same own source address, or
    # near-identical text, settles the pair without a model call.
    identical = {}
    for a, b in pairs_to_ask:
        same_source = caps[a]["own_source"] and _canonical(caps[a]["own_source"]) == _canonical(caps[b]["own_source"])
        if same_source:
            identical[(a, b)] = "same source"
            continue
        ratio = SequenceMatcher(None, caps[a]["body"][:6000], caps[b]["body"][:6000]).quick_ratio()
        if ratio >= NEAR_IDENTICAL and SequenceMatcher(None, caps[a]["body"][:6000], caps[b]["body"][:6000]).ratio() >= NEAR_IDENTICAL:
            identical[(a, b)] = round(ratio, 3)
    pairs_to_ask = [pr for pr in pairs_to_ask if pr not in identical]
    answers = in_chunks(pairs_to_ask, 6, ask) if pairs_to_ask else {}
    dup_rows = [{"a": names[a], "b": names[b], "a_adds": None, "b_adds": None, "verdict": "duplicate",
                 "adds_nothing": [names[b]], "similarity": r} for (a, b), r in identical.items()]
    if not usages:
        return {"cluster": dup_rows, "judgment": {}, "answers": {}, "pairs_considered": len(identical), "captures": len(paths),
                "blocked": len(paths) > MAX_BATCH}
    usage = usages[0]
    for extra in usages[1:]:
        usage.requests += extra.requests
        usage.input_tokens += extra.input_tokens
        usage.usd += extra.usd
        usage.splits += extra.splits
        usage.skipped.extend(extra.skipped)
    t = thresholds(usage.backend)
    pairs, raw = list(dup_rows), {}
    for a, b in pairs_to_ask:
        ab, ba = answers.get(f"adds_{a}_{b}"), answers.get(f"adds_{b}_{a}")
        if ab is None or ba is None:
            continue
        raw[f"adds|{names[a]}|{names[b]}"] = round(ab.p, 4)
        raw[f"adds|{names[b]}|{names[a]}"] = round(ba.p, 4)
        redundant = [names[x] for x, ans in ((a, ab), (b, ba)) if 1 - ans.p >= t["T_REDUNDANT"]]
        pairs.append({"a": names[a], "b": names[b], "a_adds": round(ab.p, 3), "b_adds": round(ba.p, 3),
                      "verdict": "merge-candidate" if redundant else "distinct", "adds_nothing": redundant})
    return {"cluster": pairs, "judgment": usage.as_dict(), "answers": raw,
            "pairs_considered": len(pairs_to_ask) + len(identical), "captures": len(paths),
            "blocked": len(paths) > MAX_BATCH}
