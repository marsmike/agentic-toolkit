# agentic-toolkit

A vault-first toolkit for Claude Code: a curated set of plugins that share one
knowledge substrate — an Obsidian-compatible markdown vault — governed by an
explicit contract, gated by evals, and continuously delivered.

The repo ships **behavior**; your vault ships **identity**. Nothing personal
lives in this repository.

## Quick start

```bash
git clone https://github.com/marsmike/agentic-toolkit && cd agentic-toolkit
uv run toolkit doctor                 # everything works against ./vault out of the box
claude plugin marketplace add .
claude plugin install obsidian@agentic-toolkit
```

To use your own vault: `export TOOLKIT_VAULT=/path/to/your/vault`, or scaffold a
fresh one with `uv run toolkit vault init ~/my-vault`. Tests and evals always run
against the bundled `./vault`, never yours.

## Layout

- `contract/` — the constitution: vault schema, profile convention, knowledge API, model routing
- `core/` — the `toolkit` CLI and Python library
- `vault/` — the example vault: docs, demo, test corpus, and eval substrate in one
- `plugins/` — curated plugins, added one release at a time
- `crates/` — native engines (Rust), coming in R1+
- `docs/PLAN.md` — why everything is the way it is, with citations

## Principles

Every rule traces to a dated failure. Every plugin declares where its failures
go. Capability evals graduate into regression gates. If a component's behavior
can't be named, it gets removed. See `docs/PLAN.md`.
