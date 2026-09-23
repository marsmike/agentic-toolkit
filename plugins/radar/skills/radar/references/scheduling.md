# Scheduling the radar

The radar runs unattended once a day and once a week. Two shapes; pick one per machine, never both.

## Claude Desktop scheduled task (with a briefing)

A local scheduled task in Claude Desktop runs the skill and leaves you the five-line briefing.

- **Daily**, 07:00: folder `~/Developer/agentic-toolkit`, instruction: *"Use the radar skill: run
  the daily scan with --promote against the vault in TOOLKIT_VAULT and brief me."*
- **Weekly**, Saturday 07:30: same folder, instruction: *"Use the radar skill: write the weekly
  capture and brief me, including feed advice."*

The task needs `TOOLKIT_VAULT`, `READWISE_TOKEN` and `OPENROUTER_API_KEY` (or
`TOOLKIT_RADAR_JUDGMENT_API_KEY`) in its environment. The repo ships no `.env` loader: export them
in the shell profile the task starts from.

## launchd (no agent, no briefing)

The scan needs no model beyond the judgment backend, so it can run as a plain job:

```bash
/bin/zsh -lc 'cd ~/Developer/agentic-toolkit && \
  uv run --project plugins/radar/scripts python3 plugins/radar/scripts/radar.py scan --since 1d --promote --json \
  >> ~/Library/Logs/radar.log 2>&1'
```

`--since 1d` overlaps a missed day only if the job runs late; after an outage run once with
`--since 3d`. Already-seen items cost nothing: they are deduplicated before any request.

## What a failed run looks like

- `SKIPPED`: a key or the interests note is missing. Nothing was sent or moved.
- `failed` with a `dlq` path: the backend answered nothing; one note in `00_Memory/dlq/`, every
  item stays in the feed for the next run.
- `archive_error` / `promote_error` in an `ok` result: judging worked, moving items in Reader did
  not; the next run moves them.
