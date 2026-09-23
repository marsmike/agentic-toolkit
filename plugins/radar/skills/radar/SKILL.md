---
name: radar
description: Run the research radar — the daily scan of Reader feed items judged against your interests, the weekly capture, feed yield and discovery of new feeds. Use for "what's new in my feeds", a daily or weekly briefing, or when feeds need curating.
allowed-tools:
  - Bash
  - Read
---

# Radar

Reader aggregates everything you subscribe to; the radar reads all of it so you do not have to.
Each feed item is judged per interest (`worth_reading`, a probability) and per kind, code applies
the thresholds, and the result lands where you already look. You run the commands and brief the
human; you never clip, and you never write active content.

```bash
R() { uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/radar.py" "$@"; }
R scan --since 1d [--promote] --json   # daily: judge, write 00_Memory/radar/, settle items in Reader
R weekly                              # Saturday: 01_Capture/Radar-Week-YYYY-Www.md for distill
R feeds --json                        # which feeds earn their place
R trend --json                        # which interests are rising this week
R discover [--interest ID] [--seed URL]   # new feeds via Kagi, as an OPML to import in Reader
```

**Daily.** Run `scan`, read `00_Memory/radar/<today>.md`, and reply with a five-line briefing:
what is strong (title, feed, the interest it serves), what is rising (from `trend`), and what is
already in the vault (`already in vault:`). Link the items; do not summarise articles you have
not read. `SKIPPED` means a key is missing: say which, stop.

**Weekly.** Run `weekly`, then hand the capture to `obsidian:distill` like any other capture. Add
the `feeds` advice to the briefing: a feed with "consider unsubscribing" is a decision for the
human, never for you.

**Curating.** `discover` writes an OPML with the reason on every feed. Reader has no subscription
API: the human imports it (or subscribes feed by feed), after reading the list.

## Hard requirements

- **Reader is only ever moved, never emptied.** `scan` archives what it has recorded and, with
  `--promote`, moves strong items to Later with `radar` tags. Never call a delete, never move an
  item back into the feed, and never run `--promote` unless the human asked for it.
- **Thresholds are code.** `scripts/judgments/policy.py` owns every number; question wording is
  `scripts/judgments/questions.py`, changed only through the `judgment-calibration` loop and a
  `QUESTIONS_VERSION` bump. Never tune either to make a briefing look better.
- **Advice, not writes.** The radar writes only `00_Memory/radar/` and, via `weekly`,
  `01_Capture/`. Nothing it produces goes into `02_`–`04_` without distill and a human checkpoint.
- **Queries stay local to discovery.** Interest queries go to Kagi and nowhere else; the judgment
  backend sees interest names and glosses only.
- **Measure before changing.** A claim that the radar is better or worse rests on `replay`
  (own clips vs. feed items, same-day AUC against BM25), not on one day's list.

Scheduling (Claude Desktop scheduled task or launchd): `references/scheduling.md`.
