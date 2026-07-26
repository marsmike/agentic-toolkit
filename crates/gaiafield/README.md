# gaiafield

Deterministic knowledge-graph extraction over an agentic-toolkit vault's wikilinks. R2 of the
engine named in `docs/PLAN.md` (Engines) and `contract/KNOWLEDGE_API.md` — v1 scope only: parse
wikilinks, frontmatter, and tags into a queryable SQLite store. No model call, no edge that can
hallucinate — see `vault/04_Resources/Concepts/Deterministic-vs-Inferred-Graph-Edges.md`. Inferred
(similarity-threshold) edges are R3+, not this crate.

## Usage

```bash
gaiafield index [--vault ./vault] [--db <path>] [--full] [--json]
gaiafield neighbors <note> [--depth N] [--direction in|out|both] [--json]
gaiafield stats [--json]
gaiafield path <from> <to> [--json]
```

- `--vault <path>` — explicit vault path. Falls back to `TOOLKIT_VAULT`, then `./vault` relative
  to a repo root found by walking up for `.claude-plugin/marketplace.json` (mirrors
  `crates/farsight` and `core/toolkit_core/vault.py::resolve_vault`).
- `--db <path>` — SQLite database location. Defaults to `<vault>/.gaiafield/graph.db`.
- `<note>` (for `neighbors`/`path`) — a vault-relative path (with or without `.md`) or a bare
  note name, resolved with wikilink semantics. A bare name matching more than one indexed note
  (this vault plants exactly one such case: `Weekly-Review`, once per project) is reported as
  ambiguous with every candidate listed — never picked silently.

## Node scope

Nodes are the schema's active-content notes — `02_Projects/`, `03_Areas/`, `04_Resources/`
(`contract/VAULT_SCHEMA.md`; matches `vault/Index.md`'s stated count) — **plus** any note directly
at the vault root whose own frontmatter declares `status: active`. In the example vault that adds
exactly one node: `Alex-Vega.md`.

**Why the addition:** taken literally, the schema's active-content filter is exactly those three
folders for "any generated index," which would exclude a root-level note. But
`vault/04_Resources/Guides/Test-Corpus-Map.md` names Alex-Vega as *the* bridge note ("root
persona, links into all three clusters"), and excluding it would make the planted bridge structure
this vault was built to test unreachable. The note's own frontmatter already opts in
(`status: active` — the note-lifecycle meaning of "active" in the same schema's frontmatter table,
distinct from the folder-level filter), so this crate honors that self-declaration narrowly:
nothing else at the root joins the node set (`Index.md` and `CLAUDE.md` carry no frontmatter at
all), and `Config/`/`Templates/` are never scanned — they hold plugin config and templates, not
vault content.

`00_Memory/`, `01_Capture/`, and `05_Archive/` are never nodes. A wikilink from active content
into one of them is recorded as a **boundary violation**, not a normal edge — the schema forbids
the link outright.

## Edge extraction

Edges come from body wikilinks only (`[[Target]]` / `[[Target|Alias]]`) — not from frontmatter
fields such as `enrichment_targets`, and not from shared tags. `docs/PLAN.md` describes v1's
inputs as "wikilinks/frontmatter/tags"; this crate reads frontmatter and tags into **node
metadata** (`title`, `description`, `status`, `kind`, `tags`) and reserves tag/frontmatter-derived
*edges* for a later increment, since v1's job is proving out the deterministic wikilink graph
first.

Each wikilink target resolves one of four ways:

1. **Node** — resolves to another indexed node; recorded as an `EXTRACTED` edge.
2. **Boundary violation** — resolves to a real file inside `00_Memory`/`01_Capture`/`05_Archive`;
   recorded with a flag, counted separately in `stats`.
3. **Out of scope** — resolves to a real vault file that simply isn't a node (`Config/`,
   `Templates/`, a root note without `status: active`, `Index.md`, `CLAUDE.md`). Not an error, not
   flagged — just outside what this graph models, the same way search's active-content filter
   silently doesn't surface it either. No edge row is written.
4. **Dangling** — doesn't resolve to any file anywhere in the vault; recorded with a flag. The
   example vault plants exactly one: `[[Nonexistent-Note-For-Linting-Demo]]` in
   `Vault-Maintenance-and-Linting.md`.

A bare-name target ambiguous between multiple real files (the planted `Weekly-Review` case) is
resolved same-folder-first — if the linking note's own directory holds one of the candidates,
that one wins, matching how every planted in-folder `[[Weekly-Review]]` link in this vault is
meant to resolve. If it's still ambiguous (no same-folder candidate — the two cross-cluster
mentions in `Toolkit-Maintenance.md` and `Running-Evals.md`), the extractor records an edge to
*every* candidate rather than silently guessing one — deterministic in the sense that it never
hallucinates a choice the source text doesn't make. This is deliberately more permissive than the
CLI's own bare-name lookup (`neighbors`/`path`), which has no source-note context to disambiguate
by proximity and refuses to guess at all.

## Incremental indexing

`index` compares each node's file mtime + size against the stored value and only re-extracts
new/changed notes; rows for notes removed from the vault are deleted along with their outgoing
edges. `--full` drops and rebuilds everything. This mirrors farsight's staleness-averse design
philosophy applied to a persisted store instead of a stateless scan — a graph has to persist to be
queryable by `neighbors`/`path`/`stats`, so unlike farsight it can't avoid a cache; incremental
re-extraction is the freshness discipline it gets instead.

## Graph queries

- `neighbors` — BFS out to `--depth` hops (default 1). `--direction` filters to `in`, `out`, or
  the default `both` (an edge is traversable either way) — "what's connected to this note" is
  usually the more useful question than a direction-strict one.
- `path` — shortest path via BFS over the same undirected view of the graph, or a clear
  not-connected answer.
- `stats` — node/edge counts, dangling-edge and boundary-violation counts, and the top 10 notes by
  in-degree.

`context` is named alongside `neighbors` in `contract/KNOWLEDGE_API.md`'s reserved surface but not
implemented here — the same incremental-delivery pattern farsight used for its own vector half:
the reserved verb exists, the increment that ships it doesn't yet.

## Testing

`tests/graph_test.rs` is the only test file, run against the repo's own `./vault` (never a user's
vault, per `CONTRIBUTING.md`) against the planted structure in
`vault/04_Resources/Guides/Test-Corpus-Map.md`: node count and link density, the one planted
dangling edge, zero boundary violations, the Alex-Vega bridge reaching all three clusters within
depth 2, a birding-to-homelab path, the ambiguous `Weekly-Review` lookup, and incremental
re-indexing touching only the changed note. Every test uses its own throwaway database under the
system temp dir — never `vault/.gaiafield/graph.db` — so a test run never leaves an untracked
database inside the example vault.

## Cross-compilation note

This crate's `rusqlite` dependency uses the `bundled` feature, which compiles SQLite's C
amalgamation — unlike `farsight`, which has no C dependencies at all. `.github/workflows/
release-binaries.yml` cross-compiles `aarch64-unknown-linux-musl` via
`taiki-e/setup-cross-toolchain-action`, which (per its own `main.sh`) pulls a real cross
toolchain image and sets `CC_<target>`/`CXX_<target>`/`AR_<target>` env vars that `cc-rs` (the
build-time dependency `libsqlite3-sys` uses to invoke a C compiler) reads directly — so this
should work without a workflow change. This is a static read of the action's script, not a
verified build; the first `gaiafield-v*` tag push is the real test.
