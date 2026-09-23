---
name: kagi
description: Ask Kagi — web search, recent small-web and news posts, a sourced answer (FastGPT), or a summary of any page, video or PDF (Universal Summarizer). Use for "search Kagi", "what's new on X", "summarize this link", or a quick answer with references.
allowed-tools:
  - Bash
---

# Kagi

Four of Kagi's services, one command each, all under the radar's spend ledger and weekly budget
(`kagi_weekly_budget_usd`, default $1.00; every call is recorded in
`00_Memory/radar/kagi-ledger.jsonl` with what it actually cost).

```bash
K() { uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/radar.py" kagi "$@" --json; }
K search "query"          # web results                       ~$0.025
K news "query"            # recent small-web and news posts    ~$0.002, with publish dates
K answer "question"       # FastGPT: an answer with references ~$0.015
K summarize "https://…"   # Universal Summarizer: page, video, PDF; billed per 1k tokens, a long page ~$0.30
```

Pick the cheapest mode that answers the question: `news` for "what happened lately", `answer` when
a sourced paragraph is enough, `search` when you need to read the pages yourself, `summarize` only
for one long thing you would otherwise read in full.

## Hard requirements

- **Report the answer with its sources.** `answer` returns references; cite them, never the model.
- **`over-budget` is a stop, not a retry.** Say how much was spent this week and let the human
  raise the budget in the profile.
- **Nothing is written to the vault.** To keep a result, save the page in Reader (it becomes a
  capture through the pipeline) or file an insight with the distill skill.
- `SKIPPED` means `KAGI_API_KEY` is not set: say so, stop.

The same client runs the radar's `discover` (new feeds) and `gaps` (what the feeds missed); see the
radar skill.
