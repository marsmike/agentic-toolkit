#!/usr/bin/env python3
"""Readwise pipeline status: last sync, unprocessed captures, DLQ count.

Reads `00_Memory/readwise-state.md` — operational state, not vault content
(contract/VAULT_SCHEMA.md: "00_Memory/ ... Never distill into it, never enrich from it").
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from vault_utils import UnparseableFrontmatter, iter_captures, read_frontmatter, require_vault

STATE_NOTE = Path("00_Memory") / "readwise-state.md"


def read_state(vault: Path) -> dict:
    path = vault / STATE_NOTE
    if not path.is_file():
        return {}
    try:
        fm, _ = read_frontmatter(path)
    except UnparseableFrontmatter:
        return {}
    return fm


def pipeline_status(vault: Path) -> dict:
    state = read_state(vault)
    captures = iter_captures(vault)
    dlq_dir = vault / "00_Memory" / "dlq"
    dlq_count = len(list(dlq_dir.glob("*readwise*"))) if dlq_dir.is_dir() else 0
    return {
        "last_synced_at": state.get("lastSyncedAt", "never"),
        "last_processed_at": state.get("lastProcessedAt", "never"),
        "captures_awaiting_distillation": len(captures),
        "dlq_entries": dlq_count,
        "state_note_exists": bool(state),
    }


def _main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    vault = require_vault()
    result = pipeline_status(vault)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Readwise Pipeline Status:")
        print(f"  Last sync:      {result['last_synced_at']}")
        print(f"  Last processed: {result['last_processed_at']}")
        print(f"  Awaiting distillation: {result['captures_awaiting_distillation']} captures in 01_Capture/")
        print(f"  DLQ entries: {result['dlq_entries']}")
        if not result["state_note_exists"]:
            print("  (no state note yet — never synced; run the ingest skill)")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_main())
