# Contributing

Thanks for the interest. Two ways to contribute:

1. **Open an issue** for bugs, requests, or proposals.
2. **Open a PR** — see below.

## DCO sign-off (required)

This project uses the [Developer Certificate of Origin](https://developercertificate.org/) (DCO). Every commit must be signed off:

```bash
git commit -s -m "your message"
```

By signing off, you certify that you authored the contribution and have the right to submit it under the project's license.

## The rules of this repo

- **Everything runs against `./vault`** — the bundled example vault is template, docs, test corpus, and eval substrate in one. Tests and evals never touch a user's vault.
- **Plugins depend on `core/` and `contract/` only, never on a sibling plugin.** Cross-plugin behavior composes through vault notes.
- **Evals gate merges.** A plugin change ships with its capability/regression evals green (`plugins/<name>/evals/`). New capabilities start with a low-pass-rate eval and graduate into the regression suite.
- **Every normative rule carries provenance.** Rules in `contract/` and CLAUDE.md cite the dated failure that earned them and name a removal condition. Don't add speculative constraints.
- **A schema change updates the example vault in the same PR** — CI enforces it.

## Adding a plugin

1. Open an issue describing the behavior it delivers (if you can't name the behavior, it doesn't get in).
2. After approval: PR with the plugin directory, a `marketplace.json` entry (version in lock-step with `plugin.json`), a README, evals, and a stated answer to the dead-letter question — *when this plugin's automation fails, where does the failure go?*

## Code style

- **Python:** `uv` for everything; `ruff` for lint/format. Small perfect code — no speculative abstractions.
- **Rust (`crates/`):** engines are CLI-in/JSON-out binaries; no linking into Python.
- **Skills:** SKILL.md stays lean (when-to-use + workflow + hard requirements); depth lives in `references/`, which only loads on invocation.

## License

Contributions are released under MIT (see [LICENSE](LICENSE)).
