# Changelog

Every release entry links the change to the research or the dated failure that motivated it — this file is the public ratchet.

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
