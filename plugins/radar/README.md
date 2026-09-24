# radar plugin

Reads everything Reader aggregates, judges every feed item against your interests with typed
judgments, and puts the result where you already look: a daily note in `00_Memory/radar/`, a
weekly capture in `01_Capture/`, strong items in Reader's Later list. It also says which feeds
earn their place and proposes new ones. The clip stays yours; the pipeline behind it is unchanged.

```mermaid
flowchart LR
  I[interests note<br/>+ Todoist epics] --> J
  R[Reader feed items] --> D[dedupe<br/>URL, title, back catalogue]
  D --> J[Jev: worth_reading<br/>per item x interest]
  J --> P[policy<br/>code owns thresholds]
  P --> M[00_Memory/radar/<br/>daily note + state.jsonl]
  P --> RW[Reader: strong to Later,<br/>the rest archived]
  M --> W[weekly capture<br/>01_Capture/]
  M --> F[feeds / trend]
  K[Kagi + seeds] --> O[discover: OPML<br/>you import]
  O --> R
```

## Commands

`scripts/radar.py` (run with `uv run --project plugins/radar/scripts python3 plugins/radar/scripts/radar.py …`):

| Command | What it does | Network |
|---|---|---|
| `scan --since 1d [--promote] [--keep-in-feed]` | judge new feed items, write the day's note and state, archive what was recorded (strong items to Later with `--promote`) | Reader, judgment backend |
| `weekly [--week YYYY-Www] [--force]` | `01_Capture/Radar-Week-…md`, a draft digest for distill | none |
| `feeds` | per-feed yield; "consider unsubscribing", "serves only <interest>" | none |
| `trend [--week]` | interests rising above their baseline; emerging title terms (experimental) | none |
| `discover [--interest ID] [--seed URL] [--queries N]` | candidate feeds from Kagi, URL shapes, autodiscovery and hnrss, validated and judged, as an OPML | Kagi, Reader (read), the candidate sites, judgment backend |
| `gaps [--promote]` | once a week: recent posts per interest the feeds missed (Kagi news), judged; strong ones in the digest, optionally saved to Later | Kagi, judgment backend, Reader (save) |
| `kagi search\|news\|answer\|summarize TEXT` | the kagi skill: one Kagi call under the ledger and weekly budget | Kagi |
| `replay --since 30d --out DIR` | acceptance: own clips vs. feed items, Jev vs. BM25 vs. recency | Reader (read), judgment backend |

The skill (`skills/radar/`) turns the daily and weekly runs into a short briefing;
`skills/radar/references/scheduling.md` sets them up as scheduled tasks.

## What it measured before shipping

The R10 acceptance run on a real Reader account (30 days, 1,325 feed items plus 24 own clips):

- Same-day AUC of own clips against feed items: **Jev 0.70, BM25 0.57, recency 0.47**. At a
  budget of 20 items a day, 71% of the clips would have been shown (BM25: 50%).
- 1,325 feed items → 194 worth reading, 102 strong (about 4 strong a day), for $0.10.
- A blind audit of 120 stratified items (labelled by a model that never saw p): the strong band
  held at 69%, the 0.60–0.80 band at 23%, which moved `T_WORTH` to 0.70.
- Feed yield: 101 of 102 strong items came from arXiv; three embedded-systems feeds produced none
  in a month. That is what `feeds` and `discover` are for.

## Configuration

`profile.example.md` documents every profile key and exactly what leaves the machine. Keys come
from the environment or the key file `~/.env`, read by each script itself (`READWISE_TOKEN`, `KAGI_API_KEY`, `TOOLKIT_RADAR_JUDGMENT_API_KEY` or
`OPENROUTER_API_KEY`); without one, the command that needs it prints `SKIPPED` and sends nothing.

## Boundaries

- No cross-plugin imports: `judge.py`, `judgments/urls.py` and `judgments/state.py` are
  byte-identical copies of the obsidian plugin's, held together by a parity test in
  `core/tests/test_contract.py`.
- Reader writes go through one guarded `bulk_update`: location (archive, later, shortlist, new),
  tags and notes only. Never a delete, never back into the feed.
- Writes into the vault: `00_Memory/radar/` (scan, discover) and `01_Capture/` (weekly). Nothing
  in `02_`–`04_`.
- Evals (`evals/run.py`): scan, replay, discover and reports, offline with stubbed network, against
  a sandbox copy of `./vault`; registered in CI.

## Not yet

Nothing from the R10 plan is left unbuilt. Since the first release: `gaps` (once a week, Kagi's
recent-posts index per interest, judged; strong finds in the weekly digest and, with `--promote`,
saved to Later within the daily budget), the `kagi` skill (search, news, FastGPT answers, the
Universal Summarizer, one ledger and budget), and `scan --todoist` (one dated comment a day on each
Portfolio epic with strong items, never a new or completed task). Reader has no feed-subscription API, so `discover` ends in an OPML, not a subscription.
