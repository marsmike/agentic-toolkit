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

Pulls new clippings from the Readwise API and writes each one as a capture note in
`01_Capture/` — flat, origin-prefixed (`Readwise-...`), filesystem-first throughout
(`contract/KNOWLEDGE_API.md`). No enrichment happens here; that's the `enrich` skill.

## Preservation rule (non-negotiable)

**Every clipping the user saved must end up in `01_Capture/`.** Never drop an item because
it looks noisy, off-topic, or short — the user sometimes clips outside their usual
interests on purpose. See [references/ingest-workflow.md](references/ingest-workflow.md)
for the coverage check that enforces this before any deletion from Readwise.

## Quick start

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 -c "
import readwise_api as rw
items = rw.reader_list_all(updated_after='2026-06-01')
print(len(items), 'items')
"
```

Then follow [references/ingest-workflow.md](references/ingest-workflow.md)'s numbered steps.

## Vault resolution and profile

`TOOLKIT_VAULT` env var, else `./vault` relative to the repo root (`contract/PROFILE.md`).
Profile: `$VAULT/Config/toolkit/readwise.md` — see `profile.example.md` for fields
(`enrichers`, `backlog_sweep`). Secrets stay in `READWISE_TOKEN`, never in the vault.

## Hard requirements

1. **Backlog sweep, every run.** `updated_after` is a watermark, not an inventory — items
   saved before the window and never captured stay invisible forever otherwise. See
   references/ingest-workflow.md.
2. **Dedup-safe writes.** `build_captures.write_capture()`/`write_book_capture()` check
   `01_Capture/` for an existing note with the same `readwise_doc_id` before writing —
   re-running ingest over the same clipping is a no-op, not a second file.
3. **Coverage check gates deletion.** Never delete/archive anything in Readwise until
   every ingested `doc_id` is confirmed present in a written capture.

## References

- [ingest-workflow.md](references/ingest-workflow.md) — full procedure: fetch, backlog
  sweep, write, coverage check, cleanup
- [api.md](references/api.md) — Readwise API endpoint reference and rate limits
