# farsight

Stateless BM25 search over an agentic-toolkit vault. R1 of the engine named in
`docs/PLAN.md` (Engines) and `contract/KNOWLEDGE_API.md` — replaces the BM25 half of
`plugins/obsidian/scripts/search.py`; the vector half and PDF-chunk support are later
increments, not this release.

## Usage

```bash
farsight query "hybrid retrieval scoring" --vault ./vault --k 10 --json
```

- `--vault <path>` — explicit vault path. Falls back to `TOOLKIT_VAULT`, then `./vault`
  relative to a repo root found by walking up for `.claude-plugin/marketplace.json`
  (mirrors `core/toolkit_core/vault.py::resolve_vault`).
- `--k <N>` — max results (default 10).
- `--json` — emit a JSON array of `{path, score, title, description}`; otherwise prints
  a human-readable table.

`02_Projects/`, `03_Areas/`, and `04_Resources/` are scanned, plus any root-level note whose
own frontmatter declares `status: active` — the active-content filter in
`contract/VAULT_SCHEMA.md`, including its root-level-note clause (e.g. this vault's persona
note, `Alex-Vega.md`). `00_Memory/`, `01_Capture/`, and `05_Archive/` are always excluded, and
`Index.md`/`CLAUDE.md` never qualify since neither carries frontmatter. Frontmatter parsing is
tolerant per the same contract's floor-not-ceiling rule: unknown keys are ignored (never
rejected), and a note with no frontmatter block at all is valid, not an error.

## Scoring

BM25 (`k1=1.5`, `b=0.75`, the same defaults `search.py` uses) over each note's
`title` (from the filename) and frontmatter `description`, each counted twice for extra
weight, plus the first 2000 characters of body — one formula, no separate scoring path,
mirroring `search.py`'s `Doc.text` construction so this is a drop-in replacement rather
than a divergent reimplementation. See `vault/04_Resources/Concepts/BM25-Dilution.md` and
the specimen pair it names for why a condensed `description` field outranks a diluted one
for the same underlying content.

## Why no persisted index

This crate is deliberately **stateless**: every `query` re-scans the vault's
active-content notes from scratch. At vault scale (~100–1500 notes) a per-query scan is
fast, and a stateless design eliminates the entire class of staleness bugs a persisted
index invites (rebuild-timing, partial-write, and cache-invalidation failures) for free.
This is why the dependency list stops at `clap` + `serde`/`serde_json` + `serde_yaml`: no
`tantivy`, no embedding stack, no on-disk index format to version or migrate. The vector
half of "hybrid BM25+vector search" (`docs/PLAN.md`) is deferred to a later increment for
the same reason — it's the piece most likely to need a cache, and it isn't needed yet.

**Removal condition:** add a persisted index when a real vault makes query latency
noticeable. Until then, this is speculative infrastructure this crate deliberately does
not build.

## Testing

`tests/query_test.rs` is the only test file, run against the repo's own `./vault`
(never a user's vault, per `CONTRIBUTING.md`): the planted BM25 specimen pair ranks
correctly, the active-content filter excludes `00_Memory`/`01_Capture`/`05_Archive`, a
no-frontmatter note doesn't crash, and `--json` output parses.
