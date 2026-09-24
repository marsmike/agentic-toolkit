# Explainer video

The agentic-toolkit explainer, rendered with [Remotion](https://www.remotion.dev) from **real captured CLI
output**. Terminal scenes replay the recorded bytes in `capture/`; nothing is retyped. No video, audio or
`node_modules/` is committed (`.gitignore`); the render is published as a release asset.

## Layout

| Path | What it is |
|---|---|
| `capture/record.py` | Records one command in a pseudo-terminal as asciicast v2 (`.cast`: output + timing). Stdlib only. |
| `capture/capture.py` | Runs the README newcomer commands in a clean, empty HOME and records each one. |
| `capture/cast_text.py` | Writes each capture's final screen as `.txt`: the verbatim text the storyboard quotes. |
| `capture/<path>/` | One folder per install path: `env.txt` (starting state, tool versions, source revision), `NN-<step>.cast`, `NN-<step>.txt`. |
| `src/cast.ts` | Replays a `.cast` into screen text (same rules as `cast_text.py`). |
| `src/Terminal.tsx`, `src/Root.tsx` | Remotion scenes. |
| `test/cast.test.ts` | Holds the replay and the `.txt` transcripts equal, capture by capture. |

## The captures

| Folder | Commands | Result (rev 72bb351) |
|---|---|---|
| `headline/` | README "New here" block, verbatim | All exit 0; the demo uses a 3-note temp vault (no checkout), so no `[INFERRED]` line |
| `from-source/` | README "From source" line, verbatim | Demo stops after step 1 (`[engines] not installed`); `claude plugin marketplace add .` is rejected |
| `from-source-fixed/` | From source + `uv run toolkit engines install`, `add ./` | All exit 0; 82 notes, 783 edges, 3 `[INFERRED]` lines. **The filmed path (decision D6)** |

`from-source-fixed` is not what the README says yet; the video labels it "From source · bundled example vault"
and shows the engines step. When the README is fixed, re-capture so the two agree.

## Re-capture

Needs `uv`, `git` and a `claude` binary. Only `claude` is taken from this machine, through a directory that
holds nothing else, so no installed `toolkit` can leak onto PATH:

```bash
mkdir -p /private/tmp/prereq-bin
ln -sf "$(readlink -f "$(command -v claude)")" /private/tmp/prereq-bin/claude
python3 capture/capture.py                  # all paths; or: capture.py from-source-fixed
npm test                                    # replay still matches the transcripts
```

`capture.py` **deletes and recreates `/private/tmp/newcomer`** for each path, then runs every command under
`env -i` with only `HOME`, `PATH` (`$HOME/.local/bin`, the claude directory, `/usr/bin:/bin:/opt/homebrew/bin`),
`TERM` and `LANG`. `claude plugin marketplace add` works there without logging in. The headline path installs
whatever `main` is at capture time; re-capture if `main` changes before publishing.

## Render

```bash
npm ci --ignore-scripts                     # no install scripts are needed
npm test && npm run typecheck
npm run render:capture                      # out/capture.mp4: the D6 path replayed, a pipeline check
```

The first render downloads Chrome Headless Shell into `node_modules/.remotion/`. The explainer composition
(one scene per storyboard scene, with music) is added once the storyboard is locked.

**Licence:** Remotion is free for individuals and companies of up to three people; larger companies need a
[company licence](https://www.remotion.dev/license).
