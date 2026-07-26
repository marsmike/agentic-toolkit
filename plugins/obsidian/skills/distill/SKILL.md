---
name: distill
description: Process captures into vault knowledge — triage the inbox, distill one file, or file a conversation insight. Use when working with 01_Capture/.
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
---

# Knowledge Distillation

Transforms raw captures from `01_Capture/` into integrated, linked knowledge notes.
Filesystem-first throughout — no CLI or embeddings store is required to run this
workflow; `vault/CLAUDE.md`'s "Distilling captures" section states the two
non-negotiable rules (two-phase checkpoint, source preservation) that hold even without
this skill loaded. Read [rules.md](references/rules.md) before starting.

## Modes

| Mode | Use for | Reference |
|------|---------|-----------|
| **Distill** (default) | Full pipeline: capture → search → PARA placement → enrichment → write | [workflow.md](references/workflow.md) |
| **Triage** | List and prioritize the inbox before distilling | [workflow.md](references/workflow.md) — Triage section |
| **Insight** | File a conversation synthesis as a new capture, then distill it | [workflow.md](references/workflow.md) — Insight section |

## Hard requirements (non-negotiable, see rules.md for the full list)

1. **Two phases, one checkpoint.** Analyze and propose, then stop for review before
   writing anything. Skip only on an explicit `--auto`/non-interactive instruction.
2. **Search before writing.** Run `scripts/search.py` against the capture's key terms —
   it degrades gracefully with no embeddings store present, but it must run; a distill
   pass with zero search is a name for "guessing at what already exists." When a
   `gaiafield` binary is available, `scripts/graph.py`'s `graph_context()` also adds
   graph-derived backlink/bridge candidates the text search alone missed (see
   workflow.md); its absence never blocks this step.
3. **Every distilled note carries its source** — a `*Source: ...*` line in the body and
   a `source:` frontmatter field — and gets `status: distilled`.
4. **The capture leaves `01_Capture/`** after distilling — archived (default, to
   `05_Archive/<Origin>-Captures-<YYYY-MM>/`) or deleted (duplicates/empty stubs only).
5. **Ambiguity goes to the DLQ, not a guess.** If placement, source, or search results
   are genuinely unclear after one honest attempt, write a dead-letter note to
   `00_Memory/dlq/` via `scripts/vault_utils.write_dlq_note()` and say so in the
   Phase 1 report, rather than silently picking an answer.

## Quick start

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/search.py" "key terms from the capture" --top 10 --json
```

Then follow [workflow.md](references/workflow.md)'s numbered steps.

## References

- [Workflow](references/workflow.md) — the full distill/triage/insight procedure
- [Rules](references/rules.md) — PARA placement logic, enrichment levels, the DLQ convention, cluster mode
