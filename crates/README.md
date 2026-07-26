# crates

**farsight** (R1) — stateless BM25 search over a vault's active-content notes; see
`crates/farsight/README.md` for usage, the BM25 formula, and why it deliberately carries
no persisted index.

**gaiafield** (R2) — deterministic knowledge-graph extraction over a vault's wikilinks into
SQLite (`index`/`neighbors`/`stats`/`path`); see `crates/gaiafield/README.md` for node scope,
edge resolution rules, and incremental indexing. v1 is deterministic-only — no inferred edge, no
model call. Inferred/similarity edges above a calibrated threshold, confidence-labeled
EXTRACTED/INFERRED/AMBIGUOUS, are **R3**, not yet built.

Engines are CLI-in/JSON-out binaries; see `docs/PLAN.md` (Engines) and
`contract/KNOWLEDGE_API.md` for the interface they must implement.
