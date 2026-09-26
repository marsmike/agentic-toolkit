---
description: Example profile for the radar plugin — copy the frontmatter shape below into your own vault's Config/toolkit/radar.md.
kind: profile
status: active
plugin: radar
interests_note: 03_Areas/Trend Radar Profile.md
todoist_project_id: ""
todoist_sections: Doing,Next,Waiting
promote_location: later
promote_per_day: 5
kagi_weekly_budget_usd: 1.00
sensors: hn,hf,github,reddit,rss
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
- **`promote_per_day`** — how many strong items a day `scan --promote` and `gaps --promote` together
  may save into Reader (default 5). The 0.80 "strong" bar is policy and stays in code; this is
  the owner's appetite. Raise it when the daily radar note shows strong items the cap discarded.
- **`kagi_weekly_budget_usd`** — `discover` stops searching once the week's Kagi spend (measured
  from the account balance, kept in `00_Memory/radar/kagi-ledger.jsonl`) would pass this.
- **`sensors`** — which momentum sources `sensors` pulls (default all five: `hn`, `hf`, `github`,
  `reddit`, `rss`). **`sensor_subreddits`**, **`sensor_github_topics`** — comma lists;
  **`sensor_feeds`** — a YAML list of RSS/Atom URLs (the default covers audio plugins and model news).
- **`signal_artifact_url`** — a claude.ai artifact the cloud run republishes the Signal Radar page to;
  empty = the page stays in the vault only.
- **`judgment_backend`**, **`judgment_base_url`**, **`judgment_model`** — the typed-judgment
  backend, as in the obsidian plugin. Thresholds are never profile keys; they live in
  `scripts/judgments/policy.py`.

## What leaves the machine

- To the judgment backend (OpenRouter by default): item titles, summaries and site names; feed
  titles, descriptions and recent item titles; interest names and glosses. Never your queries,
  never vault content.
- To Kagi (`discover`, `gaps`): the interests' queries; (`signal --kagi`): up to six entity
  names a day, each at most once a week.
- To Hacker News (Algolia), Hugging Face, GitHub, Reddit and the `sensor_feeds` hosts (`sensors`):
  plain GETs of public listings; the GitHub topics and subreddit names are in the URLs.
- To Reader: the location, tags and note of items the radar has recorded (archive, or Later with
  `--promote`). Nothing is ever deleted.
- To arbitrary sites (`discover` only): plain GETs of search-result pages and feed URLs.

## Secrets

No credential belongs in this file — see `contract/PROFILE.md`'s Secrets section. Keys come from
the environment or the key file (`~/.env`, read by the script itself): `READWISE_TOKEN`, `KAGI_API_KEY`, and `TOOLKIT_RADAR_JUDGMENT_API_KEY` (or
`OPENROUTER_API_KEY`). Without one, the command that needs it prints `SKIPPED` and sends nothing.
