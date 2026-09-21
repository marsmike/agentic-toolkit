#!/usr/bin/env python3
"""Adjudicated link suggestions — gaiafield's inferred candidates plus a typed judgment each.

    uv run scripts/link_judge.py --note 04_Resources/Concepts/Hybrid-Retrieval.md
    uv run scripts/link_judge.py --surprise --top 20 --include-ambiguous --json

gaiafield proposes pairs from embedding similarity and labels them INFERRED or AMBIGUOUS
against two model-calibrated gates. Its AMBIGUOUS band is, by its own README, overlap
"a human, not a gate, should adjudicate". This script asks a typed-judgment backend
(judge.py) one narrow question per pair, "would a link between these two help a reader?",
and attaches the probability as `adjudication` so that human reads a short list first.

Report-only, like everything about inferred edges (contract/KNOWLEDGE_API.md v2, rule 1):
nothing is written to the vault, gaiafield's own score, label and order are untouched, and
AMBIGUOUS rows appear only when asked for with --include-ambiguous.
"""
from __future__ import annotations

import argparse
import json

import graph
from vault_utils import require_vault


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    what = ap.add_mutually_exclusive_group(required=True)
    what.add_argument("--note", help="vault-relative note: adjudicate its inferred candidates")
    what.add_argument("--surprise", action="store_true", help="adjudicate the vault-wide surprise ranking")
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--include-ambiguous", action="store_true", help="only when the human asked for the AMBIGUOUS band")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    vault = require_vault()

    rows = (
        graph.surprise_candidates(vault, top=args.top, include_ambiguous=args.include_ambiguous)
        if args.surprise
        else graph.inferred_candidates(vault, args.note, k=args.top, include_ambiguous=args.include_ambiguous)
    )
    if isinstance(rows, graph.GraphUnavailable):
        print(json.dumps({"unavailable": rows.reason, "detail": rows.detail}) if args.json
              else f"no inferred candidates: {rows.reason} ({rows.detail})")
        return 0

    judged = graph.adjudicate_candidates(vault, rows, note=args.note)
    if isinstance(judged, graph.GraphUnavailable):
        note = f"adjudication skipped: {judged.reason} ({judged.detail})"
        judged = rows
    else:
        note = "advisory adjudication attached; report-only, nothing is linked automatically"

    if args.json:
        print(json.dumps({"note": note, "rows": judged}, indent=2))
        return 0
    print(note)
    for row in judged:
        verdict = row.get("adjudication") or {}
        pair = f"{row['a']}  <->  {row['b']}" if "a" in row else row.get("path", "")
        print(f"  {verdict.get('label', '--'):<13} p={verdict.get('p', '--')!s:<6} {row.get('label', ''):<9} "
              f"score={row.get('score', 0):.2f}  {pair}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
