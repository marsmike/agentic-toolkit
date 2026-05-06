# Contributing

Thanks for the interest. Two ways to contribute:

1. **Open an issue** for bugs, requests, or proposals.
2. **Open a PR** — see below.

## DCO sign-off (required)

This project uses the [Developer Certificate of Origin](https://developercertificate.org/) (DCO). Every commit must be signed off:

```bash
git commit -s -m "your message"
```

The `-s` flag adds a `Signed-off-by:` line. By signing off, you certify that you authored the contribution and have the right to submit it under the project's license.

The DCO check on PRs will block merges without sign-off.

## Adding a plugin

A plugin is a directory at the repo root with a `.claude-plugin/plugin.json` manifest. To propose a new plugin:

1. Open an issue describing what the plugin does and why it belongs in this marketplace.
2. After approval, open a PR adding the plugin directory and a `.claude-plugin/marketplace.json` entry.
3. Include a plugin-level `NOTICE.md` listing every third-party dependency and adapted code pattern.
4. Include a plugin-level `README.md` with install and usage examples.

## Code style

- **Python:** `uv` for dependency management; `ruff` for lint and format.
- **Markdown:** front-matter required for skills; descriptions under 100 characters.

## License

Contributions are released under MIT (see [LICENSE](LICENSE)).

## Leak prevention (OSS repo only)

This repo must never receive proprietary internal markers (corporate URLs, kit auth tokens, asset IDs from internal CDN paths). Two local hooks enforce this:

- `.githooks/pre-commit` blocks commits that introduce flagged content.
- `.githooks/pre-push` blocks pushes that would publish flagged content to GitHub.

Activate both with one command after cloning:

```bash
git config core.hooksPath .githooks
```

There is no CI-side scanner: by the time a CI workflow runs, the content is already on GitHub. The hook gate is the only meaningful gate. If a hook trips on a genuine false positive, review the staged diff manually and use `git commit --no-verify` (or `git push --no-verify`) once you are sure.
