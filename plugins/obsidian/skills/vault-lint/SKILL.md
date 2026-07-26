---
name: vault-lint
description: Vault health — metadata normalization, orphans, stale pages, broken links, and tag taxonomy. Use when running vault maintenance or audits.
allowed-tools:
  - Bash
  - Read
---

# Vault Lint

Vault health, metadata normalization, and link verification. **Audit-only by default —
nothing is written unless you pass `--fix`.**

## Two tools, different jobs

### 1. `vault_lint.py` — structure (report only, no LLM)

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/vault_lint.py" [--stale-days 180] [--json]
```

Orphans, stale pages, missing concepts (wikilink targets referenced 2+ times with no
page), Index.md drift. Needs nothing beyond PyYAML — works on a fresh clone immediately.

### 2. `vault_normalize.py` — metadata (audit + fix, LLM-assisted for some checks)

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/vault_normalize.py" \
  --check tags --scope 04_Resources --fix --dry-run
```

| Check | What it does | Needs an LLM |
|---|---|---|
| `links` | Broken wikilinks: fuzzy-match auto-fix, LLM-assisted for the rest | Only for ambiguous cases |
| `frontmatter` | Fills `status`, `description`; enforces `source`/`processed_date` on distilled notes | Yes, for description/status generation |
| `tags` | Classifies a `domain/*` taxonomy, migrates legacy free-form tags | Yes |
| `source` | Extracts the source URL from the body | Yes |
| `summary` | Regenerates bootstrap-quality (⚙-marked) `Index.md` entries | Yes |

**No inference_model configured (the shipped default) is not an error.** Every
LLM-assisted check skips cleanly with a `SKIPPED — no inference_model configured` result
rather than crashing or hanging on a connection attempt — see `profile.example.md` to
point it at a local Ollama server or an OpenAI-compatible endpoint.

**Always `--fix --dry-run` before `--fix`.** Dry-run writes nothing; read its report to
confirm the proposed changes before applying them.

A note whose frontmatter block exists but fails to parse is **skipped, not guessed** —
`vault_normalize.py` refuses to write through a broken YAML block (that would emit a
second, shadowing frontmatter block) and instead writes a dead-letter note to
`00_Memory/dlq/` naming the note and why.

## Scope

Both tools default to active folders only: `02_Projects/`, `03_Areas/`, `04_Resources/`.
`00_Memory`, `01_Capture`, `05_Archive` are never scanned or auto-fixed. `--exclude
<prefix>` (repeatable) additionally skips private paths that must never reach an LLM
call, e.g. `--exclude 03_Areas/Personal`.

**Link-target existence is checked vault-wide**, not just in active folders — a
wikilink can validly point at a root-level or `Config/` note (a persona, a profile),
so `checks/links.py` builds its note index from everywhere except
`00_Memory/01_Capture/05_Archive` (which active content must never link into anyway).

## Enrichment/tag rules

Semantic-adjacent connections use the vault's `search_score_gate` (default 0.70).
Tags: aim 3-7 per note (content type + domain + context); `DOMAIN_TAGS` in
`checks/tags.py` is a *starter* taxonomy — edit it to match what actually recurs in your
vault, not the default categories.

## References

- [checks.md](references/checks.md) — what each lint/normalize check does, in detail
- [taxonomy.md](references/taxonomy.md) — tag taxonomy and assignment guidance
- [backlink-workflows.md](references/backlink-workflows.md) — post-distill verification, orphan/connection discovery
