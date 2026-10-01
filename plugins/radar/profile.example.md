---
description: Example profile for the radar plugin — copy the frontmatter shape below into your own vault's Config/toolkit/radar.md.
kind: profile
status: active
plugin: radar
interests_note: 03_Areas/Trend Radar Profile.md
todoist_project_id: ""
todoist_sections: Doing,Next,Waiting
promote_location: later
promote_per_run: 5
promote_per_name_per_run: 2
promote_per_name_per_day: 6
promote_per_source_per_run: 3
promote_sensor_share: 0.5
promote_per_event_per_day: 3
# bubble_weights:            # multiply a bubble's weight (interest id or name)
#   music-production-djing: 0.5
watch: OpenAI,GPT,ChatGPT,Codex,Anthropic,Claude,Google,Gemini,DeepMind,Meta,Muse,Llama,Mistral,xAI,Grok,DeepSeek,Qwen
kagi_weekly_budget_usd: 1.00
tavily_weekly_budget_usd: 2.00
sensors: hn,hf,github,reddit,rss,kagi_news
sensor_kagi_news: AI,Technology,Linux & OSS,Music Technology,Science
sensor_subreddits: LocalLLaMA,ClaudeAI,ClaudeCode,singularity,MachineLearning,synthesizers,WeAreTheMusicMakers,audioengineering
sensor_github_topics: llm,ai-agents,claude-code,mcp,local-llm,audio-plugin,vst
signal_artifact_url: ""
judgment_backend: jev
judgment_base_url: https://openrouter.ai/api
judgment_model: jev-1.13-20260917
tags:
  - domain/toolkit-meta
  - profile
---

# radar plugin profile (example)

Copy this file's frontmatter shape to `$VAULT/Config/toolkit/radar.md` to override the plugin's
shipped defaults. Every field is optional; an absent file or field falls back to the default
shown here. Each field can also come from the environment as `TOOLKIT_RADAR_<FIELD>`
(`contract/PROFILE.md`: env var, then this note, then the default).

## Fields

- **`interests_note`** — the note that holds your interests: frontmatter `interests:`, a list of
  `{name, gloss, queries, tags}`. `gloss` is one sentence saying what the interest *is*; it and
  the name are all the judgment backend ever sees. `queries` are search strings for `discover`
  and go only to Kagi.
- **`todoist_project_id`**, **`todoist_sections`** — optional: open top-level tasks in these
  sections of a Todoist project (via the `td` CLI) become interests too, with the first sentence
  of the task's `What:` line as gloss. Off while the id is empty or `td` is missing.
- **`promote_location`** — where `scan --promote` moves a strong item: `later` (default),
  `shortlist` or `new`.
- **`promote_per_run`** — how many strong items one `scan --promote` (or one `gaps --promote`) may
  save into Reader (default 5), sensor items first and the feed's strong items after them. The
  budget starts fresh every run, so a busy morning cannot starve the rest of the day. Both
  commands allocate the same way (the keys below, the bubbles' weights and credit); the strong
  gap items a weekly run has no slot for wait in the hold file, and the next scans offer them again. The 0.80
  "strong" bar is policy and stays in code; this is the owner's appetite. Raise it when the daily
  radar note shows strong items the cap discarded.
- **`promote_per_name_per_run`**, **`promote_per_name_per_day`** — how many sensor promotions one
  watched name (Muse, OpenAI, …) may take in a run and in a day (defaults 2 and 6). Outlets retell
  one story in headlines too different to match, and distill merges them into one note anyway; a
  lab's own announcement always goes, and counts.
- **`promote_per_source_per_run`** — how many of a run one source may take: a Reader feed, a Google
  News search, Hacker News, a lab's own blog (default 3). What it holds back waits in the window
  for the next run.
- **`promote_sensor_share`** — the share of a run's budget the sensors are offered first (default
  0.5); the Reader feed gets the rest, and whatever the feed leaves goes back to the sensors. Both
  sides are allocated together (below).
- **`promote_per_event_per_day`** — how many promotions one story may take in a day (default 3). A
  story is an event the Signal Radar saw this fortnight (Sonnet 5.5, DevDay, Muse), or headlines that
  overlap enough; its best copy (a lab's own post, the feed, an open outlet, a paywall last) is
  promoted and the other outlets ride along in the Reader note as "also covered by".
- **`bubble_weights`** — a multiplier per bubble (interest id or name). A bubble's weight is
  `sqrt(1 + notes) + sqrt(1 + notes this month)` from the vault (tags or `radar_interests`), times
  1.5 while the Signal Radar calls it rising; this key has the last word.

**How a run chooses (`allocation.py`).** Must-see events (a Signal Radar early warning, or strength
75+ from 3+ source families) and the labs' own posts go first, up to half the run. Then every bubble
gets turns by weight: each run adds `promote_per_run × weight share` to its credit, each promotion
costs one, credit carries from run to run (halved at a new day). A bubble with nothing yet today
goes first, so every bubble with a strong item gets one a day; a bubble more than one past its share
waits. What is not taken is held: a feed item stays in Reader and is offered again first for three
days, a sensor item stays in the window; what never makes it is written to `missed.jsonl`. Each scan
rewrites `00_Memory/radar/Bubbles-<day>.md`, the day by bubble (★ must-see, ⏳ held, ✗ missed, → the
note), which the daily note copies in.
- **`watch`** — the labs and models you follow by name (comma list or YAML list). A sensor item
  (Hacker News, Kagi News, the sensor RSS feeds) whose title names one and that the judge rates
  worth reading (0.70) is saved into Reader like a strong feed item, and the Signal Radar's web
  check asks watched names first. Matched case-insensitively, ending at a non-letter: `GPT` matches
  "GPT-6.1", `Meta` does not match "metadata". A lab's own announcement page (`openai.com/index/…`,
  `anthropic.com/news/…`, `blog.google/technology/ai/…`, the list in `policy.LAB_ANNOUNCEMENTS`) is
  saved whatever the judge says, watch list or not. Empty: no watched-name rule.
- **`kagi_weekly_budget_usd`** — `discover` stops searching once the week's Kagi spend (measured
  from the account balance, kept in `00_Memory/radar/kagi-ledger.jsonl` and, for the Signal Radar,
  `kagi-ledger-signal.jsonl`; one budget over both) would pass this.
- **`tavily_weekly_budget_usd`** — the same for Tavily, called only through the `tvly` CLI: the
  Signal Radar's name check and the Reddit sensor's fallback stop once the week's spend (list price,
  $0.008 a credit, one credit a search; `tavily-ledger.jsonl` and `tavily-ledger-signal.jsonl`)
  would pass this. The free 1,000 credits a month cover the default use.
- **`sensors`** — which momentum sources `sensors` pulls (default all six: `hn`, `hf`, `github`,
  `reddit`, `rss`, `kagi_news`). **`sensor_kagi_news`** — Kagi News categories by name, as its
  index at news.kagi.com/kite.json lists them (AI, Technology, Music Technology, Apple, …). **`sensor_subreddits`**, **`sensor_github_topics`** — comma lists;
  **`sensor_feeds`** — a YAML list of RSS/Atom URLs (the default covers audio plugins and model news).
- **`signal_artifact_url`** — a claude.ai artifact the Signal Radar routine republishes the page to;
  empty = the page stays in the vault only.
- **`judgment_backend`**, **`judgment_base_url`**, **`judgment_model`** — the typed-judgment
  backend, as in the obsidian plugin. Thresholds are never profile keys; they live in
  `scripts/judgments/policy.py`.

## What leaves the machine

- To the judgment backend (OpenRouter by default): item titles, summaries and site names; feed
  titles, descriptions and recent item titles; interest names and glosses. Never your queries,
  never vault content.
- To Kagi (`discover`, `gaps`): the interests' queries; (`signal --check`, only when Tavily
  cannot run): up to six entity names a day, each at most once a week.
- To Tavily, through the `tvly` CLI (`signal --check`): up to six entity names a day, each at most
  once a week; (`sensors`, only when Reddit refuses the request): `r/<subreddit>` for each
  subreddit, each at most every 12 hours. Weekly budget `tavily_weekly_budget_usd` (default 2.00).
- To Hacker News (Algolia), Hugging Face, GitHub, Reddit, Kagi News and the `sensor_feeds` hosts (`sensors`):
  plain GETs of public listings; the GitHub topics and subreddit names are in the URLs.
- To Reader: the location, tags and note of items the radar has recorded (archive, or Later with
  `--promote`). Nothing is ever deleted.
- To arbitrary sites (`discover` only): plain GETs of search-result pages and feed URLs.

## Secrets

No credential belongs in this file — see `contract/PROFILE.md`'s Secrets section. Keys come from
the environment or the key file (`~/.env`, read by the script itself): `READWISE_TOKEN`, `KAGI_API_KEY`, `TAVILY_API_KEY` (read by the Tavily CLI `tvly`,
never by this plugin directly — the Signal Radar's name check and the Reddit sensor's fallback),
and `TOOLKIT_RADAR_JUDGMENT_API_KEY` (or
`OPENROUTER_API_KEY`). Without one, the command that needs it prints `SKIPPED` and sends nothing.
