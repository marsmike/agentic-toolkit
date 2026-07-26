---
description: How a plugin's identity and settings resolve — env var, vault profile note, shipped default — and where to look when a setting isn't behaving as expected.
status: active
created: 2026-02-03
kind: guide
topics:
  - profiles
  - onboarding
tags:
  - domain/toolkit-meta
---

# Profiles and Config

Every plugin that reads configuration follows the same resolution order, normatively documented in
`contract/PROFILE.md` and conceptually in [[Fill-From-Obsidian-Profiles]]: environment variable
first, then `$VAULT/Config/toolkit/<plugin>.md`, then the plugin's shipped default.

## Writing your own profile note

Copy the shape from the plugin's own `profile.example.md` — every profile-reading plugin ships
one — into `Config/toolkit/<plugin>.md` in your vault. [[Config/toolkit/obsidian.md|This vault's
own example]] shows the shape for the obsidian plugin specifically: frontmatter for structured
settings, body prose for rationale a future editor would want.

## Debugging a setting that isn't taking effect

`toolkit doctor` (see [[Toolkit-CLI]]) reports which step of the resolution order supplied each
setting's current value — check that first before assuming a profile note is malformed.

## What never belongs in a profile note

Credentials. An API token, a password, anything secret lives in an environment variable or a
keychain, never in vault content — see the Secrets section of `contract/PROFILE.md`. A profile
note may say a credential exists and name where to configure it; it never carries the value.

## Related

- [[Fill-From-Obsidian-Profiles]]
- [[Config/toolkit/obsidian.md]]
- [[Toolkit-CLI]]
- [[Alex-Vega]]
