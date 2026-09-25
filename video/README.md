# Explainer video

The agentic-toolkit explainer, rendered with [Remotion](https://www.remotion.dev) from **real captured CLI
output**. Terminal scenes replay the recorded bytes in `capture/`; nothing is retyped. No video, audio or
`node_modules/` is committed (`.gitignore`); the render is published as a release asset.

## Layout

| Path | What it is |
|---|---|
| `capture/record.py` | Records one command, or one interactive shell session with typed commands, in a pseudo-terminal as asciicast v2 (`.cast`: output + timing). Stdlib only. |
| `capture/capture.py` | Runs the README newcomer commands in a clean, empty HOME and records each one. |
| `capture/cast_text.py` | Writes each capture's final screen as `.txt`: the verbatim transcript the video's numbers and names are checked against. |
| `src/timeline.json` | The film on one page: eight scenes on a 3-second bar grid (80 BPM), one label per scene, and the cue times. The picture and the music both read it. |
| `src/graph.json`, `scripts/build_graph.py` | The example vault's real link graph (gaiafield: 83 notes, 783 links) with a fixed layout, plus the search hits, neighbours and INFERRED pairs looked up from the capture. |
| `src/Explainer.tsx`, `src/Root.tsx` | The `Explainer` composition: one graph layer on screen the whole time, a camera gliding over it, scene layers crossfading on top. Nothing cuts. The terminal scene replays real session lines through `src/cast.ts`. |
| `src/cast.ts` | Replay of a `.cast` into screen text (same rules as `cast_text.py`). |
| `music.json`, `MUSIC.md`, `scripts/make_music.py` | The music bed, generated from `src/timeline.json` (not committed). |
| `test/` | Replay vs transcripts; timeline, graph and capture agree; music is documented. |

## The captures

| Folder | Rev | Commands | Result |
|---|---|---|---|
| `headline/` | 72bb351 | README "New here" block, verbatim | All exit 0; the demo uses a 3-note temp vault (no checkout), so no `[INFERRED]` line |
| `from-source/` | 72bb351 | README "From source" line, verbatim | Demo stops after step 1 (`[engines] not installed`); `claude plugin marketplace add .` is rejected |
| `from-source-fixed/` | 72bb351 | From source + `uv run toolkit engines install`, `add ./`, one shell per command | All exit 0; 82 notes, 783 edges, 3 `[INFERRED]` lines (decision D6) |
| `from-source-main-0dd21a7/` | 0dd21a7 | main's README From-source journey as **one continuous `/bin/sh -i` session**: clone, `cd` once, engines, demo, `add ./` | All exit 0; both engines print `installed unverified` (no published `.sha256`); demo as above |

Which capture is filmed is decision D8 (outcome-lead). `main` moved from 72bb351 to 0dd21a7 on 2026-09-24, so the
72bb351 folders no longer show what `main` installs.

## Re-capture

Needs `uv`, `git` and a `claude` binary. Only `claude` is taken from this machine, through a directory that
holds nothing else, so no installed `toolkit` can leak onto PATH:

```bash
mkdir -p /private/tmp/prereq-bin
ln -sf "$(readlink -f "$(command -v claude)")" /private/tmp/prereq-bin/claude
python3 capture/capture.py                  # lists the paths and the main revision each one records
python3 capture/capture.py from-source-main-0dd21a7
npm test                                    # replay still matches the transcripts
```

The transcripts follow a real terminal: output wraps at the recorded width (120 columns), cursor moves count
wrapped rows, and wrapped rows are joined back into one line. To cross-check a capture against tmux, replay its
bytes into a 120-column pane and compare with `tmux capture-pane -p -J -S -`; every committed capture matches.

**The throwaway HOME.** For each path, `capture.py` deletes and recreates `/private/tmp/newcomer`, but only the
directory it created itself: a marker beside it (`/private/tmp/newcomer.capture-owned`) holds that directory's
device and inode. If the path exists without a matching marker (someone else's directory, or one replaced since),
or is a symlink, it refuses and deletes nothing. Remove such a directory yourself if it is disposable.

**The environment.** Every command (or the session shell) runs under `env -i` with only `HOME`, `PATH`
(`$HOME/.local/bin`, the claude directory, `/usr/bin:/bin:/opt/homebrew/bin`), `TERM` and `LANG`, plus
`PS1='$ '` for a session. `claude plugin marketplace add` works there without logging in.

**Revisions.** Every path installs or clones `main` as it is at capture time, and each folder records one revision
(`RECORDED` in `capture.py`). `capture.py` checks `main` with `git ls-remote` first and refuses to re-capture a
folder recorded at another revision, since that would replace the evidence, unless given `--new-revision`. If you
do, update `RECORDED` and rename the folder.

**Exit status.** It counts commands whose exit code differs from the recorded expectation. `from-source` expects
its `add .` step to fail, because that failure is what it records. A refusal exits 2.

## Render

```bash
npm ci --ignore-scripts                     # no install scripts are needed
npm run graph                               # src/graph.json from vault/ (needs gaiafield; committed, rerun only if vault/ changes)
npm run music                               # public/music/explainer-bed.wav from src/timeline.json
npm test && npm run typecheck
npm run render                              # out/explainer.mp4: 1920x1080 H.264 + AAC, 93 s
```

The first render downloads Chrome Headless Shell into `node_modules/.remotion/`. Labels are set in DIN Condensed
and terminal text in Menlo (both ship with macOS); elsewhere the fallback fonts change the look slightly.

Changing what the video says means editing `src/timeline.json`: the labels, and the scene and cue times the music
follows. Rerun `npm run music` after a time changes.

**Licence:** Remotion is free for individuals and companies of up to three people; larger companies need a
[company licence](https://www.remotion.dev/license).
