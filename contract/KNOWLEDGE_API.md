# Knowledge API

How plugins read and write vault knowledge: the filesystem, plus CLI tools that speak JSON. No MCP
server sits between a plugin and the vault.

**Rationale:** direct filesystem/CLI access to vault content beats MCP-server indirection by
roughly 35× on token overhead for vault access.
`[earned: Obsidian-Agent-Access-MCP-vs-Filesystem-2026, ~35× token overhead]`

## v0 — implemented by `core` (R0)

The baseline surface every plugin can rely on:

- **Note CRUD** — create, read, update, delete notes via the filesystem, subject to the placement
  and lifecycle rules in `contract/VAULT_SCHEMA.md` (e.g. never write into `05_Archive/`, never
  delete via an irreversible operation).
- **Frontmatter read/write** — parse and update frontmatter tolerant of unknown fields (the
  floor-not-ceiling rule in `contract/VAULT_SCHEMA.md`); a write-back never strips a field the
  caller didn't touch.
- **Capture-inbox append** — append a new capture into `01_Capture/` following its naming and
  flatness rules.

These are filesystem operations first; where `core` exposes one as a CLI command, the command
takes flags in and returns JSON out.

## v1+ — reserved for the Rust engines

A stable CLI-in/JSON-out interface that plugins may call but must never bypass by reading an
engine's internal state (index files, databases) directly:

- **farsight** — `query`: hybrid BM25+vector search over vault and PDF chunks.
- **gaiafield** — `neighbors`, `context`, and other graph queries over the link/frontmatter/tag
  graph.

Until an engine ships, plugins needing this behavior fall back to the v0 surface (e.g. grep-based
search) rather than inventing a competing interface.

## No cross-plugin imports

Plugins depend on `core` and `contract` only, never on a sibling plugin. Composition across
plugins happens through vault notes — one plugin writes a note, another reads it — never through
a direct call from one plugin's code into another's.
