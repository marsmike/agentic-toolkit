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

## v2 — inferred edges (R5)

The graph carries two kinds of edges, and they are never conflated:

- **`extracted`** — deterministic: a wikilink physically present in a note body. Carries the
  dangling/boundary flags from v1. Never carries a similarity score.
- **`inferred`** — statistical: semantic similarity between two notes' content, computed by
  gaiafield's embedding pass. Carries `score` in [0,1] and a `label`:
  - **`INFERRED`** — score at or above the model-calibrated high gate. Eligible for *reporting*
    as a candidate.
  - **`AMBIGUOUS`** — score inside the band between the low and high gates. Surfaced only when a
    caller explicitly asks; never proposed proactively.

Rules, in order of importance:

1. **Report-only, forever.** No automation may write vault content — a link, an enrichment, a
   note — from an inferred edge without explicit human confirmation in that session. Inferred
   edges are *candidates for a human decision*, never inputs to an autonomous write. This is the
   successful-corruption guard: a wrong inferred edge that auto-applied would corrupt the vault
   while reporting success. `[earned: gaiafield R2 deletion bug, 2026-07-26 — the deterministic
   layer already produced one silent-corruption class; the statistical layer does not get the
   chance]`
2. **Inference never mutates extraction.** Inferred edges live in their own rows; recomputing
   embeddings or rescoring never touches an `extracted` row. Deleting all inferred edges must
   restore the exact v1 graph.
3. **Gates are model-calibrated, not universal.** The high/low gates are properties of the
   embedding model, calibrated against the example vault's planted clusters (intra-cluster pairs
   must score above cross-cluster pairs); switching models requires recalibration. A gate value
   without its model name is meaningless.
4. **Traversal defaults to deterministic.** `neighbors`/`path` use `extracted` edges only unless
   the caller passes an explicit include-inferred flag; results always label which edge kind
   produced them.
5. **Surprise scoring is derived, not stored magic**: an inferred edge between notes whose
   deterministic graph distance is large (or infinite) in different PARA subtrees — the
   cross-domain candidates worth a human look. Deterministic formula, documented in the crate.

## No cross-plugin imports

Plugins depend on `core` and `contract` only, never on a sibling plugin. Composition across
plugins happens through vault notes — one plugin writes a note, another reads it — never through
a direct call from one plugin's code into another's.
