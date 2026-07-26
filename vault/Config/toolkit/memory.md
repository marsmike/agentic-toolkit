---
description: Example profile for the memory plugin — demonstrates the fill-from-Obsidian convention documented in contract/PROFILE.md.
kind: profile
status: active
created: 2026-07-26
plugin: memory
min_human_turns_to_archive: 1
max_transcript_bytes: 2000000
default_tags:
  - agent/memory
  - domain/toolkit-meta
tags:
  - domain/toolkit-meta
  - profile
---

# memory plugin profile (example)

This is what `$VAULT/Config/toolkit/memory.md` looks like in a real vault. Every field is
optional — an absent file or field falls back to the plugin's built-in default; see
`contract/PROFILE.md` for the resolution order (env var → this note → shipped default).

- `min_human_turns_to_archive` — sessions with fewer human turns are skipped by the
  session-capture hook.
- `max_transcript_bytes` — byte cap the hook reads from a transcript (enforced, not advisory).
- `default_tags` — tags stamped on generated session notes.

The canonical field reference is the plugin's own `profile.example.md` — keep the shapes
identical by hand.

## Related

- [[Fill-From-Obsidian-Profiles]]
