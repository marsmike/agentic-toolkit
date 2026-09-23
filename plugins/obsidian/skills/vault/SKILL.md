---
name: vault
description: Work with the vault directly — read, create, edit and search notes, frontmatter, links, canvases and Bases — and keep it healthy (orphans, stale pages, broken links, Index drift, metadata). Use for any vault operation or maintenance audit.
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
---

# Vault

The vault is plain Markdown in PARA folders (`contract/VAULT_SCHEMA.md`), so `Read`, `Write`,
`Edit`, `Grep` and `Glob` are the interface; no server sits in between. Resolve the vault first:
`TOOLKIT_VAULT`, else `./vault` in the repo (`contract/PROFILE.md`). Paths below are vault-relative.

```bash
S() { uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/$1" "${@:2}"; }
S search.py "query" --top 10 --json          # ranked: BM25, plus semantic when installed
S vault_lint.py [--stale-days 180] [--json]  # orphans, stale, missing concepts, Index drift
S vault_normalize.py --check links|frontmatter|tags|source|summary [--scope 04_Resources] [--fix --dry-run]
S vault_judge.py [--scope 04_Resources]      # vague descriptions, missing domain tags (report only)
```

## Finding things

Start at `Now.md` (what changed), `Index.md` (one line per note) and `Maps/<domain>.md` (a domain
by kind, its hubs first); `grep` the descriptions in `Index.md` before full-text search. All four
are generated: never edit them, fix the note and let the pipeline rebuild them.

## Writing

- A new note is a file in the right PARA folder with YAML frontmatter; an edit is a text edit.
  Read and write frontmatter **tolerant of unknown fields**: the field table is a floor, never
  drop a key you did not set (`vault_utils.read_frontmatter`/`write_frontmatter` do this).
- New material goes into `01_Capture/` (flat, origin-prefixed) and through the distill skill,
  never straight into `02_`–`04_`. Never link into `00_Memory/`, `01_Capture/` or `05_Archive/`.
- Obsidian syntax (links, embeds, callouts, `.canvas`, `.base`, the optional desktop CLI and
  its exit-0 trap): [obsidian-syntax.md](references/obsidian-syntax.md).

## Health

**Audit-only by default: nothing is written without `--fix`, and always `--fix --dry-run`
first.** `vault_lint.py` needs nothing but PyYAML. `vault_normalize.py`'s LLM-assisted checks
(`frontmatter`, `tags`, `source`, `summary`, ambiguous `links`) print `SKIPPED — no
inference_model configured` without one; that is not an error. A note whose frontmatter does not
parse is skipped and written to `00_Memory/dlq/`, never guessed at.

Both tools scan `02_Projects/`, `03_Areas/`, `04_Resources/` only; `--exclude <prefix>` keeps
private paths away from any model call. Link targets are checked vault-wide (a link may point at
a root or `Config/` note). Links from generated navigation never count as a note's inbound link.

`vault_judge.py`, `link_judge.py` and `vault_sweep.py` (duplicates, contradictions) need a
judgment key and write nothing: treat their output as a reading list. With a key the `links`
check proposes a target per broken link; `--fix` applies only p ≥ 0.80.

Tags: 3–7 per note (content type + `domain/*` + context); edit `DOMAIN_TAGS` in
`checks/tags.py` to what actually recurs in the vault.

## References

- [obsidian-syntax.md](references/obsidian-syntax.md): links, embeds, callouts, properties, Canvas, Bases, desktop CLI
- [checks.md](references/checks.md): each lint and normalize check in detail
- [taxonomy.md](references/taxonomy.md): tag taxonomy and assignment
- [backlink-workflows.md](references/backlink-workflows.md): post-distill verification, orphan and connection discovery
