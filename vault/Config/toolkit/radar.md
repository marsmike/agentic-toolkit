---
description: Example profile for the radar plugin — demonstrates the fill-from-Obsidian convention documented in contract/PROFILE.md.
kind: profile
status: active
created: 2026-09-23
plugin: radar
interests_note: 03_Areas/Trend Radar Profile.md
promote_location: later
kagi_weekly_budget_usd: 1.00
tags:
  - domain/toolkit-meta
  - profile
---

# radar plugin profile (example)

This is what `$VAULT/Config/toolkit/radar.md` looks like in a real vault. Every field is
optional; see `contract/PROFILE.md` for the resolution order (env var → this note → shipped
default) and the plugin's own `profile.example.md` for every key and what leaves the machine.

- `interests_note` — the note whose frontmatter `interests:` lists `{name, gloss, queries}`.
  This example vault ships none; the radar's evals write their own fixture note.
- `promote_location` — where `scan --promote` moves strong items in Reader.
- `kagi_weekly_budget_usd` — the ceiling `discover` enforces from its spend ledger.

Keys come from the environment or the owner's key file (`~/.env`), each read by the script that
needs it: `READWISE_TOKEN`, `KAGI_API_KEY`, `TOOLKIT_RADAR_JUDGMENT_API_KEY` (or `OPENROUTER_API_KEY`).
