---
name: ingest
description: Pull new Readwise highlights (Reader v3 + Classic v2) and write them as origin-prefixed capture notes in 01_Capture/. Use when syncing Readwise or running the full pipeline's first stage.
allowed-tools:
  - Bash
  - Read
  - Write
  - Grep
  - Glob
---

# Readwise Ingest

Every Reader library item not yet in the vault becomes a capture in `01_Capture/`, in one
scripted run with no agent steps:

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/ingest.py" --json
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/ingest.py" --dry-run   # counts only
```

It fetches everything changed since `lastSyncedAt` plus a backlog sweep of new/later/shortlist,
skips feed items (unless the radar promoted them, tag `radar`), fetches each item's full text,
and writes one capture per item with its provenance: `via: clip` (you saved it), `newsletter`
(delivered) or `radar` (promoted, with `radar_interests`). Dedup is a ledger,
`00_Memory/readwise-ingested.jsonl`, plus the vault itself (a capture with the same doc id, or a
note whose `source` is the item's address). Nothing in Reader is moved or deleted.

The obsidian `pipeline` skill runs this, then distill, on a schedule; run it by hand only to
catch up or to check a dry run. What the script does, step by step and why:
[references/ingest-workflow.md](references/ingest-workflow.md).

## Preservation rule (non-negotiable)

**Every clipping the user saved must end up in `01_Capture/`.** Never drop an item because it
looks noisy, off-topic, or short. The script enforces it: an item fetched but not captured fails
the run with a DLQ note, and the watermark does not move until it is captured. Distill may drop
a `newsletter` or `radar` capture; it never drops a `clip`.

## Hard requirements

1. **Backlog sweep, every run** (the script does it): `updated_after` is a watermark, not an
   inventory.
2. **Dedup-safe writes**: a re-run never writes a second capture for the same doc id.
3. **Nothing in Reader is deleted or moved by ingest.** Cleanup, if ever wanted, is a separate
   explicit request.

## References

- [ingest-workflow.md](references/ingest-workflow.md) — what `ingest.py` does and why
- [api.md](references/api.md) — Readwise API endpoint reference and rate limits
