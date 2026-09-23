# Scheduling the pipeline

The pipeline runs unattended every 3 hours: `scripts/run-pipeline.sh` starts Claude Code headless
with the obsidian and radar plugins loaded from the repo (readwise ingest runs as a script) and the pipeline skill as the
instruction. launchd runs it; a Claude Desktop scheduled task with the same instruction works too
(pick one, never both: the run lock turns the second into a no-op, but it still costs a start).

To run it as a Claude cloud routine instead (no Mac needed), see `docs/cloud-routine.md`.

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

## Reading a run

- `Now.md`: this week's new and enriched notes, radar, stuck work and inbox (rebuilt every run).
- `Log.md`: one `pipeline |` line per run with distilled / retired / failed.
- The vault's git log: one `pipeline YYYY-MM-DD HH:MM: …` commit per run; `git revert` undoes a run.
- `00_Memory/dlq/`: parked captures (failed twice) and ingest gaps, each with what to do.
- `00_Memory/radar/<date>.md`: the day's feed judgments, for reading.
