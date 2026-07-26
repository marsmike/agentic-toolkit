---
description: Example profile for the handoff plugin — copy the frontmatter shape below into your own vault's Config/toolkit/handoff.md.
kind: profile
status: active
plugin: handoff
autosnapshot: true
index_path: 00_Memory/handoffs/index.md
default_visibility: commit
tags:
  - domain/toolkit-meta
  - profile
---

# handoff plugin profile (example)

Copy this file's frontmatter shape to `$VAULT/Config/toolkit/handoff.md` to override the
plugin's shipped defaults. Every field below is optional — an absent file, or an absent field
within it, falls back to the plugin's built-in default. See `contract/PROFILE.md` for the full
resolution order (env var → this note → shipped default).

## Fields

- **`autosnapshot`** — whether the `PreCompact` hook writes a git-state snapshot to
  `_handoff/.autosnapshot.md` right before context compaction. Defaults to `true`. Set
  `false` to disable the safety net entirely. Accepted spellings (case-insensitive):
  `true`/`yes`/`1`/`on` and `false`/`no`/`0`/`off` — same set for this field and its
  `TOOLKIT_HANDOFF_AUTOSNAPSHOT` env var below.
- **`index_path`** — where the cross-project handoff index lives, relative to the vault
  root. Defaults to `00_Memory/handoffs/index.md`. Change only if you've reorganized
  `00_Memory/`.
- **`default_visibility`** — `commit` or `gitignore`. What the `handoff` skill's save step
  suggests for `_handoff/` at the end of a save: `commit` for team/cross-machine
  continuity, `gitignore` for private, single-machine use. Defaults to `commit`. This is
  only a suggestion the skill (and the script's own printed output) surfaces to you — the
  script never runs `git add` or edits `.gitignore` itself.

## Secrets

Nothing here ever carries a credential — this plugin has no external service dependency
at all (no LLM subprocess, no delivery channel). See `contract/PROFILE.md`'s Secrets
section regardless, since a future tunable might.

## Env var overrides

Every field above also has a `TOOLKIT_HANDOFF_<FIELD>` environment variable that wins over
this note, per `contract/PROFILE.md`'s resolution order — e.g.
`TOOLKIT_HANDOFF_AUTOSNAPSHOT=false`.
