---
name: vault-ops
description: Read, create, edit, and search vault notes directly on the filesystem — CRUD, frontmatter, wikilinks, canvases, and Bases. Use when performing vault operations.
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
---

# Vault Operations

Filesystem-first vault CRUD, per `contract/KNOWLEDGE_API.md`: the vault is plain
markdown, so `Read`/`Write`/`Edit`/`Grep`/`Glob` are first-class, not a fallback for when
some other tool is unavailable. No MCP server sits between an agent and the vault —
direct filesystem access beats that indirection by roughly 35× on token overhead.

## Vault location

Resolve the vault before touching any path: `TOOLKIT_VAULT` env var, else `./vault`
relative to the repo root (`contract/PROFILE.md`). Every path below is vault-relative.

## Quick start

```bash
# Read a note
cat "$VAULT/03_Areas/Some-Area.md"

# Search by keyword or path
grep -rl "some term" "$VAULT/02_Projects" "$VAULT/03_Areas" "$VAULT/04_Resources"

# Ranked search (keyword + optional semantic) — see references/commands.md
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/search.py" "query" --top 10 --json
```

Create/edit notes with the `Write`/`Edit` tools directly — a new note is a file under the
right PARA folder (`contract/VAULT_SCHEMA.md`) with a YAML frontmatter block; an edit is
a normal text edit. There is no CLI layer to route through for either operation.

## Frontmatter

Parse and write frontmatter tolerant of unknown fields — the field table in
`contract/VAULT_SCHEMA.md` is a floor, not a ceiling. Never reject a note or strip a
field for being unrecognized. `scripts/vault_utils.py`'s `read_frontmatter`/
`write_frontmatter` implement this if you're scripting; by hand, just preserve whatever
YAML keys were already there.

## Optional: the Obsidian desktop CLI

If the user has Obsidian running with *Settings → General → Advanced → Command line
interface* enabled, its `obsidian` binary offers the same operations plus live-app
niceties (daily notes, backlink queries against the actual graph, plugin dev tools). It
is an optional enhancement, never a requirement — everything in this skill works with
zero Obsidian process running. See [commands.md](references/commands.md) if you want it,
including the one hard trap: **the CLI exits 0 and prints an error string on stdout when
disabled** — never trust its exit code, check the output.

## References

- [commands.md](references/commands.md) — optional Obsidian desktop CLI reference, syntax, its silent-failure trap
- [markdown-syntax.md](references/markdown-syntax.md) — wikilinks, callouts, embeds, properties, tags
- [properties.md](references/properties.md) — standard frontmatter schemas
- [json-canvas.md](references/json-canvas.md) — `.canvas` file format
- [obsidian-bases.md](references/obsidian-bases.md) — `.base` file format
