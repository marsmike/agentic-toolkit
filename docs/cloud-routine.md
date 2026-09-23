# The pipeline as a Claude cloud routine

The unattended pipeline can run as a scheduled Claude routine instead of launchd on the Mac: the
routine works in this repo (code and skills), clones the vault through git, runs the pipeline
skill, and pushes the vault back. Everything the next run needs is committed in the vault
(`00_Memory/pipeline-state.json`, `radar/*.jsonl`, `readwise-ingested.jsonl`, `readwise-state.md`,
`Config/toolkit/`), so a fresh clone continues exactly where the last run stopped.
[earned: 2026-09-23, R12 — the owner moves the pipeline to a cloud routine]

## Routine prompt

The routine runs in this repo, so its instruction can be one line, and this file stays the one
place to change:

```text
Follow the "Routine prompt" in docs/cloud-routine.md exactly: run the TheVoid pipeline once, unattended.
```

The prompt it points at (paste it in full instead if you prefer the routine to be self-contained):

```text
Run the TheVoid knowledge pipeline once, unattended, then stop. Ask no questions: if something
blocks, record it (the scripts write DLQ notes) and finish the run.

SETUP
1. You are in the agentic-toolkit repo (code and skills). Work from its root:
     export TOOLKIT_REPO="$PWD" CLAUDE_PLUGIN_ROOT="$PWD/plugins/obsidian"
   If `uv` is missing: pip install uv
2. Vault. If a TheVoid checkout already exists in the workspace (a directory holding AGENTS.md
   and 00_Memory/, e.g. ../TheVoid), export TOOLKIT_VAULT=<that path>. Otherwise run
     scripts/cloud-vault.sh open
   and export TOOLKIT_VAULT="$PWD/.vault-live". Never commit the vault into agentic-toolkit.
3. Keys: check by name only, never print a value:
     python3 -c "import os; print({k: bool(os.environ.get(k)) for k in ('OPENROUTER_API_KEY','READWISE_TOKEN','KAGI_API_KEY')})"
   A missing key means that source prints SKIPPED. That is fine; go on.
4. Read $TOOLKIT_VAULT/AGENTS.md, then plugins/obsidian/skills/pipeline/SKILL.md, and follow
   the pipeline skill exactly (use the obsidian:pipeline skill if it is loaded; otherwise follow
   the file). Distill each capture per plugins/obsidian/skills/distill/SKILL.md in --auto mode.
   The radar commands are
     uv run --project plugins/radar/scripts python3 plugins/radar/scripts/radar.py <args>
   and ingest is
     uv run --project plugins/readwise/scripts python3 plugins/readwise/scripts/ingest.py --json

RUN, in the skill's order
- pipeline_run.py begin. "busy" or "skipped": stop and report why. Keep the "token" it returns.
- Radar: scan --since 1d --promote --todoist --json. With `td` installed (the environment's
  setup script) and TODOIST_API_TOKEN set, --todoist comments the strong items on each epic
  task itself. Once a week (Saturday): gaps --promote and weekly ("exists" is normal).
- Readwise ingest.
- pipeline_run.py queue --json, then distill every capture in the batch (--auto). Rebuild the
  index after each note and before distill_check.
- Todoist fallback, only if `td` is not on PATH: for each interest in
  $TOOLKIT_VAULT/Config/toolkit/radar.md that has a todoist_task_id and got strong items today,
  add ONE comment to that task with the Todoist connector:
    "[radar YYYY-MM-DD] N strong feed item(s) for this epic:" plus up to 5 "- [title](url) (p=0.xx)"
  Skip a task if 00_Memory/radar/todoist.jsonl already has {"task": id, "date": today}.
  After posting, append that line to the file.
- pipeline_run.py end --token <token> --distilled N --dropped N --failed <captures>. ALWAYS call it, even
  after a failure. It rebuilds Index, Maps and Now, runs the secret scan, commits TheVoid,
  pulls and pushes. Status "refused" = a key-shaped string; the DLQ note says where.

HARD RULES
- Never delete in Reader. Never discard a clip; only radar or newsletter captures may leave
  without a note.
- Stay within the batch.
- Never edit generated files (Index.md, Now.md, Maps/, Boards/, Log.md).
- Never run git in the vault yourself: begin and end are its only committer.
- Never print, write or commit a key.

FINISH with one line: what came in (radar, readwise), distilled / dropped / failed, the commit,
and whether it was pushed.
```

## Routine settings

- **Repositories:** attach both `marsmike/agentic-toolkit` (the working repo, branch `main`) and
  `marsmike/TheVoid`. The session's git push rights cover only attached repos.
- **Environment variables:** `TOOLKIT_VAULT_REMOTE=https://github.com/marsmike/TheVoid.git`,
  `OPENROUTER_API_KEY`, `READWISE_TOKEN`, `KAGI_API_KEY`, `TODOIST_API_TOKEN` (read by `td`);
  optional `TOOLKIT_OBSIDIAN_PIPELINE_BATCH=10`. Keys live only there, never in a file in a repo.
- **Setup script** (below): installs tools only. It assumes no repository is cloned yet.
- **Network access:** the run calls `openrouter.ai`, `readwise.io`, `kagi.com`, `api.todoist.com`,
  GitHub, PyPI and npm. If the environment's network level is restricted, allow those hosts or
  use full access; otherwise each source just prints `SKIPPED`.
- **Connectors:** Todoist, only as the fallback when `td` is missing.
- **Schedule:** every 3 hours.

## Environment setup script

Runs when the environment starts, before any repository may be present, so it installs tools
and touches no repo: `uv` for the scripts (their dependencies install on first `uv run`) and
`td`, Doist's Todoist CLI (`@doist/todoist-cli`), which reads `TODOIST_API_TOKEN` and lets
radar's `--todoist` comment on the epics directly.

```bash
#!/bin/bash
# TheVoid pipeline routine: tools only; no repository is assumed to exist yet.
set -u
command -v uv >/dev/null 2>&1 || pip install -q uv || echo "uv not installed; the routine installs it"
if command -v npm >/dev/null 2>&1; then
  command -v td >/dev/null 2>&1 || npm install -g --silent @doist/todoist-cli || echo "td not installed; Todoist falls back to the connector"
else
  echo "npm missing: td not installed; Todoist falls back to the connector"
fi
echo "uv: $(uv --version 2>/dev/null || echo missing) · td: $(td --version 2>/dev/null || echo missing)"
```

Every step degrades instead of failing: without `uv` the routine installs it, without `td`
the prompt's Todoist fallback uses the connector.

## On the Mac, once the first cloud run has pushed

1. **Run only one scheduler.** The run lock (`00_Memory/pipeline.lock`) is a local file git does
   not carry, so it cannot stop a Mac run and a cloud run from overlapping. Stop the launchd job:
   `launchctl unload ~/Library/LaunchAgents/io.agentic-toolkit.pipeline.plist`
   (`skills/pipeline/references/scheduling.md` describes it).
2. **Obsidian Git takes over the Mac's sync.** The Mac pipeline used to commit hand edits and pull
   from GitHub. With it off, set Obsidian Git to auto commit-and-sync every 10 minutes, pull on
   startup, and pull before push. Otherwise the Mac copy falls behind the cloud's commits, and
   Obsidian Sync spreads that stale copy to the other devices.
