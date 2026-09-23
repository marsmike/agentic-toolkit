---
name: pipeline
description: The one unattended run that keeps the vault current — radar and Readwise bring material in, distill turns it into notes and connections, the vault commits. Use when a scheduled task (or the user) says "run the pipeline".
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Grep
  - Glob
---

# Pipeline

One run, start to finish, no questions: new material comes in from every source, becomes notes
and links through the same distill for all of it, and the vault commits. It runs every few
hours; a run that finds nothing is short and says so.

```bash
P() { uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/$1" "${@:2}"; }
P pipeline_run.py begin          # pulls the vault's upstream first; "busy" (another run holds the lock)
                                 # or "skipped" (pull conflict, key in hand edits; DLQ note): stop, say so
# sources, each optional; SKIPPED (no key, plugin absent) is fine, go on:
#   radar skill:     radar.py scan --since 1d --promote --todoist --json
#                    radar.py gaps --promote   (once a week: what the feeds missed; "exists" is normal)
#                    radar.py weekly   (last week's digest, written once; "exists" is normal)
#   readwise:ingest: ingest.py --json
P pipeline_run.py queue --json   # this run's captures: the owner's clips first, oldest first
# distill each one with the distill skill, --auto
P pipeline_run.py end --distilled N --dropped N --failed <captures that failed distill_check>
```

**Sources.** The radar judges the feed and promotes at most five strong items a day to Reader's
Later, and once a week writes the digest capture (`via: radar`); ingest turns every new library item (your clips, newsletters, promoted items) into a
capture that says how it arrived (`via`). Run them in that order so promoted items land in this
run's queue.

**Distill.** Each capture in the queue goes through the distill skill in `--auto` mode, exactly as
it would by hand: dossier, read the related notes, write or enrich, `distill_check`, retire the
capture. Rebuild the index (`P index_build.py`) after writing a note and before
`distill_check`, whose Index gate needs the new line. The source changes one thing only (distill invariant 8): a `clip` always ends as a note
or an enrichment; a `radar` or `newsletter` capture may be retired without one when the dossier
triage says discard, with the reason in the manifest line. A capture whose `distill_check` does
not pass stays in `01_Capture/` and goes into `--failed`; after two failed runs `queue` parks it
with a DLQ note for a human.

**End, always.** Call `end` even when a step failed, with what did happen: it rebuilds the
index, the maps (`Maps/`) and `Now.md` with its board, logs the run, commits the vault (the undo
for everything the run wrote) and pushes it when the vault has an upstream. A staged key-shaped
string makes `end` return `refused`: nothing is committed, a DLQ note names the file. The
counts are disjoint: `--distilled` = captures that became a note or an enrichment (every one of
them is also archived; that is not a drop), `--dropped` = captures that left *without* a note (a
radar or newsletter discard; never a clip), `--failed` = captures still in `01_Capture/`.
[earned: 2026-09-23, a run logged "10 distilled, 10 retired" for ten captures]
Reply with one line: what came in, what was distilled or dropped, what failed, the commit, and
whether it was pushed.

## Hard requirements

- **Never skip `begin`/`end`.** Two runs at once corrupt the queue; a run without `end` leaves no
  commit to undo and holds the lock for hours.
- **Never delete a clip, never discard one.** Only `radar` and `newsletter` captures may leave
  without a note, and only through distill's retirement.
- **Nothing outside the vault changes** except Reader locations the radar sets (archive, Later)
  and the vault's own git upstream, which `begin` pulls and `end` pushes. Never delete in Reader,
  never run git in the vault yourself: `begin`/`end` are its one committer.
- **Never edit the generated files** (`Index.md`, `Now.md`, `Maps/`, `Boards/`, `Log.md`); fix
  the note or `Config/toolkit/maps.md` and let `end` rebuild them.
- **Stay within the batch.** The backlog drains over several runs; a run that tries to do
  everything at once is the one that times out mid-write.
