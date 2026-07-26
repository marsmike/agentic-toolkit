---
description: Example profile for the readwise plugin — demonstrates the fill-from-Obsidian convention documented in contract/PROFILE.md.
kind: profile
status: active
created: 2026-07-26
plugin: readwise
enrichers:
  - github
  - youtube
backlog_sweep: true
tags:
  - domain/toolkit-meta
  - profile
---

# readwise plugin profile (example)

This is what `$VAULT/Config/toolkit/readwise.md` looks like in a real vault. Every field is
optional — an absent file or field falls back to the plugin's built-in default; see
`contract/PROFILE.md` for the resolution order (env var → this note → shipped default).

- `enrichers` — which enrichment scripts the enrich skill may invoke for matching captures.
- `backlog_sweep` — whether `daily` also sweeps older unprocessed captures.

The API token is never stored here: `READWISE_TOKEN` is an environment variable, referenced by
name only. The canonical field reference is the plugin's own `profile.example.md` — keep the
shapes identical by hand.

## Related

- [[Fill-From-Obsidian-Profiles]]
- [[Capture-Conventions]]
