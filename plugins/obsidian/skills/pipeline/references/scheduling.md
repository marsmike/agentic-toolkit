# Scheduling the pipeline

The pipeline runs unattended every 3 hours: `scripts/run-pipeline.sh` starts Claude Code headless
with the obsidian and radar plugins loaded from the repo (readwise ingest runs as a script) and the pipeline skill as the
instruction. launchd runs it; a Claude Desktop scheduled task with the same instruction works too
(pick one, never both: the run lock turns the second into a no-op, but it still costs a start).

To run it as a Claude cloud routine instead (no Mac needed), see `cloud/README.md`.

## launchd

`~/Library/LaunchAgents/io.agentic-toolkit.pipeline.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>io.agentic-toolkit.pipeline</string>
  <key>ProgramArguments</key><array>
    <string>/bin/zsh</string><string>-c</string>
    <string>$HOME/Developer/agentic-toolkit/plugins/obsidian/scripts/run-pipeline.sh</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>TOOLKIT_VAULT</key><string>/Users/YOU/Documents/YourVault</string>
  </dict>
  <key>StartInterval</key><integer>10800</integer>
  <key>StandardOutPath</key><string>/tmp/agentic-toolkit-pipeline.log</string>
  <key>StandardErrorPath</key><string>/tmp/agentic-toolkit-pipeline.log</string>
</dict></plist>
```

The run's agent holds no key and reaches only what the pipeline needs (`run-pipeline.sh` says
exactly what): each script reads its own key from `~/.env` (or `TOOLKIT_KEYS_FILE`), and a stub's
source is fetched only from `TOOLKIT_PIPELINE_FETCH_DOMAINS` (default `github.com
raw.githubusercontent.com`; add either variable to `EnvironmentVariables` to change it). A stub
from an unlisted domain ends as a short note with its link; add the domain to
`TOOLKIT_PIPELINE_FETCH_DOMAINS` to fetch it again.

```bash
launchctl load ~/Library/LaunchAgents/io.agentic-toolkit.pipeline.plist     # start
launchctl start io.agentic-toolkit.pipeline                                  # one run now
launchctl unload ~/Library/LaunchAgents/io.agentic-toolkit.pipeline.plist   # stop
```

## Git is the sync channel

When the vault's branch has an upstream, `begin` commits hand edits and pulls (`--rebase`), and
`end` commits, pulls again and pushes. Cloud sessions write to the vault through the same remote,
so their commits arrive with the next run. The pipeline is the only committer on the Mac: in
Obsidian Git, turn auto-commit **off**, pull on startup **on**, push manual. A conflict aborts the
rebase and skips the run with a DLQ note; nothing is resolved by guessing.

## The Mac while the pipeline runs in the cloud

With the pipeline a cloud routine, nothing on the Mac pulls its commits or pushes hand edits
unless something runs `pipeline_run.py sync` there: hand edits committed (the pipeline's secret
scan), the upstream pulled (`--rebase`; a conflict aborted with a DLQ note), pushed, all under the
run lock. `scripts/vault-sync.sh` wraps it for launchd: one log line per run, a macOS notification
when it needs a human (a conflict, a refused key, an hour of failures), and git authenticated with
`GH_TOKEN` from `~/.env` through a helper that never reaches the Keychain.
[earned: 2026-10-01 — the Mac pulled only when a session did it by hand]

`~/Library/LaunchAgents/io.agentic-toolkit.vault-sync.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>io.agentic-toolkit.vault-sync</string>
  <key>ProgramArguments</key><array>
    <string>/bin/zsh</string><string>-c</string>
    <string>$HOME/Developer/agentic-toolkit/scripts/vault-sync.sh</string>
  </array>
  <key>EnvironmentVariables</key><dict>
    <key>TOOLKIT_VAULT</key><string>/Users/YOU/Documents/YourVault</string>
  </dict>
  <key>StartInterval</key><integer>600</integer>
  <key>RunAtLoad</key><true/>
  <key>ProcessType</key><string>Background</string>
  <key>StandardOutPath</key><string>/Users/YOU/Library/Logs/agentic-toolkit-vault-sync.log</string>
  <key>StandardErrorPath</key><string>/Users/YOU/Library/Logs/agentic-toolkit-vault-sync.log</string>
</dict></plist>
```

```bash
launchctl load ~/Library/LaunchAgents/io.agentic-toolkit.vault-sync.plist     # start (and one run now)
tail ~/Library/Logs/agentic-toolkit-vault-sync.log                            # one line per run
launchctl unload ~/Library/LaunchAgents/io.agentic-toolkit.vault-sync.plist   # stop
```

One machine per vault: two checkouts that Obsidian Sync keeps alike would each commit the same
hand edits.

**Obsidian Sync beside git.** Obsidian Sync merges files too, and a device or server with an older
copy of the vault can merge stale versions in (2026-10-01: Signal-Radar.md back to an earlier run,
59 old Log.md lines appended, a pipeline enrichment dropped from a note, `readwise-state.md`'s
`lastSyncedAt` corrupted to "2026-110-01…"). So `sync` never commits what the cloud routines own
(`CLOUD_OWNED`: Log.md, `00_Memory/radar/`, the pipeline and Readwise ledgers and state, and the
generated navigation): a local change to those goes back to HEAD. A change to any other file that
is byte for byte an earlier version of it, or only drops lines a pipeline run added in the last 24
hours, is held: not committed, left in the working copy, one DLQ note (`sync-held-…`) and one
notification. A deletion is always the owner's.

## Reading a run

- `Now.md`: this week's new and enriched notes, radar, stuck work and inbox (rebuilt every run).
- `Log.md`: one `pipeline |` line per run with distilled / retired / failed.
- The vault's git log: one `pipeline YYYY-MM-DD HH:MM: …` commit per run; `git revert` undoes a run.
- `00_Memory/dlq/`: parked captures (failed twice) and ingest gaps, each with what to do.
- `00_Memory/radar/<date>.md`: the day's feed judgments, for reading.
