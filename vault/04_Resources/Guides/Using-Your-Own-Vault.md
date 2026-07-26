---
description: Pointing the toolkit at a real personal vault via TOOLKIT_VAULT, and how tests stay isolated from it regardless.
status: active
created: 2026-02-02
kind: guide
topics:
  - onboarding
  - vault-architecture
tags:
  - domain/toolkit-meta
---

# Using Your Own Vault

`./vault` — this example vault — is the default. To point every plugin and CLI command at a real
vault instead, set the `TOOLKIT_VAULT` environment variable to its path. Resolution order:
environment variable first, `./vault` as fallback, documented normatively in
`contract/PROFILE.md`.

## Scaffolding a fresh personal vault

`toolkit vault init /path/to/new` (see [[Toolkit-CLI]]) copies this vault's structure — the PARA
folders, `Templates/`, and a `CLAUDE.md` from `contract/templates/VAULT_CLAUDE.md` — into a new
location, empty of content, ready to start capturing into.

## Tests never touch it

However `TOOLKIT_VAULT` is set in the environment a test or eval runs in, tests and evals always
target `./vault` regardless — see `contract/PROFILE.md`'s Tests and Evals section. A personal
vault reached through `TOOLKIT_VAULT` is never read or written by CI or by a test/eval run, on
purpose: your real notes should never be at risk from running `pytest`.

## Growing past the example

Once pointed at a real vault, growth in structure and content should track actual need — new
captures, new projects, new areas — not an attempt to match this example vault's size or shape.
See [[Vault-Größe-und-Skalierungsschwellen]] for when flat structure stops being enough.

## Related

- [[Toolkit-CLI]]
- [[Quick-Start]]
- [[Profiles-and-Config]]
- [[Vault-Größe-und-Skalierungsschwellen]]
