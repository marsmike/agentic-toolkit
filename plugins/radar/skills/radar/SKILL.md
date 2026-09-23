---
name: radar
description: Run the research radar — the daily scan of Reader feed items judged against your interests, the weekly capture, feed yield and discovery of new feeds — and ask Kagi (search, news, sourced answers, summaries). Use for "what's new in my feeds", a daily or weekly briefing, curating feeds, "search Kagi" or "summarize this link".
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
R gaps [--promote] --json              # weekly: what the feeds missed (Kagi news), judged
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
  `scripts/judgments/questions.py`, changed only through the judgment-calibration loop (`docs/MAINTAINING.md`) and a
  `QUESTIONS_VERSION` bump. Never tune either to make a briefing look better.
- **Advice, not writes.** The radar writes only `00_Memory/radar/` and, via `weekly`,
  `01_Capture/`. Nothing it produces goes into `02_`–`04_` without distill and a human checkpoint.
- **Queries stay local to discovery.** Interest queries go to Kagi and nowhere else; the judgment
  backend sees interest names and glosses only.
- **Measure before changing.** A claim that the radar is better or worse rests on `replay`
  (own clips vs. feed items, same-day AUC against BM25), not on one day's list.

## Kagi: search, news, answers, summaries

The same client serves one-off questions ("search Kagi", "what's new on X", "summarize this
link"), under the radar's spend ledger and weekly budget (`kagi_weekly_budget_usd`, default
$1.00; every call is recorded in `00_Memory/radar/kagi-ledger.jsonl` with its real cost).

```bash
R kagi search "query" --json          # web results                        ~$0.025
R kagi news "query" --json            # recent small-web and news posts     ~$0.002, with dates
R kagi answer "question" --json       # FastGPT: an answer with references  ~$0.015
R kagi summarize "https://…" --json   # page, video, PDF; per 1k tokens, a long page ~$0.30
```

Pick the cheapest mode that answers: `news` for "what happened lately", `answer` when a sourced
paragraph is enough, `search` when you must read the pages, `summarize` only for one long thing
you would otherwise read in full. Cite the references `answer` returns, never the model.
`over-budget` is a stop, not a retry: say what was spent this week. Nothing is written to the
vault; to keep a result, save it in Reader (it becomes a capture) or file an insight with distill.
`SKIPPED` means `KAGI_API_KEY` is not set: say so, stop.

Scheduling (Claude Desktop scheduled task or launchd): `references/scheduling.md`.
