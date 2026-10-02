# Changelog

Every release entry links the change to the research or the dated failure that motivated it — this file is the public ratchet.

## [Unreleased] — R12, enriched tweets and a dashboard

- **The run report no longer promotes more than it judged (obsidian 3.9.4).** "What the feeds
  brought today" read "7 items judged, 2 strong, 12 promoted into Reader" on 2026-10-02: the judged
  and strong counts are the feed judge's for today, the promoted count is every row of
  `promoted.jsonl` dated today, five of them the Signal Radar's sensor news and some feed items
  judged on an earlier day. The sentence now says "feed items judged" and names the sensor share;
  `radar_ledger.load` returns `promoted_today_sensors`.

- **The Atlas's flow fits a phone (obsidian 3.9.3).** "From source to topic" drew at least 760 px
  and scrolled sideways, so at 390 px (the Atlas is mostly opened on a phone) the domains it ends in
  were off-screen (2026-10-02 screenshot). Under 640 px the Sankey now draws at the card's width,
  labels sit inside the columns (sources right of their bar, outcomes and domains left), the domain
  column folds after five, and a lane under 4 % carries its count in the legend instead of a label.
  Desktop is unchanged.

- **Emptying the inbox keeps the inbox (obsidian 3.9.2).** Git keeps no empty directory: on
  2026-10-01 the 15:58 UTC run retired the only capture, the Mac's sync pulled it and removed
  `01_Capture/`, and the folder vanished from Obsidian, where the Capture template writes. `end` now
  keeps a hidden `01_Capture/.gitkeep` (created when missing, committed with the run); the pipeline
  eval's phase 2 checks it is tracked. contract/VAULT_SCHEMA.md says so.

- **A description over 250 characters is a soft finding of the check (obsidian 3.9.1).** A note's
  `description` is its one line in Index.md and its map (contract/VAULT_SCHEMA.md: "one-sentence
  purpose"). Since the pipeline moved to the cloud on 2026-09-23 the median grew from ~160 to ~440
  characters — still one sentence, held together by semicolons — 32 of the 34 notes distilled on
  2026-10-01 were over 320, and Index.md reached 452 KB. `distill_check.py` now reports
  `soft.description` (characters, the limit, the fix) and the skill says what a description is;
  like every soft finding it is answered, never a failed gate, so no unattended run can stall on it.

- **The Signal Radar's name check no longer counts namesakes from before it added context (radar
  3.10.3).** check_candidates learned on 2026-10-01 to ask a one-word name with disambiguating
  context, but the rows asked bare before that stayed evidence for their whole week, and a name asked
  in the last week is not asked again: "jeff" (the Jev-compatible decision models, one real Hacker
  News post) stayed HOT at 70 on an obituary, a TV host and a governor from the 09-30 row. A row now
  records its `context`; a one-word name's row without that record is ignored, so the name is asked
  again with context. The Reddit fallback through Tavily also strips old.reddit's " : <sub>" title
  suffix, not only " : r/<sub>": "r/ClaudeAI List of Ongoing Megathreads : ClaudeAI" had made
  ClaudeAI a blip.

- **The Atlas shows what each interest brought, and the strongest items (obsidian 3.9.0).** The
  Dashboard's "Strong per week" and "Top feed items" had no counterpart in the Atlas, so the one page
  meant to show the whole way in left out what the radar's interests yield. Two full-width panels
  under the funnel now do: per interest, nested bars of worth reading or better, strong and promoted
  in the page's range (the funnel's colour steps), the strong count, and strong per week for the
  ledger's last 8 weeks (each item counted once for every interest it is strong for, like the bars);
  and the range's 10 highest-scored items with interest, feed, day and whether they were promoted,
  linked only when the address is a web one. The data (`radar_view`) keeps the 10 best a day for the
  last week and the 3 best a day before it; a retired interest has no row. The atlas eval's phase 5
  covers aliases, the retired row, the older days' cut and a `javascript:` address.

- **An unusable Readwise cursor falls back to the window (readwise 3.1.6).** Only ingest writes
  `lastSyncedAt`, but on 2026-10-01 a stale Obsidian Sync merge wrote `'2026-110-01T13:00…'`, which
  `_utc` raises on: the next ingest would have failed before fetching anything. A cursor that is no
  timestamp, or lies in the future, now counts as none: the run fetches the four-week window (the
  ledger keeps anything from coming in twice), writes one `readwise-cursor-…` DLQ note (none in a dry
  run) and rewrites the cursor when it ends cleanly. The ingest eval's phase 6 covers both cases.
- **Index rebuilds are logged only when notes came or went (obsidian 3.8.1).** A pipeline run
  rebuilds Index.md three or four times, and the identical "Index.md rebuilt" lines were 324 of
  Log.md's 873. The line now carries `+added -dropped` and is written only when either is non-zero.

- **The Mac's sync never pushes a stale copy (obsidian 3.8.0).** Obsidian Sync merges files too,
  and on 2026-10-01 it merged older copies into the Mac's vault when Obsidian started: Signal-Radar.md
  went back to the 08:30 run, Log.md gained 59 repeated lines from the day before, a note lost the 24
  lines the 07:10 run had added, and `readwise-state.md` got `lastSyncedAt: '2026-110-01T13:00…'`,
  which the next ingest would have read. The 13:32 UTC sync committed and pushed all four as hand
  edits (undone in the vault by b222403). `sync` now puts back to HEAD any local change to what the
  cloud routines own (`CLOUD_OWNED`: Log.md, `00_Memory/radar/`, the pipeline and Readwise ledgers and
  state, beside the generated navigation), and holds a change to any other file that is byte for byte
  an earlier version of it or only drops lines a pipeline run added in the last 24 hours: not
  committed, left in the working copy, one `sync-held-…` DLQ note and one notification, never
  reverted, since deleting exactly what a run added looks the same. A deletion is always the
  owner's. Excluded paths are now literal pathspecs (vault paths hold brackets and spaces).
  [earned: 2026-10-01, the 13:32 UTC sync commit 8114a63]

- **A feed that answers in gzip unasked still parses (radar 3.10.2).** deepmind.google's blog feed
  began answering `text/xml` with a gzip body, and the 11:28 UTC Signal Radar run read it as "not
  XML: not well-formed (invalid token): line 1, column 0" (rss: partial). `sensors._request` now
  inflates a body that starts with the gzip magic bytes (capped at `MAX_BYTES`) and passes any
  other body through. [earned: 2026-10-01]

- **Reader's "Unnamed Document" is no title (readwise 3.1.5).** Reader names a page it could not
  title "Unnamed Document" rather than leaving the title empty, so the radar-headline fallback (3.1.3)
  never ran: three radar promotions in a week reached the ledger, the run report and the Atlas as
  "Unnamed Document" while `promoted.jsonl` held their headlines. Reader's placeholder names
  (`PLACEHOLDER_TITLES`) now count as no title. [earned: 2026-10-01, the 10:10 UTC run]

- **CI green again: the Atlas finds the routines snapshot without a fixed path depth (obsidian
  3.7.7).** `atlas_build.py` set `ROUTINES = Path(__file__).resolve().parents[3] / …` at import. CI's
  `pipeline_run` eval runs the generators from `/tmp/<dir>/`, where on Linux `parents[3]` does not
  exist: `IndexError: 3`, reported as a second `build_failed` beside the eval's own failing
  `map_build`, and the evals job failed on every push from 3.7.1 (bcfd60a) to 3.7.6. macOS resolves
  `/tmp` to `/private/tmp`, one level deeper, so the local runs passed. `routines_file()` now looks
  upwards for `cloud/routines.json` and finds none outside a checkout. The same class of bug was
  earned once before (vault_utils.py, 2026-09-28). [earned: 2026-10-01, CI run 36822324842]

- **The Atlas opens on now on a phone (obsidian 3.7.6).** The routines chart and the topic map are
  drawn at their true size and scroll sideways on a narrow screen; the chart now opens on its right
  end (now) instead of the range's first day, with its row labels in a column that stays put, and
  the map opens on its middle.

- **A blind spot is the owner's business (radar 3.10.1).** Any blip at strength 30 that no note
  anchored was a blind spot, so world news the sensors carried ("Delhi", "Netherlands", "Ukraine",
  "Pac-Man", "White House") stood beside Anthropic IPO on Now.md and in the morning push ("Not in
  your vault: … Delhi"). A blind spot now also needs a sector (an interest the judge tied it to) or,
  unsectored, relevance of at least 0.6 (`BLIND_SPOT_OTHER_RELEVANCE`, `blind_spot()`). On the
  2026-10-01 data: 28 blind spots → about 17, Anthropic IPO and Windows 11 kept, the world news gone;
  hexstrike-ai (0.50) goes too, a known borderline. [earned: 2026-10-01]

- **The run report links the Atlas and the Signal Radar, and counts kinds as the maps group them
  (obsidian 3.7.5).** The three published pages did not point at each other; the report's header now
  links the Atlas and the Signal Radar once their URLs are set. Its Kinds panel counted 89 raw kind
  values and 157 "unsorted" project and area notes, which need no kind; `map_build.kind_families`
  and `kind_family` now give the report and the Atlas one grouping, the `Config/toolkit/maps.md`
  sections (Research 353, Concepts 282, Tools 230 on the owner's vault), with "project notes" and
  "area notes" for the rest. [earned: 2026-10-01 quality audit]

- **A fragment folds into its qualified name instead of a generic word absorbing whatever shares
  its ending, and a bare word names nothing on its own (radar 3.10.0).** `merge_variants` merged
  key `k` into `base` on pure string containment — `base` a prefix or suffix of `k`, `base`'s
  mentions `>=` `k`'s — with no check the two were actually about the same thing, and direction
  fixed to the *shorter* string, so a fragment could never fold into a longer, more-mentioned
  qualified name. It now merges a candidate pair only on evidence of relatedness: either the
  longer key is exactly the shorter plus a trailing version number (`entities._spans` only ever
  attaches one there, so that shape is never a coincidence), or the qualifier the longer name
  adds over the shorter appears as a whole word in the shorter entity's own mention titles — and
  the more-mentioned of the two, not the shorter string, is what the merged thing is called.
  `entities.py` separately stopped manufacturing the fragments in the first place: `_name_like`
  treated any capitalised non-first word not in `GENERIC`/`FILLER` as a name, so a bare common
  noun ("Machines", "Scope", "Sift") or a demonym ("Chinese", "Korean", "American", …, `PLACES`
  had the countries but not their adjectives) became its own entity, and `_OWNER` stripped
  `owner/`-style prefixes from prose generally, so Reddit's `r/ClaudeAI` became entity "ClaudeAI".
  `BRANDS` gained the observed common nouns (excluded only as a standalone span, never trimmed out
  of a real compound like "Dental Scope"), `FILLER` gained a `DEMONYMS` set, and a new
  `_REDDIT_REF` pattern drops a subreddit or redditor reference whole before `_OWNER` ever sees
  it. On the Signal Radar generated 2026-10-01 04:15 UTC (60 blips): Machines, Scope, Sift,
  Chinese and ClaudeAI were junk blips in their own right, "Scope" had absorbed the unrelated HN
  launch Dental Scope and "Machines" the unrelated GitHub repo sleeping_machines, while Muse (12
  mentions), Sol (2), Astra and Gemini 4 (3) sat beside their qualified names (Meta Muse 65,
  GPT-6.1 Sol 8, GPT-6.1 Astra, Gemini 4 Argon 11) instead of folding into them.
  [earned: 2026-10-01, Signal Radar 2026-10-01 04:15 UTC: jeff (HOT, 70), Machines, Scope, Sift,
  Chinese, ClaudeAI as blips; Muse/Sol/Astra/Gemini 4 beside their qualified names]

- **An Other-sector bare word an interest stands behind is checked with that interest as context
  (radar 3.10.0).** `check_candidates` added a one-word name's sector as web-check
  context only when the sector was not `None`/`"other"` — the function's own comment already
  documented why that is backwards: an unsectored name is often exactly what the web check exists
  to corroborate or dismiss, and a bare ambiguous name needs disambiguating context *more*, not
  less, for having none. "jeff" judged 0.87 on Small Decision Models & Typed Judgments from one
  real mention never earned a sector (`assign_sectors` wants a second mention or a name match,
  neither of which one mention gives it), so it was asked bare and five unrelated people named
  Jeff came back as a second, third, fourth, fifth and sixth source — strength 70, stage HOT.
  `check_candidates` now also checks an Other-sector name when its single best-scoring judged
  interest cleared `_interest_weights`' own 0.5 bar, and asks it with that interest as context; an
  Other-sector name with no judged interest at all ("Delhi", "Netherlands") still gets no check,
  as the 2026-09-30 budget rule wanted. [earned: 2026-10-01, Signal Radar 2026-10-01 04:15 UTC:
  jeff, HOT, strength 70, one real mention plus five unrelated Tavily namesakes]
- **The Atlas opens its landscape with a topic map (obsidian 3.7.4).** Domains are the large nodes
  (size: notes), each domain's leading topic tags orbit it, and a tag that several domains share sits
  between them, so the map shows which topics bridge which domains; the domains whose notes link
  most are joined by lines. A tag with notes added in the chosen range is filled, a quiet one hollow;
  picking a domain lights its topics and links. The layout is a deterministic force simulation in
  the page (no library), fitted to the canvas, with labels placed where they cover nothing.

- **A tweet's title keeps its leading link text (readwise 3.1.4).** Reader titles a tweet with its
  first words but drops a leading link, so the ClaudeDevs post "Claude.dev is our new home for
  developers building with Claude" became a capture, a ledger row and a run-report item titled "is
  our new home…". `write_capture` takes the dropped words back from the tweet's own first line when
  Reader's title sits inside it a few words in; any other title stays Reader's. [earned:
  2026-10-01, the 04:05 UTC run's report]

- **The Mac's sync leaves generated navigation to the run (obsidian 3.7.3).** A local change to a
  generated file (a plugin rewriting the Kanban board, a stray edit to Now.md) was committed as a
  hand edit; meeting the cloud run's rebuild of the same file in the rebase, it would stop the sync
  with a conflict until someone resolved it by hand. `sync` now puts tracked generated files
  (`GENERATORS`, but not the daily notes, whose text outside the block is the owner's) back to HEAD
  before it commits; the next run rebuilds them anyway. The log line names what it left to the run.
  [earned: 2026-10-01 review of the sync job]

- **The Atlas names a domain's kinds as its map groups them (obsidian 3.7.2).** 89 kind values
  (`research` 213 beside `research-finding` 137, `tool-landmark` beside `tool`) made each domain's
  kind chips a list of near-synonyms, and 157 project and area notes, which need no kind, read
  "unsorted". A kind now shows as the `Config/toolkit/maps.md` section that names it (Research,
  Tools, Concepts, Guides and references, …), and a project or area note without one as "project
  notes" or "area notes". [earned: 2026-10-01 quality audit]

- **The Atlas draws the machine and its plan (obsidian 3.7.1).** A "How the machine runs" diagram
  takes the sources, the three cloud routines (each with its schedule and model from
  `cloud/routines.json`, its last run and its next one in the viewer's time), the vault on GitHub and
  the owner's devices (the Mac sync, Obsidian). The routines chart now draws the planned runs:
  ahead of now (today's range) as hollow rings, and a planned pipeline or radar run with no result
  from 15 minutes before to 75 minutes after as a red ring, counted only from a routine's first run
  in the data. `#today`, `#7d`, `#30d` and `#12w` open the page on that range.

- **The Atlas: what the vault knows and how knowledge comes in, on one page (obsidian 3.7.0).**
  `atlas_build.py` writes `Atlas.html` at the end of every run (a generator in `end`, restored
  like the others if it fails), and the routine publishes it to `atlas_artifact_url`. One range
  (today, 7 / 30 days, 12 weeks) scopes both halves. *Inflow*: every imported item flows from its
  source (an own save, a radar feed pick, sensor news, a gap search, a newsletter) through what it
  became (a new note, an enriched one, dropped, waiting) to the domains it fed; the radar's funnel
  (judged, worth reading, strong, promoted); the routines' runs on one time axis (the pipeline's
  from the ledger, the Signal Radar's and the Mac sync's from their commits, pauses over 4.5 h
  marked); and the median time from ingest to note. *Landscape*: a treemap of every active note by
  domain, colored by what the range added; each domain's most-linked and newest notes, kinds and
  topic tags; the topic tags on the move; a matrix of the links between domains; twelve weeks of
  growth per domain. An item whose fate names no note (manifest prose from before the ledger
  carried notes: 151 of 342) takes the notes that cite its source, so the flow reaches its
  domains. Now.md and the dashboard link the page. Owner's goal for 2026-10-01: "visualized the
  topics and process very good"; Now.md, the dashboard and the run report each showed one slice.
- **What's moving lists a renamed interest once (obsidian 3.7.0).** `radar_ledger.canon()` kept an
  alias's own slug, so rows scored before a rename and after it landed under two ids with one
  name: "Local AI & Self-Hosted Inference" showed 122/70/32 and 42/18/3, and three other renamed
  interests likewise. An alias now counts under the interest's current id. `radar_ledger.load`
  also returns its counts per day (`days`), the Atlas's funnel.
- **An enrichment shows when it enriched (obsidian 3.7.0).** The run report and Imports.md printed
  an enriched note's own `distilled_at`, the day it was first written: "ingested 2026-10-01 03:59
  UTC · distilled 2026-09-30 19:10 UTC". A fate now carries `retired_at` from its `retired` row,
  and an enrichment shows "enriched <retired_at>". [earned: 2026-10-01, review of the day's runs]
||||||| parent of 5d5b696 (radar 3.10.0: a fragment folds into its qualified name, not whatever shares its ending; Other gets web-check context too)

- **The Mac syncs the vault itself while the pipeline runs in the cloud (obsidian 3.6.0).**
  `pipeline_run.py sync` commits hand edits through the pipeline's secret scan, pulls the
  upstream (`--rebase`; a conflict is aborted with a DLQ note) and pushes, under the run lock.
  `scripts/vault-sync.sh` runs it from launchd every 10 minutes, with Obsidian open or closed. It
  logs one line a run and sends a macOS notification only for a conflict, a refused key or an hour
  of failures. Git authenticates with `GH_TOKEN` from `~/.env` through a helper that answers only
  from that variable: every configured helper is reset first, so an unattended run never reaches
  the Keychain. On 2026-10-01 nothing on the Mac pulled the cloud's commits. Obsidian Git's
  intervals were never set and Obsidian was closed. The vault, and the devices Obsidian Sync
  feeds from it, lagged the cloud until a session pulled by hand (the 01:08 and 04:05 UTC runs
  arrived at 06:13 local), and hand edits reached GitHub only when a session committed them.
  Also: `_push` carries a pull's `conflict` and `secrets` to its caller (`commit_paths`' retry
  loop checked `conflict`, which never arrived), and `new_commits` counts the upstream's commits,
  not a rebased hand edit. `cloud/README.md` and `references/scheduling.md` describe the job.
  [earned: 2026-10-01, the day's monitoring of the cloud routines]

- **A note that only got a backlink is retired with `--linked`, never given the capture's source
  (obsidian 3.5.3).** The distill skill said to name every changed note with `retire_capture.py
  --note` (since 3.4.0), and `--note` holds each note to `distill_check`, whose source-line gate
  refuses a note that does not cite the capture. A note with only an L1 backlink never does. Two
  cloud runs on 2026-10-01 worked around it in two ways. The 01:08 UTC run added the capture as a
  "(Related link)" Source line and `sources:` entry on notes it had only linked to; seven notes
  carry such lines (the 2026-09-29 19:03 run made three), and the Bubbles briefing's "→ note" for
  the Dirk-Qwen item pointed at the Swift 1.5 note. The 04:05 UTC run left its backlinked notes
  out of the ledger instead. `--linked <note>` now takes such a note. It must sit in 02–04 and
  link to a `--note`. It gets `updated_at` alone (it was changed, not distilled) and its own
  `linked` list in the ledger row. The skill says which flag takes which note, and never to add
  the capture's source to a note that only links to it.
  [earned: 2026-10-01, review of the day's cloud runs]

- **Gap promotions go through the scan's allocation (radar 3.9.0).** `gaps --promote` saved its
  strongest items by probability alone, up to `promote_per_run` (25 on the owner's profile): no
  bubble weights, no credit charged, no per-source, per-name or per-event cap, and nothing held.
  `scan --promote` has allocated sensors and feed together since 3.8.0. Gaps now builds the same
  allocation (`radar.allocation_context`: the profile's budget and caps, the Signal Radar's events,
  the watched names, the weights, this run's credit and today's promotions) and walks the same
  `Selector`, and its promotions are charged to their bubbles' credit in `allocation.json`. What
  gets no slot waits in `promote_hold.jsonl` as a `gap` row that keeps its interests' p. The next
  scans offer it again beside the sensors and the feed (`gaps_promoted` in the scan's result), and
  after `HOLD_DAYS` it is missed like any held item. A Google News link from Kagi is resolved like
  a sensor's.
  [earned: 2026-10-01, review: the weekly run (Saturdays) could put a whole run's budget into one
  bubble or one site]

- **Every promotion records the address it was saved under, and the briefing links that (radar
  3.9.0).** `promoted.jsonl` rows carried only the canonical key, which is lower-cased, so the
  Bubbles briefing linked `https://` plus the key. The Reuters story on TradingView
  (`newsml_L6N45M1EL`) became a 404, and 46 of the 120 promotions of 2026-09-30 and 2026-10-01 had
  capitals in their path. Google News ids, LessWrong and TradingView break on that; Reddit and
  GitHub forgive it. Feed, sensor and gap rows now carry `url`. An older row takes the address as a
  note or capture wrote it (`briefing.note_index(vault, urls)`), and only then the key.
  [earned: 2026-10-01, review of the day's briefing]

- **The dossier reads the whole capture, not its first heading (obsidian 3.5.2).** The content check
  (`content_match`) judged the text from `## Full Text` up to the next heading of any level, so an
  article with its own headings ended at its first one. A GitHub README that opens with `## guardrails`
  was "empty", which made it a stub without a model call. An Ollama model page ended at `## Models`
  after six words, and the model rightly called that too little. Of the 328 captures archived in
  September 2026, 42 (13%, mostly READMEs) reached the check with under 300 characters where they held
  1,000 or more. The text now runs to the writer's own trailing sections (`## Linked`, `## My notes`,
  `## Processing Notes`, highlights).
  [earned: 2026-09-30, two false "stub" dossiers in one run; distill caught both by reading the text]

- **The briefing links what distill just wrote (radar 3.8.1, obsidian 3.5.1).** The scan writes
  `Bubbles-<day>.md` before distill, so a promoted item's "→ note" waited a whole run: Gemini 4
  Argon was distilled at 20:46 on 2026-09-30 and the daily note still had no link to it. The new
  `radar.py briefing` command rebuilds it, and `pipeline_run.py end` runs it (a sibling's entry point as
  a subprocess, skipped when the radar plugin is absent) before the daily note is built.
  [earned: 2026-09-30, first live run of radar 3.8.0]

- **An untitled radar promotion takes the radar's headline (readwise 3.1.3).** Reader leaves a
  paywalled or consent-walled page untitled, and each one became a "missing title" DLQ note (three
  on 2026-09-30: FT, Yahoo Finance, InnovationAus), all for items the radar had promoted under a
  known headline. Ingest now takes the title from `00_Memory/radar/promoted.jsonl` (the row with that
  document id); an untitled item the radar never saw still gets its DLQ note.
  [earned: 2026-09-30, the watchdog's "2 new DLQ note(s)" on the first live run of radar 3.8.0]

- **A weighted selection of the owner's bubbles, with nothing important missed (radar 3.8.0,
  obsidian 3.5.0, readwise 3.1.2).** On 2026-09-30, Music Production got 23 promotions while Local AI
  (27 strong items) and AI Agents (23) got one each, and one story took 14 of a run. Promotion now
  runs through one allocator for sensors and the feed together (`allocation.py`, `bubbles.py`):
  - **Must-see lane:** a Signal Radar early warning, or an event at strength 75+ from 3+ source
    families, and the labs' own posts go first (up to half the run), whatever the quotas say.
  - **One event, one promotion:** an event is a Signal Radar entity first seen in the last ten days,
    in one of the owner's sectors, and not a term his interests already use. All coverage of it is
    one story. Its best copy is promoted (lab post, then feed, then open outlet, paywall last); the
    others ride along in the Reader note as "also covered by". At most 3 a day
    (`promote_per_event_per_day`).
  - **Weighted bubbles:** a bubble's weight is `sqrt(1 + notes) + sqrt(1 + notes this month)` from the
    vault, ×1.5 while rising, overridable per bubble (`bubble_weights`). Each run adds
    `budget × weight share` of credit and each promotion costs one; credit carries across runs and is
    halved at a new day. A bubble with nothing yet today goes first; one more than a promotion past
    its share waits.
  - **Per-source cap per bubble:** 3 per bubble, 6 across bubbles. arXiv and reddit carry several
    bubbles, and a shared cap held back the heaviest ones.
  - **Nothing silently lost:** strong items not taken are held. A feed item stays in Reader and is
    offered first for 3 days (`promote_hold.jsonl`); what never makes it goes to `missed.jsonl`.
  - **The day in the vault:** each scan writes `00_Memory/radar/Bubbles-<day>.md`, bubbles heaviest
    first with ★ must-see, ⏳ held, ✗ missed and → the note an item became; the daily note copies it
    in (headings down, no link into `00_Memory`). Items merged into a note's `sources` link to that
    note; the archive is never linked.
  - **Local loop:** `TOOLKIT_READER_SHADOW=<file>` logs every Reader write instead of sending it, and
    `scripts/local-loop.sh` runs scan and a dry ingest on a vault clone in seconds.
    `run-pipeline.sh` now takes claude's login only from `~/.env` and refuses to fall back to the
    Keychain.

  Replaying 2026-09-30 in 8 runs with the vault's real weights: Local AI 11 and AI Agents 11 (they
  had 1 each), Claude Code 7, every must-see event in, 58 promotions against the real 98, and 9
  items held at day's end. The replay also showed Obsidian & Agentic KM, the owner's second-heaviest
  bubble, with no strong feed item at all: a feed gap, not an allocation gap.
  [earned: 2026-09-30, the owner: "I do not want to miss anything important, but need a weighted
  selection of what happened in my bubbles"]

- **Even ingest: every interest gets a turn, no source takes the run (radar 3.7.0, obsidian
  3.4.6).** The per-name caps of 3.6.2 handled one symptom. The general problem: the sensors took
  their promotions before the Reader feed got any (42 to 8 of the day's 50), one Google News
  search held 155 of the day's sensor items, and both paths took candidates strongest first, so
  one busy topic could fill a run. Now:
  - the sensors are offered `promote_sensor_share` (0.5) of the run first, the feed gets the rest,
    and what the feed leaves goes back to the sensors;
  - both paths take interests round-robin (`fairness.interleave`: each interest's strongest item,
    then each interest's second, and so on), with the labs' own announcements still first among
    the sensors;
  - one source (a Reader feed, a Google News search, Hacker News, a lab's own blog) takes at most
    `promote_per_source_per_run` (3) of a run. A held-back sensor item stays in the three-day window
    and goes first next run.

  Replayed on 2026-09-30's sensor data, two runs of 13 cover 7 interests and 11 origins. Before,
  OpenAI's blog took 6 of 13 and all 14 Muse stories went in one run.
  [earned: 2026-09-30, the owner: "it is a general topic. We need to ingest sources evenly"]

- **One story cannot fill a run (radar 3.6.2; profile keys in 3.6.3).** In the first run on radar 3.6.1, 14 of the 20
  promotions were Meta Muse coverage from 14 outlets. Their headlines were worded too differently
  for the title-overlap check, and distill merges them into one note anyway. A watched name now
  takes at most `SENSOR_PER_NAME_PER_RUN` (2) of a run's sensor promotions and
  `SENSOR_PER_NAME_PER_DAY` (6) of a day, counted from today's ledger. Held-back items are counted
  as `sensors_capped`. A lab's own announcement always goes through but counts toward its name. A
  watched name followed by a hyphen and a letter no longer matches: "Meta-Instrument" took one of
  Meta's slots in the replay. Replayed on 2026-09-30's sensor data, one run of 25 is now 10 lab
  posts, 1 momentum item, 9 watched and 5 strong, across Sonnet 5.5, Dots, Nvidia, Jeff and the
  music plugins, with 60 items held back.
  Both limits are profile keys since 3.6.3: `promote_per_name_per_run` and
  `promote_per_name_per_day`.
  [earned: 2026-09-30, 19:11 run; the owner: "all from Muse is not ok"]

- **Google News links become the publisher's URL (radar 3.6.1); a same-named capture no longer
  fails retirement (obsidian 3.4.5).** On 2026-09-30, 210 of the day's 989 sensor items were
  `news.google.com/rss/articles/…` links, from the Google News search feeds and from Kagi News.
  Reader cannot follow one: it saved a document with no title or text, ingest wrote a capture
  named "Google News" plus a DLQ note, and the day's second one had the same filename as the
  first, which was already archived. That made `retire_capture` refuse it, so the capture failed
  and stayed in the inbox. The sensors now resolve such a link before saving (`gnews.py`: an
  old-format id carries the URL; a current one is resolved through the article page's signature
  and `batchexecute`). A link that cannot be resolved is not saved and is counted as
  `sensors_unresolved`. The ledger row records the Google link, so a later run skips it without
  resolving it again. `retire_capture` now tells the same capture retired twice (still refused)
  from another capture that only shares its name (a different `readwise_doc_id` or `source`),
  which is archived beside it as `<stem>-2--FULLCAPTURE.md`.
  [earned: 2026-09-30, the watchdog reported "1 failed" and two DLQ notes on the first run with
  25 promotions]

- **The promotion budget is per run, not per day (radar 3.6.0, obsidian 3.4.4).** On 2026-09-30
  the day's 50 promotions were used up by 07:11 UTC, most of them in one early-morning burst of lab
  news. The three pipeline runs after that judged 60 feed items and promoted none. Each item that
  went over the cap was archived, not kept for the next day. The profile key is now
  `promote_per_run` (default 5). It limits one `scan --promote` or one `gaps --promote`: sensor
  items go first and the feed's strong items get what is left. Earlier promotions that day no
  longer count, and `SENSOR_PROMOTE_PER_DAY` is gone. **Breaking:** rename `promote_per_day` in
  your radar profile; the old key is no longer read.
  [earned: 2026-09-30, the owner saw no new notes after 09:11 CEST despite a full day of feeds]

- **The Signal Radar note holds the whole radar.** The Obsidian note showed 8 of 12 early warnings,
  8 of 22 blind spots and 15 of 60 signals. Everything else, including each signal's items and the
  interest trend, was only on the HTML page and the claude.ai artifact. The note now lists every
  early warning and blind spot, puts every signal in one table, and adds the interest trend, the
  sources and a detail section per signal: its score parts, every item with origin, date and
  score, the vault notes that hold it, and the hubs it connects to. Tags and growing hubs stay
  capped at 8, as on the page.
  [earned: 2026-09-30, the owner asked for the radar in the vault, not only online]

- **Lab news is distilled first; open outlets beat paywalls (obsidian 3.4.3, radar 3.5.1).** The
  first pipeline run on radar 3.5.0 promoted DevDay, GPT-6.1 Sol and Dots, and merged a Sonnet 5.5
  news copy into its note. But it distilled 11 music-plugin and tool captures while those three
  waited, because a day's radar captures tied on a bare `saved_at` date and went by file name. The
  queue now orders them as the radar promoted them (`promoted.jsonl` row by `readwise_doc_id`), so
  lab announcements come first. Both FT stories were dropped as paywalled while NPR had the Astra
  story whole, so a paywalled outlet now loses a tie to an open one. The sensors' `radar/sensors`
  tag also no longer shows up as an interest named "sensors" in `radar_interests`.
  [earned: 2026-09-30, first pipeline run after radar 3.5.0]

- **News copies merge into one note (obsidian 3.4.2).** Now that the radar promotes sensor news, one
  launch arrives as the lab's page, an HN link and several outlets. Distill merges them without
  asking: one note per event, sourced from the primary source, and every other report is an L1
  enrichment (its source line plus what it adds). It looks for the event itself before writing,
  because the dossier's `covers` question asks about the same work or product and may miss another
  outlet's report of the same event. A later event involving the same product is still a new note.
  The `covers` wording is unchanged until it can be calibrated.
  [earned: 2026-09-30, the owner asked that distillation merge the copies automatically]

- **Sensor news becomes captures; the labs are watched by name (radar 3.5.0).** OpenAI DevDay
  2026 and GPT-6.1 Sol never reached the vault. The Signal Radar had both for two days: OpenAI's own
  Sol post at 805 Hacker News points, the DevDay recap, and FT and NPR on GPT-6.1 Astra being
  shelved. But only Reader feed items could be promoted, and the feeds carry no lab. Now `scan
  --promote` also saves sensor items (Hacker News, Kagi News, sensor RSS) to Later, at most 50 a
  day inside `promote_per_day`: a lab's own announcement page whatever its title scored ("DevDay
  2026 Recap": 0.31), 300+ HN points at worth-reading, a title naming a lab or model on the new
  profile `watch` list at worth-reading, or strong. It never saves anything already promoted or in
  the vault, or a second outlet's copy of a story it just saved. Run against that day's sensor
  files, it saves the recap, the Sol post, OpenAI's Dots announcement and the Astra story. The
  Signal Radar's six daily Tavily checks no longer go to names that belong to no interest ("jeff",
  "Delhi" and "Netherlands" took three on 2026-09-30, and their hits then counted as a second source
  for "jeff"). Watched names are checked first, and a one-word name is asked with its interest
  beside it. New eval `sensor_promote`.
  [earned: 2026-09-30, the owner found DevDay missing from the vault]

- **Agents are pointed at `unisphere` (obsidian 3.4.1).** The CLI was on PATH, but no agent-facing
  file named it: the vault template, the `vault` skill and TheVoid's own `AGENTS.md` sent agents to
  `search.py` only, and the link graph had no command an agent could run. Now the `vault` skill and
  the `VAULT_AGENTS.md` template use `unisphere graph neighbors|path|candidates` and `unisphere
  search` when `command -v unisphere` finds it, and fall back to `search.py` and `grep` when it
  does not (cloud runs). Following Claude Code's advice to name the CLI and let the agent learn
  the rest from `--help`, they list a few commands and point to `unisphere commands --json`
  instead of copying the catalogue. The help examples use `<note>` and `<from> <to>` in place of
  the example vault's `Gaiafield` and `Alex-Vega`, which failed on any other vault.
  [earned: 2026-09-29, the owner asked whether agents used unisphere; none were told it existed]

- **One ledger, one definition per number, no count from git history (obsidian 3.4.0, radar 3.4.1).**
  The same week showed 52, 192 and 290 new notes on different pages: the cloud checkout of TheVoid
  can be shallow, and `Now.md`, the Dashboard (17 runs of 59) and the daily notes counted from
  `git log`. Now `00_Memory/imports.jsonl` is the one ledger: a run row per run (counts, UTC time,
  `shallow`) and a retired row per capture (`kind` new, enriched, dropped or duplicate, `notes`,
  `reason`, `what`), pruned to a twelve-week window at `end`. Run counts, `Imports.md`, the daily
  note, the report and the watchdog read it; "distilled" is one rule (`vault_utils.distilled_when`:
  distilled, real date, never estimated) so the per-day chart says 17, not 92, for 2026-09-26.
  `Now.md` shows health (`watchdog.health()`), the last run's receipt with the reason for every
  drop, and new topics. The run report says why an item was dropped and where its numbers come
  from. Pipeline, Signal Radar and watchdog prompts fetch the full history first, and `end` says
  when it is still truncated. `map_build` writes canvases exactly as Obsidian saves them, so
  opening the vault no longer leaves thousands of changed lines behind (a cause of "Pull
  failed"). Radar: the blind-spot count is the true total, and "rising in your vault" needs a real
  baseline (it read "baseline 0.0" for every tag) and says "no baseline yet" until it has one.
  [earned: 2026-09-29, the owner could not trust or reconcile the pipeline's numbers]

- **A homepage you can read in five seconds, a "recently changed" list, the Signal Radar inside
  the vault, and a note per day (obsidian 3.3.0, radar 3.4.0).** `Now.md` was 126 lines of link
  lists with the live views at the bottom; now it opens with one status line (last run, stuck,
  inbox, the radar's early warnings as of their own time), then `Recently changed` and
  `Recently distilled` from `Vault.base`, and folds the long lists away (`> [!tip]-`).
  `updated_at` (ISO 8601 UTC, like `distilled_at`) is stamped in code by `retire_capture.py` on
  every note a capture produced or enriched, and by `end`'s safety net on any changed note it
  missed; `Recently changed` sorts on `updated_at`, then `distilled_at`, then `processed_date`,
  so nothing is backfilled and a git pull cannot fake it the way `file.mtime` does. The Signal
  Radar note embeds two SVGs (`Signal-Radar-scope.svg`, `Signal-Radar-momentum.svg`) drawn from
  `signal.json`, so Obsidian shows what the browser page shows. `daily_build.py` writes one note
  per UTC day in `00_Daily/` (the folder Daily notes and Calendar already point at), owning only
  its marked block. `_owned` no longer treats a not-yet-existing generator folder as a file to
  restore. [earned: 2026-09-29 — the owner could not tell what was going on from Now.md, and its
  "recently distilled" view sat under 75 lines of lists]

- **Battle-tested against the real vault, Reader, Kagi, Tavily and the cloud runs (obsidian 3.2.1,
  radar 3.3.1, readwise 3.1.1, gaiafield 0.2.6).** Each feature of the week ran on live data in a
  scratch copy; what broke is fixed with a test:
  - readwise: file names X links as domains (`train.py`, `program.md`) no longer land in a tweet
    capture's `links:`, while real sites on `.sh`, `.rs`, `.pl` and `.cc` still do.
  - obsidian: Now's "Enriched this week" no longer drops a note added and enriched the same week;
    the run report shows one line per item, "ingested … UTC · distilled … UTC", and the notes'
    real titles (dots kept); the dashboard shows UTC dates in English, "1 capture", GitHub
    releases with their repo name, and interests renamed in the profile under their new names
    (`aliases:` in the interests note), with truly retired ones last in one dimmed row.
  - radar: the Signal Radar's labels and dots keep clear of each other and of the ring labels,
    long item titles wrap, a name found once in one feed no longer claims that feed's sector,
    early warning shows only real signals, times are UTC; the weekly digest, trend and feeds
    count a renamed interest's history under its new name.
  - unisphere and gaiafield: status shows the routines' true UTC times; ASCII, colour and width
    settings reach status, doctor and link; errors name the subcommand and never show Python or
    Rust internals; `link` re-runs report "unchanged"; negative `--limit`/`--depth` are refused;
    gaiafield's `candidates`/`surprise` text output reads as text.
  [earned: 2026-09-28 — the owner's goal: every feature of the week battle-tested and working]

- **Every capture and note carries when it came in and when it was distilled (obsidian 3.2.0,
  readwise 3.1.0, radar 3.3.0).** Two contract fields, `ingested_at` and `distilled_at` (ISO 8601
  UTC, `2026-09-28T18:59:34Z`): every capture writer stamps `ingested_at`; `retire_capture.py`
  stamps `distilled_at` and carries the capture's `ingested_at` into the note, with a safety net
  in the pipeline's `end`, so neither depends on the model. The run report, Imports, Now, the
  dashboard, the Log, the radar's daily, weekly and scout notes, the Signal Radar and the
  watchdog digest show when they were generated and, per item, when it was ingested and
  distilled; a date without a known time is shown as estimated, never given one. Log.md times
  are UTC now. `backfill_timestamps.py` proposes both fields for older notes from git history,
  marked `*_estimated`, and writes only with `--apply`. The docs site wears the brand palette,
  fonts, a starfield in dark mode and the brand icon.
  [earned: 2026-09-28 — the owner asked for the ingest and distill date and time on every report
  and note]

- **unisphere explains itself, and the project wears its theme.** Help in the manner of gh,
  kubectl and brew: bare `unisphere` shows commands grouped by task, global flags, examples,
  the environment it reads and where to learn more; every command has a description, flags with
  defaults, examples, its JSON shape and related commands; `unisphere help <command>`,
  `--version`/`version`, and "Did you mean this?" for typos, with a one-line usage error in place
  of argparse's dump. One table drives the help and `commands --json` (which gains `examples` and
  `group`), and a test keeps any command from shipping without them. Colour, emoji and clickable
  links follow the terminal (`term.py`); pipes, `--json` and `NO_COLOR` get plain text. On a
  terminal, bare `unisphere` opens with a line from the vault's own numbers, and `status` lists
  the cloud routines as U-SHADOWS. The brand is a quiet nod to Peter F. Hamilton's Commonwealth
  (`docs/BRAND.md`): new banners and a social card drawn from the real vault graph (notes as
  worlds, links as wormholes, clusters as star systems, generated by `assets/build_banner.py`), a
  glossary in the README, command names and data output left plain.
  [earned: 2026-09-28 — the owner asked for help like gh/kubectl/brew and made the Hamilton
  homage the project's theme]

- **Fixes from the review of the week's 88 commits (obsidian 3.1.1, radar 3.2.1, readwise 3.0.1,
  gaiafield 0.2.5).**
  - gaiafield: `infer` writes in one transaction like `index`, so parallel distill workers can no
    longer duplicate or wipe each other's inferred edges; both scan the vault and encode before
    taking the write lock, which now covers only the database diff (tested with 12 indexers).
  - The secret scan catches `DB_PASSWORD=`, `userPassword:`, unquoted passwords and credentials
    inside URLs, and still lets placeholders (`<pw>`, `${VAR}`, `***`) through. A second refused
    commit on the same day no longer re-finds an older DLQ note.
  - radar: a truncated ledger line, a read timeout from Reader or Kagi, or a non-numeric profile
    value no longer crashes a run; a failed promotion is retried from `promote_retry.jsonl` even
    after it leaves the `--since` window and archived after three failures; the Signal Radar's
    Reddit fallback writes its own ledger and records each call's yield; the name check asks
    Tavily's news topic first; `gaps-<week>.json`, replay and discover write atomically.
  - `fetch_source.py` keeps a Tavily ledger (`00_Memory/tavily-extract-ledger.jsonl`) under the
    weekly budget, and retries an empty extraction once at advanced depth.
  - readwise: a short highlight counts as captured only in its own document's notes (a vault-wide
    match needs ≥ 80 characters or 12 words); `?s=`/`?t=` are stripped only on X/Twitter links.
  - `unisphere`: `vault init` and `link` answer filesystem errors with the JSON error shape; a
    toolkit checkout behind its upstream makes `status` unhealthy. DLQ notes are dated in UTC.
  [earned: 2026-09-28 week review]

- **The Tavily CLI is the one way to Tavily (radar 3.2.0, obsidian 3.1.0).** Every use goes through
  `tvly` (tavily-cli, pinned 0.1.8), locally and in the cloud routines, with the key read by the
  script and handed to `tvly` alone:
  - Reddit refuses cloud addresses, so the cloud radar never saw a thread: when the listing is
    blocked, `sensors` asks Tavily for each subreddit's day (`r/<sub>` over reddit.com, basic
    depth), without scores, each subreddit at most every 12 hours.
  - `signal --check` (was `--kagi`) searches the week's web for the newest names through Tavily,
    Kagi news only when Tavily cannot run; answers already on record from either count for a week.
  - distill fetches a stub's source with `fetch_source.py`, which reads the URL from the capture
    itself and keeps to the unattended run's domain allow-list (a direct `tvly extract` grant
    would have bypassed it).
  - A weekly budget, `tavily_weekly_budget_usd` (default 2.00), over two ledgers as for Kagi; the
    default use fits the free 1,000 credits a month. `unisphere status` checks `tvly`, and the
    catalogue lists it as a companion. Measured live: 15 fresh r/LocalLLaMA threads for 1 credit.
  [earned: 2026-09-28 — the owner chose the Tavily CLI as the uniform way to use Tavily]

- **obsidian 3.0.3, radar 3.1.2:** their scripts' hints name `unisphere engines install`, so an
  installed plugin never points at the removed `toolkit` command. [earned: 2026-09-28, the rename]

- **The CLI is `unisphere` now, one front door for people and for agents.** Named for the
  Commonwealth's unisphere, next to farsight and gaiafield; the `toolkit` command is gone (the Python
  package stays `toolkit_core`, and the cloud setup calls `python -m toolkit_core.cli`, which works
  in every tag). `unisphere link` removes the `toolkit` entry an earlier link wrote. `status` answers "is
  everything current and healthy?" in one panel: engines against their latest release and the
  cloud pin, every Claude Code plugin install against this checkout's version (outdated and
  orphaned installs named, with the command that fixes them), the vault, its graph and open DLQ
  entries, the pipeline's watchdog verdict, and the companion CLIs (Obsidian's, Todoist's `td`).
  `search` and `graph stats|neighbors|path|candidates` put farsight and gaiafield
  behind readable output; a note that does not exist answers with the notes a search finds.
  `unisphere commands --json` is the catalogue agents start from, derived from the parser so it
  cannot drift; `unisphere link` puts `unisphere`, the engines and Obsidian's CLI on `~/.local/bin`.
  Text is coloured only on a TTY and honours NO_COLOR; every command takes `--json`. `doctor` and
  `status` count only open DLQ entries (resolved ones stay listed in the total).
  [earned: 2026-09-28 — checking that the latest versions were active took a dozen commands across
  three tools, `gaiafield` was "command not found" in the owner's shell, and doctor reported five
  DLQ entries when all five were resolved]

- **Links in the published pages open outside the artifact frame (obsidian 3.0.2, radar 3.1.1).**
  claude.ai renders an artifact in a frame, and a link without a target navigated the frame: GitHub,
  X and Reddit refuse to be framed and obsidian:// cannot open there, so the click showed "This
  content is blocked". The run report, the dashboard and Signal Radar carry `<base target="_blank">`;
  in-page links (blip names) keep working, they cancel the navigation. The report and signal evals
  fail without it. [earned: 2026-09-28, the owner clicking links in the published run report]

- **gaiafield 0.2.4: parallel indexers wait for each other.** The pipeline distills in parallel
  workers, and each one's `distill_check` runs `gaiafield index` on the same `graph.db`; SQLite had
  no busy timeout, so the second writer failed at once with "database is locked" and filed a DLQ
  note. `open_db` now waits up to 30 s, and one index pass is one `BEGIN IMMEDIATE` transaction,
  so two passes queue instead of interleaving their per-note delete/insert pairs (which would
  duplicate edges). `concurrent_indexers_serialize_on_one_database` runs six indexers at once and
  fails on 0.2.3; the cloud setup pins gaiafield-v0.2.4. [earned: 2026-09-28, the 09:58 pipeline
  run — three distill workers, `2026-09-28-gaiafield-index-failed` in the DLQ]

- **gaiafield 0.2.3 and the obsidian plugin read links written inside tables.** In a Markdown
  table a wikilink is `[[target\|alias]]` (Obsidian's escape for the pipe); gaiafield and six
  Python readers (vault_lint, map_build, distill_check, imports_log, judgments/capture) took the
  target with the backslash, so the link never matched its note: dangling edges in the graph,
  false orphans in the lint, lost edges in the maps. `checks/links.py` alone had been fixed, on
  2026-09-22. On the owner's vault 0.2.3 resolves 101 more links (dangling 1,580 → 1,479).
  `core/tests/test_wikilinks.py` covers every reader, the gaiafield test the crate; the cloud
  setup pins gaiafield-v0.2.3. [earned: 2026-09-28, a double-check of the portfolio commit —
  106 table links in 15 notes, 13 of them in the generated Maps/Overview]

- **Signal Radar: one article through two pipes is one source.** An item that arrives through Reader
  and through the RSS, GitHub or Reddit sensor (the same publisher feed, twice) is one mention: the
  sensor's row with its score, the judge's relevance from Reader's. Hacker News, Hugging Face and
  Kagi News linking the same article still count as their own attention. [earned: 2026-09-27, the
  owner imported the radar's music feeds into Reader — each music article would have scored two
  families of breadth]

- **Signal Radar: less noise from the music feeds.** Google News titles lose their "- Outlet" suffix
  (outlets had become signals: "Gearnews.com", "MusicRadar"); deal words ("Save 50%") and country
  names never make a name on their own; "NI Maschine 3.7" is Maschine. A Kagi News category missing
  from the day's index is a quiet day, not a partial source. [earned: 2026-09-27, the first run with
  the owner's music feeds]

- **Signal Radar: clicking a blip opens its details.** The SVG helper set `onclick` with
  `setAttribute`, which turns a function into inline code that only evaluates the arrow function
  (and which the artifact's CSP blocks anyway): blips did nothing on click or Enter, in the vault
  and in the artifact. Handlers are now listeners, as in the HTML helper; checked in headless
  Chrome (click and keyboard). The detail panel no longer overflows with long titles, and "new"
  counts only anchored notes created this week. [earned: 2026-09-27, owner — "clicking on the radar
  blips does nothing"]

- **No file with two writers across the two routines.** The pipeline (`gaps`, and `discover`/`scout`
  by hand) and the Signal Radar (its Kagi check) both appended to `kagi-ledger.jsonl`, and both push
  TheVoid: two appends conflict in `pull --rebase`, and a pipeline run whose push fails loses its
  notes with the session. The Signal Radar now writes `kagi-ledger-signal.jsonl`; `kagi.ledger()`
  budgets over both files, so the weekly cap still covers every call (a soft cap: at most one
  run's calls over). The routine commits an explicit list of its own files; `commit` skips a named
  file not written yet, and on a key-shaped string commits the DLQ note alone so the diagnostic is
  not lost with the session. `cloud/README.md` lists which routine writes which file. [earned: 2026-09-27, owner's question about the routines' dependencies]

- **The watchdog also guards the Signal Radar routine.** Once the vault has a `signal radar …`
  commit, one older than four hours is a `signal-stale` problem (one push, like the pipeline's
  `stale`); `facts` carry its last summary and age. A vault without the routine is never alarmed.
  [earned: 2026-09-27, health check after the routine went live — nothing would have noticed it stop]

- **Kagi News as a Signal Radar source** (`sensors`: `kagi_news`). Kagi's news product clusters
  each day's stories by event and counts the independent domains carrying each: that count is the
  cluster's score, so breadth arrives measured. Free JSON at news.kagi.com (no key, nothing against
  the Kagi API budget); categories by name, profile `sensor_kagi_news` (default AI, Technology,
  Linux & OSS, Music Technology, Science); one row per story across categories. First real run: 36
  stories; TypeSafe's Jev gained a fourth family, AutoTune Advanced its second. [earned:
  2026-09-27, owner — "Kagi can also provide information about trending things"]
- **GitHub Trending when the cloud proxy refuses api.github.com.** In a Claude cloud session every
  `api.github.com` path outside the attached repositories answers 403 "sessions are bound to their
  configured repositories", token or not, so no `GITHUB_TOKEN` can help there. The sensor now
  recognises that refusal, skips the anonymous retry and reads GitHub Trending (daily, all
  languages and Python) from an RSS mirror on github.io, scored by rank. [earned: 2026-09-27, the
  Signal Radar routine's 11:28 run after #57 named the proxy]
- **The GitHub sensor survives a token GitHub refuses.** A 401/403 with a token on the first query
  is retried once anonymously, and every refusal keeps GitHub's own message in the detail instead
  of a bare "rate limited". [earned: 2026-09-27, the Signal Radar routine's first run — the cloud
  session's `GH_TOKEN` is set, yet search answered 403; a real `GITHUB_TOKEN` takes precedence]

- **The Signal Radar runs as a routine of its own** (`cloud/signal.prompt.md`, every three hours
  at :28, Sonnet 5): sensors, signal with the Kagi check, a commit of `00_Memory/radar/` only, the
  page republished, and one morning push with the early warnings, hot signals and blind spots. The
  pipeline routine no longer runs `sensors` and `signal`. New `pipeline_run.py commit --path P
  --message M`: commits only the named vault paths with `end`'s secret scan, rebases over what the
  pipeline pushed meanwhile (`--autostash`, never sweeping other changes in) and retries the push;
  eval phase 7. [earned: 2026-09-27, owner's request — a dedicated routine in the GenAI News
  environment; the first cloud runs showed GitHub rate-limited from the shared address, hence the
  optional `GITHUB_TOKEN`]

- **Signal Radar: what is taking off, not only what is relevant** (radar 3.1.0). `radar.py
  sensors` pulls sources that carry engagement and that Reader does not have — Hacker News
  (Algolia), Hugging Face trending models and spaces, new GitHub repos by stars, Reddit with
  upvotes, plain RSS (audio plugins and model news by default) — and judges what is new like a
  feed item. `radar.py signal` joins them with the judged feed, the owner's own notes and clips
  (`vault_pulse.py`) and his knowledge graph (`vault_graph.py`, gaiafield: the notes of any date a
  thing is anchored in, their linked neighbourhood, the hubs it connects to, and the hubs this
  week's notes are thickening) into named things (`entities.py`: `Qwen 3.8`, `Qwen3.8-27B` and
  `unsloth/Qwen3.8-GGUF` are one) with a 0–100 strength from breadth, velocity, engagement,
  relevance, volume and graph anchoring; `--kagi` corroborates at most six new names a day with
  Kagi news. It writes `00_Memory/radar/Signal-Radar.html` (a radar scope, early warnings, blind
  spots, the vault's rising tags and growing hubs, every note an `obsidian://` link),
  `Signal-Radar.md` (wikilinks) and `signal.json`; the cloud run republishes the page to
  `signal_artifact_url`. [earned: 2026-09-26, owner's request — "one thing I can check and see
  early what is trending, be it a new local LLM, a new Claude Code feature or a new VST plugin";
  the scan scored relevance only, 45 % of its items were arXiv and nothing carried engagement]

- **`cloud/` holds the whole cloud routine**: the two prompts as files the routines point at
  (`pipeline.prompt.md`, `watchdog.prompt.md`), the environment's setup script as a script
  (`setup.sh`, pasted into the environment), the routines' settings (`routines.json`) and the
  README; `docs/cloud-routine.md` is a stub that points there. The setup script now also fetches
  gaiafield's model into the cached data directory and the prompt's SETUP exports
  `TOOLKIT_GAIAFIELD_MODEL_DIR` to it. [earned: 2026-09-26, owner's request — the script lived
  only inside a Markdown code block and on claude.ai]

- **gaiafield 0.2.2** trusts the OS certificate store for the model download (`ureq`
  `native-certs`), and `fetch-model --dir` downloads and verifies the model without a vault.
  [earned: 2026-09-26 — in the cloud environment `infer` failed with "invalid peer certificate:
  UnknownIssuer" behind the proxy CA the machine trusts; the dossier lost its graph and the
  watchdog pushed]

- **One DLQ note per failure and day.** `write_dlq_note` returns the existing note when the same
  slug already reports the same "What happened" today, instead of `-2`, `-3` copies. [earned:
  2026-09-26 — two identical `gaiafield-infer-failed` notes from one run]

- **Cloud routine SETUP puts the vault checkout on `main` deterministically** (`checkout -B main
  origin/main` after a fetch). Every run so far arrived on a detached HEAD and the model repaired
  it by hand, judging each time whether commits would be lost. [earned: 2026-09-26 — the run's
  own report called it "more git than the rules allow"]

- **The cloud routine installs the engines.** SETUP runs `toolkit engines install` after the
  checkout, so search.py uses farsight and the distill dossier has gaiafield's graph context and
  inferred candidates in the cloud too; FINISH names the versions. [earned: 2026-09-26 — every
  cloud run so far had searched with the BM25 fallback and distilled without a graph]

- **gaiafield 0.2.1** — the fixes that sat unreleased since 0.2.0: `.md` symlinks out of the vault
  are not nodes, loops and dangling targets skipped (#28); a duplicate bare wikilink resolves to
  the linking note's own folder, links re-resolve when the target's scope changes, nanosecond
  mtimes, AMBIGUOUS edges kept out of `neighbors`/`path` (#26); model2vec-rs 0.3.0. New:
  `infer --high-gate/--low-gate`, so a `calibrate` result becomes the obsidian profile's
  `graph_high_gate`/`graph_low_gate` instead of a rebuild. Releases carry `.sha256` sidecars;
  farsight 0.1.2 and gaiafield 0.2.0 got theirs uploaded by hand and now install verified.
  [earned: 2026-09-25 engine check on The Void — the gates were compile-time constants, and
  calibrate on nine of the vault's own clusters suggests 0.59/0.53 against an intra-cluster mean of
  0.695: on this vault the English-only static model, not the gate, is the limit]

- **What's moving.** The dashboard gets a "What's moving" section from the radar's ledgers (per
  interest: worth / strong / promoted for the selected range, rising markers, strong items per
  ISO week stacked by top interest, the top feed items with their fate: promoted, in vault, or
  strong-but-not-promoted); the run report gets "What the feeds brought today"; the watchdog's
  `facts.week` carries seven days of numbers and the Sunday evening check sends them as a digest.
  All from `radar_ledger.py`, a reader of the cross-plugin ledgers. [earned: 2026-09-25, owner's
  request — "I need to see what is moving out there"; the radar's daily note sat unseen in 00_Memory]

- **`promote_per_day` is a radar profile key** (default 5, the old constant). The judgment
  thresholds stay policy in code; how many strong items a day may enter Reader is the owner's
  appetite. [earned: 2026-09-25 — 93 items rated strong in a week, the fixed cap of five let
  ~35 through and silently discarded the rest]

- **A watchdog for the pipeline** (`watchdog.py`, and a second routine documented in
  `docs/cloud-routine.md`): from the vault alone it tells a healthy pipeline from a stale, hung,
  failing, parked, backlogged one or a fresh DLQ note, and the routine notifies only then.
  [earned: 2026-09-25, owner's request — the pipeline routine cannot report a run that never ran]

- **Images that git will not carry are never lost silently.** `end` checks every `media:` file the
  run's captures name: one git ignores, or one not on disk, gets a DLQ note and a count in the
  run summary. [earned: 2026-09-25 — 111 of 130 recovered tweet screenshots never reached git:
  `*.JPG` in the vault's .gitignore also matched `.jpg` on a case-insensitive checkout]

- **The last run's ingestion report, as a Claude artifact** (`report_build.py`, a generator in
  `end`): every import with its source, expanded links and images, what it became (the note on
  GitHub and in Obsidian, found by source when the manifest names it in prose), and the notes the
  run wrote; a quiet run shows the last run that imported. The routine republishes it to the
  profile's `report_artifact_url` after every successful run (REPORT step; `Artifact` joins the
  routine's tools), and the dashboard links it. [earned: 2026-09-25, owner's request]

- **The owner's Reader highlights reach the vault** (`ingest.ingest_highlights`): every highlight
  and note not in the ledger, whatever its age, lands in a highlights capture per document that
  names where the document went; text already in the vault is recorded, not captured; highlights
  are never archived in Reader. Distill merges them as the owner's own words. [earned:
  2026-09-25 correction run — ingest skipped every child of a document: 101 of 123 highlights,
  back to 2023, were only in Reader]
- **Enrichment skips file names X linked as domains** (`CLAUDE.md`, `judge.sh`). [earned:
  2026-09-25 correction run]

- **Every clipping stays in the vault.** Nothing is deleted any more: `retire_capture.py
  --duplicate-of` archives a duplicate whole (distill invariant 6), and a tweet's images are
  stored under `04_Resources/Attachments/Tweets/` (1200 px) and embedded by vault path, with the
  original link beside each. [earned: 2026-09-25, owner's request — errors lose data]
- **`Imports.md`** (`imports_log.py`): what each run imported and what became of every item,
  runs as date-time sections, newest first, in one file; a clipping in neither inbox nor archive
  is called out as missing. The dashboard's runs open to the same list and link to it.
  [earned: 2026-09-25 — its first build found four captures archived by hand with no manifest line]

- **Settled clippings are archived in Reader** (`ingest.archive_settled`, run by `ingest.py`):
  once a capture is retired to `05_Archive/` in the upstream branch (so the run after the one
  that distilled it) or was found already in the vault, its Reader item and its copies move to
  Archive, once, logged in `00_Memory/readwise-archived.jsonl`. No upstream, no archiving; never
  a delete. [earned: 2026-09-25, owner's request — archive the clippings once they are
  definitely in the vault]

- **Tweets are enriched at ingest** (`plugins/readwise/scripts/tweet_enrich.py`): `t.co` links are
  expanded in place and listed in `links:`, and up to three linked pages are excerpted into a
  `## Linked` section (GitHub repos through the API and README, arXiv papers through the API,
  any other page by title, description and main text). Images and video posters are kept, a
  quoted post is named. Stdlib, fixed timeouts; a failure only marks `enrichment: partial`.
  [earned: 2026-09-25 — tweets are 47% of Readwise captures; 17 of 42 in September held only
  t.co links, a screenshot prompt arrived as nothing, ~16 read "Your browser does not support
  the video tag."]
- **Distill has tweet rules**: a pointer tweet becomes a note about the thing it points at
  (named for it, `tool-landmark` / `research-finding`, `sources:` with the links); a thread or
  field report keeps the author's claim; `## Linked` is material fetched from the capture's own
  links, so invariant 9 holds.
- **`Dashboard.html`** (`dashboard_build.py`, a fourth generator in `end`): twelve weeks of
  distilling in one self-contained page — today / yesterday / 7 / 30 days, per day by source, a
  twelve-week heatmap, domains, kinds, search, the notes (opening in Obsidian) and the runs.
  Notes with a backfilled `processed_date_estimated: true` stay out.

## [Unreleased] — R12, the vault from a cloud session

A Claude cloud task runs in this repo, where the code and skills are, and reaches the vault through
git; the vault stays knowledge only and gets no copy of the code.

- **farsight 0.1.2** — a note's own headings are weighted like its title wherever they fall, not only
  within the first 2,000 characters scored: "how were contrails solved" found nothing although a
  note has a section "Result: contrails solved" at character 3,512; it now ranks first. Mirrors
  `search.py`. [earned: 2026-09-24 pipeline run, a distill worker's findability check]
- **`scripts/cloud-vault.sh`** — `open` clones (or updates) `$TOOLKIT_VAULT_REMOTE` into the
  git-ignored `.vault-live/`, syncs the scripts' environment and reports keys by name;
  `close` is the pipeline's own `end` (index, maps, Now, secret scan, commit, pull, push).
- **Git-ignored notes leave every generated view and lint.** Tested end to end against a bare
  clone of the real vault: three notes kept out of git because they hold a secret sat in the
  Mac's maps and Index and not in the clone's, so every sync would have flipped them. Now a build
  on the Mac and one in a clone produce identical maps. [earned: 2026-09-23]
- `AGENTS.md` gains "Working on a real vault".

## [3.0.0] — R12, six skills and one entry file; generated navigation and git sync (reconstructed from history)

Fifteen skills, six wrapper commands and a duplicate distill agent cost a slot in every session's
skill list and about 2,470 lines of skill text, 666 of them generic Obsidian syntax reference.
Six skills remain, each short enough to read and follow without the plugin installed.

- **`obsidian:vault`** joins `vault-ops` and `vault-lint`; one 51-line syntax sheet replaces the
  five Obsidian format references.
- **`radar:radar`** absorbs `kagi` as a section; **`handoff:handoff`** absorbs `handoff-resume`
  as a mode.
- **plugins/handoff 3.0.0** — `handoff-resume` folds into `handoff` as its resume mode (one skill,
  two sections, instead of two skills); its now-redundant `commands/handoff.md` and
  `commands/handoff-resume.md` thin wrappers are removed, since a skill is invoked by its own
  name. No behavior change to save or resume themselves.
- **readwise is scripts only**: the pipeline runs `ingest.py` by path. `daily`/`status` (Now.md
  and Log.md say the same), `enrich` and its two modules (never run by the pipeline) and the
  SessionStart hook (a line in every session) are gone.
- **Maintainer loops** `judgment-calibration` and `retrieval-verification` are procedures in
  `docs/MAINTAINING.md`; their scripts are unchanged.
- **All six commands and `agents/knowledge-distillation-agent.md` removed.**
- **`AGENTS.md` is the entry file** for the repo, the example vault and every vault
  `toolkit vault init` creates (`contract/templates/VAULT_AGENTS.md`). Claude Code reads
  `AGENTS.md` when no `CLAUDE.md` is on the path; keeping both would hide it.

**Generated navigation and git sync (plugins/obsidian)**

The vault had a flat 1,386-line Index.md and about 80 hand-made MOCs that its own rules forbid
("no hand-maintained MOCs"); they had gone stale. Everything a person or an agent uses to find
their way is now rebuilt by the pipeline's `end` step, with no model call.

- **`map_build.py`** — one `Maps/<domain>.md` and `.canvas` per `domain/*` tag (Start here = the
  most-linked notes, New = last 30 days, every note by `kind`, neighbouring domains by co-tags),
  plus `Maps/Overview`. Titles, intros and sections come from `Config/toolkit/maps.md`.
- **`now_build.py`** — `Now.md`, the homepage: this week's new and enriched notes from the
  pipeline's own commits, the radar's strong items, parked captures and open DLQ notes, the inbox,
  notes distilled per day, and live `Vault.base` views below. `Boards/Pipeline.md` is the same
  state as a Kanban board.
- **`vault_setup.py`** — installs `Vault.base`, the `toolkit.css` snippet and two Templater
  capture templates; prints the settings only the owner can click.
- **Git is the sync channel** — with an upstream, `begin` commits hand edits and pulls
  (`--rebase`), `end` commits, pulls and pushes; a conflict aborts, writes a DLQ note and skips the
  run. Cloud sessions write to the vault through the same remote.
- **Secret scan before every commit** — a key-shaped string on the staged diff refuses the commit;
  the DLQ note names the file and the kind of key, never the value.

## [2.10.0] — R10/R11, the radar; tools from migrating a live vault (reconstructed from history)

Everything before R10 ran *after* a clip. Measured on a real Reader account: 1,716 feed items in
30 days, none of them ever opened, and 55 clips made by hand, none from the feed. The radar reads
the feed in full with the same typed judgments distill uses, and only what matters reaches you.
Plan and acceptance: `docs/R10-RADAR-PLAN.md`.

- **`radar.py scan`** — Reader `location=feed` items, deduped by canonical URL (GitHub repo roots
  and arXiv abs/pdf/vN collapse, `judgments/urls.py`), by feed + title (a repost under a new
  address) and by back catalogue (published a week before the window: a newly subscribed feed's
  archive) [earned: 2026-09-22 smoke run, both arrived as new]. Jev answers `worth_reading` per item
  x interest and `kind` per item, 8 items per request; rows go to `00_Memory/radar/state.jsonl`
  and a daily note. Every item the radar has recorded then leaves the feed: archived, or with
  `--promote` moved to Later tagged `radar/<interest>` with a dated note. A failed promotion stays
  in the feed and is retried; nothing is ever deleted [Mike, 2026-09-23: judged items off the feed].
- **`radar.py replay`, the acceptance run** — own clips vs. feed items, three scorers on the same
  items. Same-day AUC: **Jev 0.70, BM25 0.57, recency 0.47**; at 20 items a day 71% of clips would
  have been shown (BM25 50%). The first run reported pooled AUC, where recency scored 0.68 because
  18 of 27 clips came from one bookmark import; same-day AUC is now the headline, and delivered
  newsletters no longer count as clips [earned: 2026-09-23 replay].
- **Blind audit** — 120 stratified items plus the top 30, labelled by a model that never saw p:
  the strong band held at 69%, the 0.60–0.80 band at 23%. `T_WORTH` moved 0.60 → 0.70 (1,325 feed
  items → 194 worth, 102 strong). Scoring the same items in different batches moves p by 0.02 on
  average and flips 1% of bands.
- **`radar.py feeds`, `trend`, `weekly`** — from state only, no model: per-feed yield with
  "consider unsubscribing" and "serves only <interest>"; interests rising above their baseline
  (median prior rate, flagged above lambda + 2 sqrt(lambda)); `01_Capture/Radar-Week-YYYY-Www.md`, a
  draft digest for distill that never links `00_Memory`. The first yield report: 101 of 102
  strong items from arXiv, three embedded feeds with none in a month.
- **`radar.py discover`** — candidate feeds from Kagi (the interests' own queries), URL shapes
  (GitHub releases.atom, subreddit .rss, Substack, Medium), RSS autodiscovery, one hnrss search per
  interest and `--seed` URLs; each fetched, parsed and dropped when thin, dormant or already
  delivered, then judged per interest; an OPML with the reason per feed, since Reader has no
  subscription API. Kagi spend is measured from the account balance against a weekly budget.
  Per-host spacing and a 429 retry [earned: parallel fetches to reddit.com drew 429s]; an hnrss
  feed's title is renamed before judging because it is the search query. First run: 20 searches
  ($0.50) found 72 candidates and 8 keepers; seeds added the rest; 14 feeds subscribed.
- **Plumbing** — `judge.py`, `judgments/urls.py`, `judgments/state.py` are byte-identical copies
  of obsidian's with a parity test (no cross-plugin imports); `judge.py` derives its key env name
  from the profile name. The radar skill (daily and weekly briefing, scheduling reference),
  `profile.example.md` with what leaves the machine, four offline evals in CI (scan 8 phases,
  replay, discover, reports on a hand-made six-week series). `contract/KNOWLEDGE_API.md` names
  `00_Memory/` and `01_Capture/` as the only automation sinks.
- **Not built** — `gaps`, `--todoist`, a Kagi skill (specified in the plan).

**Tools from migrating a live vault**

What the first real migration (a ~1,200-note vault, 2026-09-22) needed that the plugin lacked. The
normalize audit went from 810 issues to 370 and Index.md drift from 148 dangling / 73 missing /
277 bootstrap entries to none.

- **`scripts/vault_yaml_repair.py`** — frontmatter that does not parse is invisible to every other check; 81 notes on the real vault failed for two mechanical reasons (an unquoted `: ` or `@handle`, a corrupted opening delimiter). One-line repairs, bodies untouched, the archive only on request; anything else is reported. The eval caught a Templater `{{date}}` case the rehearsal script had missed.
- **`scripts/index_build.py`** — Index.md from each note's own `description`, no model call. Replaces v1's Gemma pass, which produced a second summary per note that drifted from the description search actually weights. A note without a description keeps its previous line and is marked ⚙; ✓/⚠ carry over; a rebuild leaves vault_lint with no drift.
- **`checks/links.py`** — `[[Note#Heading]]`, `[[Note^block]]`, `[[#Heading]]` and the table-escaped `[[Note\|alias]]` were all reported broken, and a repair rebuilt the link, dropping anchor and alias; a missing `[[Person]]` inside that person's article was repaired into a self-link. All three fixed, each with an eval phase shown to fail on the old code.
- **`checks/frontmatter.py`** — sixteen lifecycle words on 80 real notes (`capture`, `living`, `shipped`, `ready-to-paste`, …) map to the contract's five statuses without a model, and the original word is kept in `stage:`. The fix label now says what decided it (it claimed "via LLM" for the no-model default).
- **Measured on the real vault** — Jev reviewed 1,206 notes for $0.08: 124 confident domain suggestions (104 applied where a note still lacked the domain) and 179 weak plus 24 missing descriptions, which were then rewritten from each note's content and verified line-level.

## [2.9.0] — R9, typed judgments on suggested links, and a quality reading list

- **plugins/obsidian 2.9.0: `graph.adjudicate_candidates()` and `scripts/link_judge.py`** — gaiafield's inferred candidates gain an advisory `adjudication` per pair from two narrow questions asked in one request: would a link help a reader (`p`), and are the two notes about the same underlying idea (`p_same_mechanism`). gaiafield's own score, label and order are never touched, the block stays report-only under KNOWLEDGE_API rule 1, AMBIGUOUS rows still appear only on request, and no key degrades silently (`GraphUnavailable("no-judgment")`). No Rust change; the crate neither knows about it nor depends on it.
- **What the measurement showed** — 105 pairs of the example vault: 20 the author linked by hand, 15 unlinked across the two planted project clusters, 70 of gaiafield's own suggestions labelled twice by blind annotators (a reasoning model that saw no scores). On gaiafield's rows the same-idea question ranks real links at AUC 0.95 where gaiafield's cosine reaches 0.75, and only 11 of the 70 suggestions were real by either annotator: **the suggestion list on this vault is about 85% noise, and a typed judgment is what sorts it.** With the shipped policy 11 rows read LIKELY-LINK (8 real), 16 read LIKELY-NOISE (0 real). [earned: R9 2026-09-22 — the first wording ("same underlying mechanism … so that a reader should be pointed") scored the author's own hand-made links at a mean of 0.24 and rejected 16 of 20; the question was narrower than what an author links. The broader wording moved them to 0.75. Both are kept because they measure different things, and three single-condition rewordings of the narrow one were tried and dropped for ranking no better.]
- **`scripts/vault_judge.py`** — a report-only reading list: notes with no description, descriptions too vague or padded to pick the note out (the two planted description specimens are the two lowest of 63), and domains a note is clearly about but does not carry. On the example vault it also made a finding about the vault itself: every note is tagged `domain/toolkit-meta` and almost nothing else, so the tags carry no information; the eight suggestions it made (knowledge-management for Atomic-Notes and PARA-Method, software-engineering for Toolkit-CLI, …) are the informative ones. `vault_normalize.py --fix` stays the only thing that edits notes; the tag fixer was deliberately **not** switched to the judgment backend on this evidence.
- **Golden set grown, by construction** — eight fixture captures under `evals/fixtures/captures/` (a repost of a note's source, a benchmark that contradicts a note, an empty stub, a promo, a cheat sheet, a project-bound and an area-bound capture, a strict subset of a sibling) give every question family a known positive: 68 rows, live agreement 50/54 tune and 13/14 held out. The one new miss is policy, not wording (the repost scores 0.68 on same-source against a 0.80 cut) and is reported, not changed.
- **Migration prerequisites** — the vault's domain taxonomy is a profile key (`domains`, name → one-line meaning), read by the tag audit, the LLM tag classifier and the judgment questions alike; capture retirement prefers `trash` over `rm` when it exists, so a vault with a delete-guard hook can run the workflow.
- **`scripts/search_judge.py`: search, widen, judge** — the two follow-ups from the published Jev-plus-graph work were built and measured against each other on twelve reader's-words questions with one known answer note each. A Jev-driven hop-by-hop graph walk (the neo4jev pattern) reached the answer 4 of 12 times at 5 s and 3× the cost of a rerank, and was dropped. What it showed on the way is what shipped: the three questions keyword search never found were each one wikilink away from a note it did find. So candidates are widened deterministically by the top hits' neighbours (no model call) and reranked once: search alone 5/12 first and 9/12 found; rerank alone 9/12 first; widened rerank **11/12 first, 12/12 found**, 0.7 s and $0.0006 a query. The same widening now feeds the distill advisory block's related-note list (`via`). Soft placement from the same source: a runner-up folder holding ≥ 0.25 of the mass is named as an alternative instead of being discarded.
- **First contact with a real vault (1,476 notes, rehearsal copy)** — two things the example vault could never show. The backend has an input limit: a capture with 40 widened candidates, and 40 pairs of real-length notes, were refused with `max_tokens_exceeded`, and the question-halving retry cannot help because every half carries the same state. `judge.StateTooLarge` now names that case and `judgments.state.in_chunks()` splits note- and pair-shaped state on it, down to one item; every caller asks in chunks (8 notes, 12 pairs). And gaiafield's gates do not transfer, as [[Calibration-Bias]] predicted: at 0.72 the real vault has over 2,000 INFERRED pairs, of which a typed judgment calls 41% noise (random 80). Link adjudication itself held: author-made links vs random unlinked pairs across PARA folders, AUC 0.96, 0 of 40 unlinked pairs judged a likely link. Retrieval did **not** repeat the example-vault gain on first try: farsight alone put the answer first for 15 of 15 reader-written questions, because a 1,476-note vault with curated descriptions gives BM25 far more to work with, and because the questions leaked the notes' own words. A harder set (no word shared with title or description) is the honest test and is recorded where it lands.
- **Review pass before merge** — five independent reviews (code paths, docs against code, the offline suite, branch history for secrets, the skill evals) found: `distill_judge.py --calibrate/--check-note/--passages` and `distill_check.py`'s findability loop let `JudgmentFailed` escape as a traceback where every sibling script reports it (fixed, exit 1 / plain search order); `judgments.policy.thresholds()` raised `SystemExit` for an unregistered backend instead of the `JudgmentFailed` the degrade paths handle (now routed through `judge.policy_for`); the profile key `enrichment_targets` was documented as pinning candidates but read by nothing (now read by `distill_judge.py`, root-level notes included, with an offline eval that fails when it goes dead again), and `default_capture_prefixes` is described as what it is, a naming convention no script branches on. Two retirement descriptions now agree (`<stem>--FULLCAPTURE.md` plus a manifest line). Nothing secret or vault-private in any commit; the one real-vault figure in the migration guide is rounded.
- **Skill evals with `claude plugin eval`** — `plugins/obsidian/skill-evals/` (declared via `experimental.evals`, so the offline script evals keep `evals/`): three cases that run a real model against the distill skill in a scaffolded copy of the example vault. `distill-auto` (an explicit --auto run must run the dossier, write or enrich, pass `distill_check`, retire the capture), `distill-checkpoint` (without --auto nothing is written and the reply is a proposal), `triage-inbox` (decisions per capture, nothing written). Where a typed judgment can be the grader it is: `distill-auto` grades the JSON `distill_check.py` writes (hard gates, findability of the agent's own questions, kept passages carried) with free regex graders, and an LLM grader is used only for what a reader must judge. Two things the sandbox forced: `scripts/` is now its own uv workspace root (discovery walked up to a read-denied repo root), and the scaffold pre-builds the scripts' environment and puts the OpenRouter key from `~/.env` into the workspace's project settings so Jev works inside the run. The default judge model failed a correct triage reply three votes to none; `--judge-model claude-sonnet-5` passes it. First full run: 3/3 cases, $3.9.
- **The distill skill rewritten for a stronger model** — 539 lines of numbered procedure became 292 lines of invariants and two tools, on the vault's own [[Delete-Over-Add-for-Stronger-Models]] principle. `distill_judge.py --dossier` produces everything mechanical up front (judgments, the capture's essence, graph context, adjudicated inferred candidates) in one block; `distill_check.py` is the definition of done (hard gates: frontmatter, own-source line, stored document linked, no forbidden or dangling wikilinks, Index line; soft: dropped URLs, findability of the reader's questions, passages not carried). The agent decides the order. `distill_judge.py` itself split into `judgments/{capture,policy,passages,batch}.py`, 843 → 521 lines. Diagrams (mermaid) for the dossier flow, the check, the judgment seam and the calibration loop.
- **Three findings from the Readwise acceptance run, fixed** — (1) *Cluster mode never replaces the captures' own notes.* Five captures merged into one 10 KB synthesis kept 30 of 40 main points and 13 of 40 specifics, and 8 of 11 unanswerable recall questions asked for exactly those; the rule is now one note per capture with its own specifics plus a hub, and `distill_judge.py --check-note NOTE CAPTURE` lists the kept passages a note does not carry (workflow step 7c) so a member note closes only when the misses are empty or named. (2) *A PDF clipping stores the document.* The readwise plugin downloads a `pdf` item's original into the vault (`attachments_folder`, default `04_Resources/Attachments`), the capture carries `attachment:` and a Document link, and the distilled note must keep it; `--passages` now covers 200 passages of a 400 KB capture. (3) *Batch uniqueness scales.* Above twelve captures, pairs are blocked by shared source, shared URL or title overlap (73 captures → 55 pairs, $0.002, 4 s); a pair with the same own source once tracking parameters are stripped, or near-identical text, is a `duplicate` without a model call [earned: Reader held one video twice under URLs differing by `&is=`, and the judged answer sat on the cut].
- **Three maintenance judgments, tested on the rehearsal copy** — `distill_judge.py --passages`: which passages of a capture carry a claim, number, mechanism or example (the essence a distilling agent reads first: 24 of 24 probe claims kept in 77% of the text on three real captures), which are the pipeline's own text, and how the pipeline's synthesis relates to the article as a four-way Choice (a Noul "is it faithful" scored every real synthesis 0.3-0.5 because syntheses add framing by design; the Choice reads them `adds_framing` and a planted inversion `misstates`). `vault_sweep.py`: same-work and contradiction judgments over pairs from shared source addresses and gaiafield's inferred edges; on the real vault, 1,200 pairs for $0.06 found eleven plan files kept in two folders, two concept notes that are the same paper as another note, and seven same-day spec/plan pairs with conflicting decisions. A shared address is a candidate, never a verdict [earned: 2026-09-22 — a 252-note methodology folder shares one repository URL]. `checks/links.py`: with a backend, one Choice per broken wikilink over a thirty-name shortlist plus `none`; the audit reports `apply:`/`propose:`, `--fix` writes only `apply` (p ≥ 0.80, margin ≥ 0.30). Sample of 100 real notes: 191 broken links, 41 apply, 22 propose.
- **Replay against the old process, blind** — three archived captures re-distilled on a 1,476-note rehearsal copy with the old notes hidden; a blind editor scored old vs new on preservation and linking. Preservation tied 9/9 everywhere: the judgments do not change what Claude writes. Linking decided it: new wins two of three and, for one capture, found a same-source note from June the old run had duplicated; old wins one, on principle-level bridges no generator in the stack proposes. Three changes from that: the capture query no longer carries Readwise header boilerplate; a second relevance channel, "same underlying principle, even in another field" (`p_principle`, `bridge`), which scores those links 0.61-0.71 where the topic question gave 0.36-0.52; and the capture's own in-text citations join the candidates. Retrieval on the same notes from memory-style questions: 7/9 old, 5/9 new, with the misses unfindable by any channel because the note's words are not the reader's, so the workflow gains a **findability check** before enrichment (step 7b).
- **Stability, measured before trusting a label** — the same pair asked again moves by 0.02-0.04; asked with its two notes swapped it moves by 0.08-0.10 on average and up to 0.5, enough to flip a third of the labels; one pair per request swings as much as forty, so it is an order effect, not batch cross-talk. `adjudicate_pairs()` therefore asks every pair in both orders, averages, reports the disagreement as `order_gap`, and reads a gap of 0.30 or more as UNDECIDED whatever the average says. The per-capture distill questions were checked the same way (rerun drift 0.008, a second reversed view changes nothing) and stay at one request. A guide, [[Migrating-a-Live-Vault]], sets out the rehearse-on-a-copy order for moving a long-lived vault onto the plugins.
- **Evals** — `eval_link_adjudication`: six offline phases (attach, untouched rows, both row shapes, silent no-key, one DLQ note on failure, read-only) plus an opt-in live phase whose ground truth needs no annotator: author-linked pairs must outrank unlinked cross-cluster pairs (AUC ≥ 0.90; measured 0.99) and none of the latter may read LIKELY-LINK.

## [2.8.0] — R8, typed judgments: probabilities into the distill checkpoint

- **contract/ROUTING.md: a third tier, typed-judgment models** — narrow, independent questions answered with a probability instead of prose, batched over one shared state; the model supplies the number, **code owns the policy** (thresholds per backend, never in question text). [earned: R8 2026-09-21 — once farsight supplied raw BM25 scores the 0.70 enrichment gate became "informational only", leaving "which found notes are really related" to unaided prose judgment on every capture] Removal condition: the hosted default goes once a local backend passes the live eval at parity. `KNOWLEDGE_API.md` gains "Judgments": never an edge kind, never stored, report-only under rule 1, meaningless without backend + model + `questions_version`.
- **plugins/obsidian 2.8.0** — `scripts/judge.py`, a backend-neutral seam (noul and choice only, so a local logit-readout backend can drop in later); first backend `jev` (TypeSafe System One via OpenRouter) spoken over stdlib `urllib`: no new dependency, a fresh clone and CI are unaffected. `scripts/distill_judge.py` asks one request per capture (triage, per-note relevance and relation → suggested L1/L2/L3, same-source-different-URL, domains, placement with an explicit `ambiguous`) plus one pairwise-uniqueness request per batch, and prints an **advisory** block for the Phase 1 handoff. Nothing is applied, `discard-candidate` is only ever a candidate, a frontmatter URL hit still beats the model. No key → `SKIPPED`, nothing sent; a configured backend that fails → one DLQ note. Three bundled captures: 4 requests, about $0.001.
- **Wording is data, tuned by the reasoning model** — every question lives in `scripts/judgments/questions.py` under a `QUESTIONS_VERSION`; the new `judgment-calibration` skill classifies each disagreement by cause (missing evidence / question too broad / debatable label / model error / threshold) before proposing the smallest fix, may edit wording and labels but never policy, keeps a held-out slice unseen, and never accepts a backend's answer as a label. First run, recorded in the vault's [[Typed-Judgments]] note: 30/35 → 31/35 on tune rows with held-out unchanged, three misses traced to one over-broad question (collector's remarks in a capture tied it to the capture-conventions guide).
- **Evals** — `eval_distill_judge`: seven offline phases against a stubbed transport (wire shape, every backticked state path resolves, policy mapping, no-key skip, request halving, exactly one DLQ note on total failure, vault untouched) plus an opt-in live phase (`TOOLKIT_EVAL_LIVE_JEV=1`) scored against `evals/golden/distill_judge.golden.json`. The golden rows are Claude-labelled proposals at `should` strength until a human confirms them, and say so.
- **Said plainly:** with a key set, capture text and the heads of related notes go to a hosted service. `profile.example.md`, the README and `contract/PROFILE.md` now require that statement next to any key that enables egress.

## [2.7.0] — R7, first-hand value: installers, demo, handoff, and an anti-bloat pass

- **Three-line integration** — `uv tool install git+https://github.com/marsmike/agentic-toolkit#subdirectory=core` puts `toolkit` on PATH; `toolkit engines install` fetches the released engine binaries for your platform (GitHub API via stdlib, sha256-recorded manifest, idempotent) into `~/.local/share/agentic-toolkit/bin`; `claude plugin marketplace add marsmike/agentic-toolkit` adds the plugins. The binary-discovery chain gained the well-known install dir, so zero env vars are needed. `install.sh` bootstraps all of it for the impatient — readable, idempotent, no sudo, asks before installing anything.
- **`toolkit demo`** — sixty seconds to first-hand value: vault scan → farsight query → gaiafield graph → inferred candidates, each step really executed and explained in one line. Works in a repo checkout against the example vault or anywhere via a temp mini-vault.
- **plugins/handoff 2.7.0** — the session-continuity plugin, migrated from the legacy toolkit and overhauled vault-driven: portable `_handoff/` markdown chained per stream (cross-tool via an AGENTS.md pointer), discovery index in the vault, profile-configurable (autosnapshot/index path/visibility), PreCompact autosnapshot hardened to the memory-plugin hook standard, DLQ on silently-lost-handoff failure modes. No fourth frontmatter parser: the plugin needs three flat scalars, so a ~25-line scan replaces the general pattern — and the observer's adversarial pass earned it comment-stripping and idiomatic boolean coercion (`autosnapshot: no` no longer silently means yes). Read-compatible with legacy-written handoffs, proven by resuming a real one in the eval.
- **Anti-bloat pass** — −70 net lines across crates and plugins with zero behavior change: duplicated extraction/guard/collision logic merged into helpers, contract tables deduplicated to pointers, closure-factory flattened. Every `[earned:]` receipt preserved. What was deliberately left alone (cross-crate duplication, transaction semantics) is documented in the PR.

## [2.6.0] — R6, the vault becomes the published documentation

- **Docs site** — `./vault` published to GitHub Pages via Quartz 4 (pinned v4.5.2): wikilinks resolved, backlinks, full-text search, and an interactive graph view — the knowledge-graph toolkit's docs render as an actual knowledge graph. No separate docs tree exists to drift; the vault is the single source. `00_Memory/` and `01_Capture/` are excluded from the published surface.
- **Docs audit** — every concept/guide note verified against shipped reality (most predated the implementations they describe): Farsight.md no longer claims vector search it doesn't have, Gaiafield.md documents v1+v2 as history with real gates, six new concept notes cover what R1–R5 practiced but never wrote down (the observer pattern, the cold-boot ritual, report-only inference, calibration bias, capability probing, headless scripting). Landing surface rewritten for strangers. Vault: 78 active notes, 829 wikilinks, all planted test invariants intact.
- **Node-count test made corpus-derived** — gaiafield's planted-structure test now computes the expected count from Index.md instead of hardcoding it; growing the docs is no longer a test-breaking event. [earned: docs-audit R6 2026-07-26 — hardcoded 73 broke at 79]
- **Pre-publication sweep** — repo made public after a full pass: zero employer references, zero personal identifiers, zero secret patterns; owner name corrected to match the public GitHub profile; the legacy archive noted as private by design.

## [2.5.0] — R5, inferred edges: the statistical layer, report-only by contract

- **contract/KNOWLEDGE_API.md v2** — two edge kinds, never conflated: `extracted` (deterministic wikilinks) and `inferred` (semantic similarity, labeled INFERRED or AMBIGUOUS). Rule 1 is load-bearing: **report-only, forever** — no automation writes vault content from an inferred edge without human confirmation in-session. Inference is perfectly separable (`infer --reset` provably restores the exact v1 graph), gates are meaningless without their model name, traversal defaults to deterministic.
- **gaiafield 0.2.0** — embedding backend model2vec-rs + potion-base-8M (256-dim static embeddings: deterministic, offline after a sha256-pinned one-time download, zero C/C++ in the embedding stack — verified by build-log inspection). New subcommands: `infer`, `candidates`, `surprise`, `calibrate`. Incremental re-embedding on note change only.
- **Calibration, corrected by the observer loop:** the first calibration's pooled statistics were dominated by the example vault's 57-note grab-bag cluster — separation 0.08 was a cluster-size artifact, and at those gates 70% of all note pairs got flagged (a birding note drew 31 mostly-noise candidates). Recalibrated on tight clusters only (objective leave-one-out rule; the grab-bag self-excludes): separation 0.177, gates 0.72/0.67, flagged pairs 1405 → 480, and the same birding note's default view is now a single same-cluster candidate. The bias lesson is documented plainly in the crate README. [earned: R5 engine observer 2026-07-26]
- **Coordination bug, owned:** the CLI spec handed to the two parallel builders omitted `label` on surprise rows — contradicting the contract's own AMBIGUOUS-never-proactive rule written an hour earlier. Both builders faithfully implemented their halves of an inconsistent spec; the stub-driven eval sealed the false confidence until the observer's first real-binary integration exposed it. Fixed on both sides; the eval now carries a real-binary phase so a stub can never again stand in for the boundary. [earned: R5 engine observer 2026-07-26 — the spec author was the failure point, not the builders]
- **plugins/obsidian 2.5.0** — distill phase-1 presents inferred candidates in a separated, model+score-labeled, report-only block (AMBIGUOUS only on request; surprise leads only when asked); capability probe distinguishes v1 binaries via exit-0 + whole-word subcommand matching (a --help mentioning "inference" in prose no longer false-positives into a spurious DLQ note); `toolkit doctor` reports model, gates, and edge counts.

## [2.4.0] — R4, two more plugins cross over: readwise and memory

- **plugins/readwise** — curated port of the highlight-ingestion pipeline: 9 v1 skills consolidated to 4 (ingest/enrich/daily/status), stdlib-only Reader v3 + Classic v2 client, dedup-safe capture writes keyed on `readwise_doc_id`, origin-prefixed captures per the vault contract, profile via `Config/toolkit/readwise.md`, token via `READWISE_TOKEN` env only. The v1 session-start hook printed a banner for every user without a token — now a silent no-op. Observer review wired `write_dlq_note` at both real ambiguity sites (missing source_url/title; unparseable profile — whose `except` branch was previously dead code) and added a book-capture dedup eval. 4 fixture-driven evals, no network.
- **plugins/memory** — the mechanism/content split: session-capture hook (SessionEnd only, stdlib-only, 2MB transcript cap, double safety net — the shell layer cannot propagate a Python failure into the session) plus a `distill-memory` skill writing `kind: sop|warning|fact` notes into `00_Memory/`. Dropped from v1 by design: the idle-debounce Stop hook that spawned background `claude -p` calls (silent LLM spend), and the entire persona/self layer — identity lives in your vault, not this repo. Observer review hardened the stdlib frontmatter codec to fail loud (`ValueError`) on non-flat YAML instead of silently mis-parsing — which the hook's catch-all converts into a DLQ note — with a pyyaml parity eval. 3 evals.
- **Engine patches** (same push): gaiafield 0.1.1 — incremental-deletion corruption fix (see corrected R2 entry below); farsight 0.1.1 — root-note `status: active` scope, ending a cross-engine disagreement where the graph could traverse a note search couldn't find.
- Process note: this is the first release cycle run fully on the observer pattern — every builder deliverable was adversarially verified by an independent agent before commit; every finding above marked "observer review" is a receipt from that loop.

## [2.3.0] — R3, the obsidian plugin consumes the gaiafield graph

- **plugins/obsidian/scripts/graph.py** — a thin client for the gaiafield binary, mirroring `search.py`'s farsight preference chain (`TOOLKIT_GAIAFIELD_BIN` env var → `gaiafield` on PATH → absent). `available()`, `ensure_index()`, `neighbors()`, `graph_stats()`, and `graph_context()` all shell out with `--json`. Absence of a binary is a normal, silent degrade (`GraphUnavailable("no-binary", ...)`); a binary that IS present but fails on a real call writes a DLQ note under `00_Memory/dlq/` before degrading the same way — the dead-letter rule (`contract/KNOWLEDGE_API.md`) applied to a genuine tool failure, not to the expected pre-adoption absent state. R3 scope only: deterministic graph consumption — no inferred edges, no LLM calls (gaiafield v2/R4+).
- **Distill phase 1 gains graph context** — after the existing search step, when a gaiafield binary is available, `graph_context(vault, matched_paths, k)` fetches depth-1 neighbors of the top text-search matches and splits them into **backlink candidates** (neighbors search itself missed) and **bridge opportunities** (candidates living in a different top-level PARA subtree than the capture's proposed placement — the deterministic precursor of the surprise scoring a later gaiafield increment adds, not a scored signal itself). `skills/distill/references/workflow.md` documents when/how phase 1 uses it; `SKILL.md` gets a one-line pointer. When the binary is absent, phase 1 proceeds exactly as before and the Phase 1 handoff says so in one line.
- **`checks/links.py` refactor: evaluated, skipped.** gaiafield's CLI surface (`index`/`neighbors`/`stats`/`path`) only exposes aggregate dangling-edge and boundary-violation *counts* (`stats`), not the per-note list of broken links with their raw target text that `links.py`'s `audit()` needs to produce actionable issues and propose fixes. Getting that list would mean either a new gaiafield CLI verb (an engine change, out of scope this release) or reading the SQLite database directly, which `contract/KNOWLEDGE_API.md`'s "never bypass an engine's internal state" rule forbids. `checks/links.py` is unchanged; small perfect code beats a lossy feature.
- **core/toolkit_core/knowledge.py** — a minimal, plugin-independent gaiafield status check (same binary-discovery chain, reimplemented rather than imported per the plugin-independence rule) backing a new `toolkit doctor` graph section: db present/absent, node/edge/dangling/boundary counts, and index freshness (newest active-content note mtime vs. the database's own mtime), or `"gaiafield not present"` when no binary is found. `core/tests/test_core.py`'s existing doctor test gains asserts for the absent-binary shape plus one new test exercising the present-binary path against a stub script (no dependency on the Rust crate being built for `pytest` to pass).
- **plugins/obsidian/evals/eval_graph_context.py** — a new R3 capability eval, registered in `evals/run.py`. Mirrors `eval_search_parity`'s presence gate (pass with `"gaiafield not present"` when no binary is available; doesn't build the crate itself). With a binary present, runs against a sandbox copy for a capture placed in the birding cluster and asserts a correct Level-1 backlink candidate from the planted field-guide cluster, plus a non-empty bridge-opportunity list — guaranteed deterministic because both of the birding cluster's top matches (`Field-Guide-Project.md`, `Birding.md`) link directly to `Alex-Vega.md`, the vault's root bridge note (`Test-Corpus-Map.md`), which can never share a top-level PARA folder with either placement candidate.
- Version bump to **2.3.0** (marketplace.json, plugins/obsidian/plugin.json) — the obsidian plugin's own behavior changed (graph.py, distill's phase 1), so it moves in lock-step per `CONTRIBUTING.md`. `crates/gaiafield` itself is untouched this release and stays on its own `gaiafield-v*` tag scheme.

## [2.2.0] — R2, gaiafield

- **crates/gaiafield** — the second Rust engine: deterministic knowledge-graph extraction (`gaiafield index [--vault] [--db] [--full] [--json]`, `neighbors <note> [--depth] [--direction] [--json]`, `stats [--json]`, `path <from> <to> [--json]`), CLI-in/JSON-out per `contract/KNOWLEDGE_API.md`. v1 scope only, by design: wikilinks, frontmatter, and tags into SQLite — no model call, no edge that can hallucinate, so the graph can't rot; see `docs/PLAN.md` (Engines) and `vault/04_Resources/Concepts/Deterministic-vs-Inferred-Graph-Edges.md`. Inferred (similarity-threshold) edges, confidence-labeled EXTRACTED/INFERRED/AMBIGUOUS, were here slated for R3; R3 (2.3.0) instead shipped deterministic graph *consumption* first (reliability-before-inference), so inferred edges moved to R4+.
- **Node scope** extends the schema's active-content filter (`02_Projects`/`03_Areas`/`04_Resources`) with root-level notes that self-declare `status: active` in their own frontmatter — in the example vault, exactly `Alex-Vega.md`. This is a documented, narrow deviation from a literal reading of `contract/VAULT_SCHEMA.md`'s active-content filter (which names those three folders for "any generated index"): without it, the bridge structure `vault/04_Resources/Guides/Test-Corpus-Map.md` plants around Alex-Vega ("root persona, links into all three clusters") would be unrecoverable — no note titled Alex-Vega would exist in the graph at all. See `crates/gaiafield/README.md` ("Node scope") for the full reasoning.
- **Edge resolution** classifies every wikilink target into one of four buckets: a normal `EXTRACTED` edge to another node; a **boundary violation** (resolves into `00_Memory`/`01_Capture`/`05_Archive`, which the schema forbids linking into from active content); **out of scope** (resolves to a real file that just isn't a node — `Config/`, `Templates/`, a root note without `status: active` — not an error, not flagged, simply not modeled); or **dangling** (doesn't resolve anywhere in the vault). Bare-name targets ambiguous between multiple real files resolve same-folder-first, falling back to recording an edge to every remaining candidate rather than guessing — deliberately more permissive than the CLI's own note-argument resolution, which refuses to guess at all and reports every candidate instead (exercised by this vault's planted duplicate-title case, `Weekly-Review`, once per project).
- **Incremental indexing** compares each node's mtime+size against the stored value and re-extracts only new/changed notes, deleting rows for notes removed from the vault; **correction (2026-07-26, adversarial observer review):** as originally shipped, other notes' edges *into* a removed note survived as resolved rows — `neighbors` crashed and `path` silently routed through deleted nodes. Fixed in gaiafield 0.1.1: incoming edges are re-flagged `dangling = 1` on node removal (the wikilinks still exist in source bodies), with a regression test. This entry originally described intended rather than verified behavior — noted per the ratchet; `--full` rebuilds from scratch. Default store: `<vault>/.gaiafield/graph.db` (gitignored — a test run never leaves one untracked inside the example vault).
- **crates/gaiafield/tests/graph_test.rs** — one lean integration test file (7 tests) run against `./vault`, asserting the planted structure in `Test-Corpus-Map.md`: node count and link density, the single planted dangling edge, zero boundary violations, the Alex-Vega bridge reaching all three clusters within depth 2, a birding-to-homelab path, the ambiguous `Weekly-Review` lookup, and incremental re-indexing touching only the changed note.
- **Cargo workspace** — `crates/gaiafield` is the second workspace member, depending on `rusqlite` (`bundled` feature — the crate's only C dependency; `farsight` has none). `.github/workflows/release-binaries.yml`'s cross-compile step for `aarch64-unknown-linux-musl` was written for a crate with no C code; per a static read of `taiki-e/setup-cross-toolchain-action`'s own script it does provide a real `CC_<target>` cross-compiler (not just a linker) that `cc-rs`/`libsqlite3-sys` should pick up, but this is unverified until the first `gaiafield-v*` tag actually builds on that target.
- **No plugin changes this release** — `plugins/` is untouched, so `marketplace.json` and `plugins/obsidian/.claude-plugin/plugin.json` stay at **2.1.0**; `crates/gaiafield` starts independently at **0.1.0** and releases on its own tag scheme (`gaiafield-v*`), same as `farsight`.

## [2.1.0] — R1, farsight

- **crates/farsight** — the first Rust engine: a stateless BM25 search binary (`farsight query "<terms>" [--vault] [--k] [--json]`), CLI-in/JSON-out per `contract/KNOWLEDGE_API.md`. No persisted index — a per-query scan over `02_Projects`/`03_Areas`/`04_Resources` is fast at vault scale (~100–1500 notes) and eliminates staleness by construction; see the crate README for the removal condition. Dependencies stop at `clap` + `serde`/`serde_json` + `serde_yaml` — no `tantivy`, no embedding stack, since the stateless decision rules them out for this release.
- **plugins/obsidian/scripts/search.py** — gains a preference chain: shells out to a `farsight` binary (`TOOLKIT_FARSIGHT_BIN` env var, else PATH) when one is available and returns its results; falls back to the existing Python BM25 path unchanged otherwise (docs/PLAN.md's fallback contract). Scoped and cache-rebuild calls still go through Python only, since farsight doesn't cover those yet.
- **plugins/obsidian/evals/eval_search_parity.py** — checks farsight's top-3 results overlap >=2/3 with the Python implementation's top-3 for 3 fixed queries when a binary is present; reports pass with "farsight not present — python fallback only" when it isn't, since release binaries don't exist yet.
- **Cargo workspace** — `crates/farsight` is the first workspace member; `.github/workflows/release-binaries.yml`'s `farsight-v*` tag path now builds a real crate instead of a not-yet-existing one.
- Version bump to **2.1.0** (marketplace.json, plugins/obsidian/plugin.json) — the obsidian plugin's own behavior changed (search.py's preference chain), so it moves in lock-step per `CONTRIBUTING.md`. `crates/farsight` itself starts independently at 0.1.0 — engine crates version and release on their own tag scheme (`farsight-v*`), not the plugin line.

## [2.0.0] — R0, the walking skeleton

R0 is version **2.0.0** everywhere (marketplace.json, plugin.json, both
pyproject.toml) — the 2.x line marks the vault-first generation; 1.x history
lives in the legacy repo.

- **contract/** — the constitution: vault schema (frontmatter as floor, not ceiling), profile convention ("fill from Obsidian"), knowledge API (filesystem+CLI over MCP indirection), model routing rules, and the `vault init` template.
- **core/** — `toolkit` CLI: `vault init`, `doctor`, `profile`; tolerant frontmatter IO; `TOOLKIT_VAULT` → `./vault` resolution.
- **vault/** — the example vault: documentation written as vault notes, `vault init` template, deterministic test corpus with planted edge cases, and eval substrate.
- **plugins/obsidian** — the reference plugin, curated from v1 (vendored env dropped): vault operations, distill workflow, lint, and the new retrieval-verification skill.
- **CI** — path-filtered checks, contract↔example-vault consistency gate, evals gate, gitleaks, release-binaries skeleton.

Prior history lives in `agentic-toolkit-legacy` (a private archive — it predates the privacy scrub); this repo starts with fresh history by design (see docs/PLAN.md).
