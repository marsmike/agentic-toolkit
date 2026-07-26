---
description: Plugins get identity and configuration from a note in the vault, never hard-coded in the repo — the repo ships behavior, the vault carries specifics.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-01-22
created: 2026-01-22
kind: concept
topics:
  - profiles
  - vault-architecture
tags:
  - domain/toolkit-meta
---

# Fill-From-Obsidian Profiles

A plugin that needs to know who it's working for — a name, a preferred style, a default score
threshold — reads that from a note in `Config/toolkit/<plugin>.md` rather than from a config value
baked into the plugin's own source. This is [[Vault-First-Architecture]] applied specifically to
identity: the repository is reusable by anyone precisely because it doesn't contain anyone's
specifics.

## Resolution order

Environment variable first (for anything secret or deployment-specific), then the vault profile
note, then the plugin's shipped default. See `contract/PROFILE.md` for the normative version and
[[Config/toolkit/obsidian.md|the worked example]] this vault ships.

## Why secrets are excluded

A profile note may say a credential exists and where to configure it; it never carries the
credential's value. Mixing secrets into vault content would make the vault unsafe to share or
put under version control — see [[Alex-Vega]]'s profile note for what a profile without secrets
actually looks like in practice.

## Related

- [[Vault-First-Architecture]]
- [[Alex-Vega]]
- [[Semantic-Search-Score-Calibration]]
- [[Toolkit-Maintenance]]
- [[Progressive-Disclosure]]
