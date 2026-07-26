# crates

**farsight** (R1) — stateless BM25 search over a vault's active-content notes; see
`crates/farsight/README.md` for usage, the BM25 formula, and why it deliberately carries
no persisted index. **gaiafield** (knowledge graph over the vault's wikilinks) is next.
Engines are CLI-in/JSON-out binaries; see `docs/PLAN.md` (Engines) and
`contract/KNOWLEDGE_API.md` for the interface they must implement.
