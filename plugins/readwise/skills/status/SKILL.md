---
name: status
description: Show Readwise pipeline health — last sync, last processed, captures awaiting distillation, DLQ count. Use to check state before deciding whether to run ingest.
allowed-tools:
  - Bash
  - Read
---

# Readwise Status

Read-only summary of pipeline state, sourced from `00_Memory/readwise-state.md` (never
distilled into, never enriched from — `contract/VAULT_SCHEMA.md`) and a scan of
`01_Capture/`.

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/status.py" --json
```

Present:

```
Readwise Pipeline Status:
  Last sync:      YYYY-MM-DD HH:MM UTC
  Last processed: YYYY-MM-DD HH:MM UTC
  Awaiting distillation: N captures in 01_Capture/
  DLQ entries: N
```

No state note yet means this vault has never been synced — say so plainly and suggest
`/readwise-process` rather than reporting zeroes that look like "nothing to do."
