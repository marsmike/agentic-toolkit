---
description: Orientation protocol for this vault's agent self-memory — operational state, not vault content.
status: active
created: 2026-01-12
tags:
  - domain/toolkit-meta
---

# Agent Memory — Orientation

This folder is the agent's own operational memory, not vault knowledge. Nothing here is distilled
into, enriched from, or linked to by an active note — see `contract/VAULT_SCHEMA.md`. If you are
an agent starting a session against this vault, read this file first; it is the whole protocol,
not a pointer to a longer one.

## Layout

- `journal/<YYYY-MM-DD>.md` — append-only, one file per day. Never rewrite a past entry.
- `dlq/` — dead-letter entries: automations that couldn't confidently resolve something on their
  own and left a record instead of guessing. See `dlq/2026-07-22-stale-search-index.md` for the
  worked example.

## Journal format

```
- [HH:MM] <project-or-plugin> | <one-line summary>
  - learned: ...
  - friction: ...
  - decided: ...
```

Omit any of `learned` / `friction` / `decided` that has nothing to say for that entry. This is
deliberately terser than a distilled note — it is a trace for the next session, not reference
material for a human.

## Why this folder is excluded from everything

Search, enrichment, and the generated index all operate on `02_Projects`, `03_Areas`, and
`04_Resources` only. Memory is operational state about *this vault's agent*, not knowledge *about
the world the agent operates in* — mixing the two would make memory entries show up in unrelated
searches and would make vault knowledge depend on session-specific noise. No note outside this
folder should ever link in here.
