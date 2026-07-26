---
description: Verifying the stranger experience end-to-end before every release — a clean clone, released binaries, and an isolated headless session — never assumed from a developer's own configured machine.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-07-26
created: 2026-07-26
kind: concept
topics:
  - reliability
  - onboarding
tags:
  - domain/toolkit-meta
---

# The Cold-Boot Ritual

A developer's own machine is the worst place to verify a fresh clone works: it already has the
right `uv`/`cargo` versions, cached dependencies, an existing `~/.claude` config, and — the
subtlest trap — engine binaries built from source rather than downloaded the way a real user gets
them. `scripts/coldboot.sh` exists to remove all of that: it clones the *published* repo into a
throwaway directory, downloads the *released* farsight/gaiafield binaries from GitHub releases, and
(opt-in, via `--live`) drives a real headless `claude -p` session against an isolated
`CLAUDE_CONFIG_DIR` — never the developer's own vault or config.

## The four stages

1. **Clone + doctor** — the README's quick-start, verbatim, against the real published repo.
2. **Released binaries** — `gh release download` for the platform-matched `farsight`/`gaiafield`
   asset, exactly as a stranger would get them, not a local `cargo build`.
3. **Engine smoke checks** — a real `farsight query` and `gaiafield index` against `./vault`,
   asserting non-trivial output.
4. **Live headless session (`--live` only)** — installs the plugin, runs the `distill` skill's
   phase 1 (analysis only, no writes) inside an isolated `CLAUDE_CONFIG_DIR`, then asserts the
   session touched no tracked file.

## What it actually found

`[earned: cold-boot test 2026-07-26]` — the ritual's first run surfaced three real gaps a
developer's own machine had silently masked: a `uv` workspace-dependency failure in the quick-start
path, missing example profile notes a fresh vault needed, and the headless permission-mode wall
(the default permission mode blocks tool execution, so an unprepared `claude -p` call silently
degrades to filesystem-only analysis instead of exercising the engines at all). See
[[Scripting-the-Toolkit-Headless]] for the exact `--allowedTools` shape that clears the third one.

## Why isolation, not just a fresh directory

The `--live` stage goes further than a temp directory for the code: it also uses a scratch
`CLAUDE_CONFIG_DIR`, copying in only an OAuth credential blob, and unsets `ANTHROPIC_API_KEY`/
`ANTHROPIC_AUTH_TOKEN` so the session can't accidentally inherit the developer's own billing
context or plugin state. A cold-boot check that reused the developer's real config would just be
testing the developer's machine again.

## A sibling ritual: verifying the docs site against reality

Cold-boot verifies the *stranger install* experience; a parallel discipline verifies the *public
docs* experience — checking the live [[Docs-Site]] against what the running system actually does,
the same adversarial way cold-boot checks a clean clone against the published repo. Both exist for
the same reason: a developer's own head is the worst place to notice that a doc drifted from the
system it describes, because the developer already knows what was meant. `scripts/docscheck.sh`
carries the mechanically-catchable slice of that verification — plugin-list drift and the
backtick-in-wikilink-alias class of renderer bug — the same way `scripts/coldboot.sh` carries the
mechanically-catchable slice of the install-experience check.

## Related

- [[The-Ratchet]]
- [[The-Observer-Pattern]]
- [[Scripting-the-Toolkit-Headless]]
- [[Vault-First-Architecture]]
- [[Docs-Site]]
- [[Quick-Start]]
- [[Capability-Probing]]
