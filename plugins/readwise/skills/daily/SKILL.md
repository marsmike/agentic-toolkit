---
name: daily
description: Digest today's new Readwise captures from 01_Capture/ to stdout, grouped by category. Use for a quick daily catch-up without running the full pipeline.
allowed-tools:
  - Bash
  - Read
---

# Readwise Daily

Scans `01_Capture/` (flat) for captures created or modified today and prints a grouped
digest — tweets, articles, videos, newsletters, books, other. Read-only: never writes,
never deletes, never calls the Readwise API.

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/daily_digest.py" [--date YYYY-MM-DD]
```

Surface the digest in conversation. This skill deliberately does not write a durable log
entry anywhere — v1 shelled out to the obsidian plugin's `log_vault.py` directly, which is
a cross-plugin import `contract/KNOWLEDGE_API.md` rules out. If a durable record is
wanted, the invoking agent writes it itself (e.g. via the obsidian plugin's own tooling,
composed through the vault, not through a direct call into this plugin's script).

A missing `01_Capture/` directory is reported as an error, not an empty digest — a `find`
over a directory that doesn't exist returns nothing and exit 0, which in the source
project this was ported from hid a broken path for months without anyone noticing.
