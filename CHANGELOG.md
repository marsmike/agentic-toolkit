# Changelog

Every release entry links the change to the research or the dated failure that motivated it — this file is the public ratchet.

## [2.1.0] — R1, farsight

- **crates/farsight** — the first Rust engine: a stateless BM25 search binary (`farsight query "<terms>" [--vault] [--k] [--json]`), CLI-in/JSON-out per `contract/KNOWLEDGE_API.md`. No persisted index — a per-query scan over `02_Projects`/`03_Areas`/`04_Resources` is fast at vault scale (~100–1500 notes) and eliminates staleness by construction; see the crate README for the removal condition. Dependencies stop at `clap` + `serde`/`serde_json` + `serde_yaml` — no `tantivy`, no embedding stack, since the stateless decision rules them out for this release.
- **plugins/obsidian/scripts/search.py** — gains a preference chain: shells out to a `farsight` binary (`TOOLKIT_FARSIGHT_BIN` env var, else PATH) when one is available and returns its results; falls back to the existing Python BM25 path unchanged otherwise (docs/PLAN.md's fallback contract). Scoped and cache-rebuild calls still go through Python only, since farsight doesn't cover those yet.
- **plugins/obsidian/evals/eval_search_parity.py** — checks farsight's top-3 results overlap >=2/3 with the Python implementation's top-3 for 3 fixed queries when a binary is present; reports pass with "farsight not present — python fallback only" when it isn't, since release binaries don't exist yet.
- **Cargo workspace** — `crates/farsight` is the first workspace member; `.github/workflows/release-binaries.yml`'s `farsight-v*` tag path now builds a real crate instead of a not-yet-existing one.
- Version bump to **2.1.0** (marketplace.json, plugins/obsidian/plugin.json) — the obsidian plugin's own behavior changed (search.py's preference chain), so it moves in lock-step per `CONTRIBUTING.md`. `crates/farsight` itself starts independently at 0.1.0 — engine crates version and release on their own tag scheme (`farsight-v*`), not the plugin line.

## [2.0.0] — R0, the walking skeleton

R0 is version **2.0.0** everywhere (marketplace.json, plugin.json, both
pyproject.toml) — the 2.x line marks the vault-first generation; 1.x history
lives in the legacy repo.

- **contract/** — the constitution: vault schema (frontmatter as floor, not ceiling), profile convention ("fill from Obsidian"), knowledge API (filesystem+CLI over MCP indirection), model routing rules, and the `vault init` template.
- **core/** — `toolkit` CLI: `vault init`, `doctor`, `profile`; tolerant frontmatter IO; `TOOLKIT_VAULT` → `./vault` resolution.
- **vault/** — the example vault: documentation written as vault notes, `vault init` template, deterministic test corpus with planted edge cases, and eval substrate.
- **plugins/obsidian** — the reference plugin, curated from v1 (vendored env dropped): vault operations, distill workflow, lint, and the new retrieval-verification skill.
- **CI** — path-filtered checks, contract↔example-vault consistency gate, evals gate, gitleaks, release-binaries skeleton.

Prior history lives in [agentic-toolkit-legacy](https://github.com/marsmike/agentic-toolkit-legacy); this repo starts with fresh history by design (see docs/PLAN.md).
