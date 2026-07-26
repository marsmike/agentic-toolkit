---
description: Example profile for the memory plugin — copy the frontmatter shape below into your own vault's Config/toolkit/memory.md.
kind: profile
status: active
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

Copy this file's frontmatter shape to `$VAULT/Config/toolkit/memory.md` to override the plugin's
shipped defaults. Every field below is optional — an absent file, or an absent field within it,
falls back to the plugin's built-in default. See `contract/PROFILE.md` for the full resolution
order (env var → this note → shipped default).

## Fields

- **`min_human_turns_to_archive`** — the SessionEnd hook skips archiving a session with fewer
  human turns than this (default `1`). Raise it to skip trivial one-shot sessions; `0` archives
  every session that produced a transcript at all, including empty ones.
- **`max_transcript_bytes`** — the hook reads at most this many bytes of a transcript before
  summarizing (default `2000000`, ~2MB). Bounds the hook's own runtime against a pathologically
  large transcript; lower it if session-end feels slow on a machine with very long sessions.
- **`default_tags`** — the tag list a new `00_Memory/notes/<slug>.md` gets when `distill-memory`
  doesn't pass an explicit `tags=` override. Defaults to `[agent/memory, domain/toolkit-meta]`.

## Secrets

Nothing here ever carries a credential — this plugin has no external service dependency at all
(no LLM subprocess, no delivery channel). See `contract/PROFILE.md`'s Secrets section regardless,
since a future tunable might.

## Env var overrides

Every field above also has a `TOOLKIT_MEMORY_<FIELD>` environment variable that wins over this
note, per `contract/PROFILE.md`'s resolution order — e.g. `TOOLKIT_MEMORY_MIN_HUMAN_TURNS_TO_ARCHIVE=2`.
List fields (`default_tags`) are comma-separated in the env var form.
