# handoff plugin

Portable, tool-agnostic session handoff: save the context of the work you're doing so a
**new session, another machine, or another tool** (Codex, Gemini) can pick it up without
you re-explaining anything.

## Why

`CLAUDE.md` / `AGENTS.md` hold *stable* project context. They don't hold the *volatile*
"what I'm doing right now, what I tried, the exact next step" — the thing you lose when
you stop mid-task or context compacts. That's what this plugin captures.

## Two-layer storage model

- **Full handoff, in-repo** — `_handoff/HANDOFF-<stream>-NN.md` in the current repo
  (travels with the code; any tool reads plain markdown). `_handoff/HANDOFF.md` always
  points at the latest. This layer needs no vault at all — save and resume work fully
  in-repo with `TOOLKIT_VAULT` unset and no `./vault` present.
- **Cross-project discovery index, in the vault** — one line appended to
  `$VAULT/<index_path>` (default `00_Memory/handoffs/index.md`), only when a vault is
  resolvable per `contract/PROFILE.md` (`TOOLKIT_VAULT` env var, else the bundled
  `./vault`). No vault resolvable → the append is silently skipped; this is a normal,
  fully-functional state, not a degraded one.
- **Auto-snapshot safety net** — a `PreCompact` hook dumps git state to
  `_handoff/.autosnapshot.md` right before context compaction, so nothing volatile is
  lost if you forget to save. Gated by the profile's `autosnapshot` field.

## What it does

| Component | Purpose |
|---|---|
| `skills/handoff` | Save mode — writes the narrative to `_handoff/.draft.md`, then runs the script to assemble frontmatter, git state, chain link, and the vault index line. |
| `skills/handoff-resume` | Resume mode — prints the latest handoff (and any newer auto-snapshot) for a fresh session to orient from. |
| `commands/handoff.md`, `commands/handoff-resume.md` | Thin slash-command entry points, each pointing at its skill — same pattern `plugins/readwise/commands/` uses. |
| `hooks/` (`PreCompact`) | Auto-snapshot git state before context compaction. |
| `scripts/handoff.py` | All deterministic mechanics: repo resolution, git state, chain sequencing, vault resolution, profile reads, the vault index, and the DLQ. |

## Vault resolution

`TOOLKIT_VAULT` environment variable, else `./vault` relative to the toolkit repo root
(`contract/PROFILE.md`). This is **independent** of the project-repo resolution used for
`_handoff/` itself (`$CLAUDE_PROJECT_DIR`, else git's own top-level) — a handoff lives in
the repo being worked on, which is almost never the agentic-toolkit repo. Tests and
evals always target `./vault` regardless of `TOOLKIT_VAULT`; a real vault reached via
that env var is never touched by this plugin's own eval suite.

## Profile

Reads `$VAULT/Config/toolkit/handoff.md` if present, per `contract/PROFILE.md`'s "fill
from Obsidian" convention. See `profile.example.md` for the exact frontmatter shape
(`autosnapshot`, `index_path`, `default_visibility`) and what each field controls. Every
field also has a `TOOLKIT_HANDOFF_<FIELD>` environment variable that overrides the note.
No profile note is a normal, fully-functional state — every field falls back to its
shipped default.

## Frontmatter decision — no general codec shipped

`plugins/obsidian`, `plugins/readwise`, and `plugins/memory` each ship a `vault_utils`/
`memory_vault` module with a general `read_frontmatter()`/`write_frontmatter()` pair:
parse any note's frontmatter, preserve unknown fields, write it back. That pattern
exists because those plugins read-and-rewrite *arbitrary* vault notes and must never
drop a field they didn't touch (`contract/VAULT_SCHEMA.md`'s "floor, not ceiling" rule) —
and `core/tests/test_contract.py`'s
`test_core_and_plugin_frontmatter_implementations_agree` exists specifically to keep
those independent reimplementations from drifting apart.

`scripts/handoff.py` genuinely does not need that. It only ever reads 3 known, flat,
scalar fields (`autosnapshot: bool`, `index_path: str`, `default_visibility: str`) out of
its own profile note, and **never writes back to it**. There is no unknown-field
preservation obligation, no list or nested-mapping support to get right, and no
write-back to round-trip — the entire justification for the general codec's complexity
is absent. `_read_profile_scalars()` is a ~25-line targeted line scan, not a frontmatter
parser, and is documented as such at its call site — its supported subset is one flat
`key: value` per line, an optional single pair of matching quotes around the value, and an
optional trailing `# comment` (stripped, unless it falls inside those quotes, in which case
it's kept as data). The individual `HANDOFF-*.md` files
this plugin writes carry their own small, fixed frontmatter shape (`stream`/`seq`/
`prev`/`title`/`date`/`repo`/`branch`/`tool`) that the script only ever *constructs*
fresh — it never reads an existing handoff file's frontmatter back in (chain sequencing
comes from the filename, not the frontmatter; `resume`/`list` treat a handoff file as
opaque text plus two `re.search` calls for display purposes).

**Consequently, `core/tests/test_contract.py`'s parity loop is not extended.** There is
no second `read_frontmatter()` implementation here to keep in sync with — extending the
loop to include a plugin with nothing comparable to compare would be test-suite noise,
not coverage.

## Dead-letter queue

`00_Memory/dlq/` via `scripts/handoff.py`'s `write_dlq_note()` — same convention
`plugins/obsidian`, `plugins/readwise`, and `plugins/memory` use (`description`/
`status`/`created`/`tags`/`confidence` frontmatter, a "What happened / Why it's here /
Resolution" body). Two triggers, both "a failure that would otherwise silently lose or
hide something":

1. **`_handoff/` is unwritable** (permissions, full disk, …) — the save would silently
   lose the handoff narrative entirely. If a vault is resolvable, a DLQ note is written
   with the narrative embedded in its body (so nothing is lost) and the script exits
   non-zero; if no vault is resolvable either, there's nowhere durable to record it, so
   the narrative is printed back to the user on stderr instead.
2. **The vault index append fails despite a resolvable vault** (the index's directory is
   unwritable, disk full, …) — the primary handoff already saved successfully, so this
   is not a total failure, but a silent no-op here would be indistinguishable from "no
   vault configured," hiding a real misconfiguration. A DLQ note records the attempted
   index path and the error; the save's own stdout reports `Vault index: FAILED` rather
   than pretending it succeeded.

No vault resolvable at all is **not** a DLQ case for the index — that's the documented,
normal degrade path (`contract/PROFILE.md`).

## Cross-tool (Codex / Gemini)

The handoff is plain markdown with no Claude-specific format. Point another CLI at
`_handoff/HANDOFF.md`, or symlink `AGENTS.md → _handoff/HANDOFF.md` in a repo where you
routinely switch tools, so Codex and Gemini pick it up automatically on startup.

## Dependencies

None. `scripts/handoff.py` is stdlib-only Python (`argparse`, `subprocess`, `re`,
`pathlib`, `datetime`) — no `pyproject.toml`, no `uv` project, matching
`plugins/memory`'s "the hook path must never need a venv" reasoning: the `PreCompact`
hook shells out to this same script.

## What changed vs. v1 (`~/Developer/agentic-toolkit-legacy/handoff`)

v1 was already lean, tool-agnostic, and carried no persona-specific content — unlike
`readwise`/`memory`, there is no large dropped-components table here.

### Ported and adapted

- `scripts/handoff.py` — same core mechanics (git-state capture, chain sequencing by
  filename regex, `save`/`resume`/`list`/`snapshot` subcommands), plus new vault
  resolution (`OBSIDIAN_VAULT_PATH` → `TOOLKIT_VAULT`/`./vault`, `contract/PROFILE.md`),
  a profile reader (`autosnapshot`, `index_path`, `default_visibility`), and the DLQ
  writer (see above).
- `skills/handoff` (save) and `skills/handoff-resume` — v1 bundled both modes into one
  skill; split into two here to match this repo's convention of one skill per mode of
  use, with the narrative template kept nearly verbatim in `references/template.md` (it
  was already good) and the deeper procedure detail (listing, cross-tool notes,
  auto-snapshot, chain integrity) moved to `references/workflow.md` to keep `SKILL.md`
  itself lean.
- `commands/handoff.md`, `commands/handoff-resume.md` — kept as thin slash-command
  wrappers pointing at the skills, rewritten to the one-line `Use the
  <plugin>:<skill> skill.` shape `plugins/readwise/commands/` established, rather than
  duplicating the skill's own instructions.
- `hooks/precompact.sh` + `hooks/hooks.json` — kept the thin-bash-launcher shape;
  `snapshot` now checks the `autosnapshot` profile field before writing, is
  byte-bounded, degrades silently with no project repo, and records a failure to the
  DLQ instead of raising or printing to stderr — the `plugins/memory` `SessionEnd` hook
  standard, applied to `PreCompact`.
- Vault index — v1 appended a bare `- {date} [{stream} seqN] {repo} → path` line only
  when `$OBSIDIAN_VAULT_PATH` was set. Kept append-only and one-line-per-handoff; the
  line now also carries the title (point 4 of the port brief) and the file gets a
  one-time frontmatter header on first creation, matching `00_Memory/journal/`'s
  established convention in the example vault.
- `author` in `plugin.json` — v1 carried a personal name and email; replaced with
  `agentic-toolkit contributors`, matching `plugins/readwise`/`plugins/memory`.

### Dropped

Nothing substantive. v1's `commands/` were kept (see above, rewritten thin rather than
dropped); there was no persona, no vendored environment variable beyond the vault path,
and no component that failed the admission bar on its own merits.

## Evals

`evals/run.py` runs three capability evals, emitting JSON `{eval, pass, detail}` per
check — no network calls:

| Eval | Asserts |
|---|---|
| `save_resume_roundtrip` | A `save` followed by a `resume` preserves the narrative text and the save output reports the correct `_handoff/HANDOFF.md` latest pointer; a copy of this repo's own pre-existing legacy-format handoff file (`_handoff/HANDOFF-toolkit-rebuild-01.md`, written by the v1 script) also resumes cleanly, confirming the new script stays read-compatible with files the old one wrote |
| `chain_sequencing` | A second `save` on the same stream tag gets `seq: 2` with `prev:` and a rendered `follows` link back to `seq: 1` |
| `dlq_index_append_failure` | An index-append failure against a resolvable-but-unwritable index path writes a DLQ note under `00_Memory/dlq/`, while the handoff save itself still succeeds |

Every eval runs against a throwaway sandbox **repo** (never this repo's own `_handoff/`)
and a throwaway sandbox **vault copy** (never `./vault` itself, never a `TOOLKIT_VAULT`-
resolved real vault) — see `evals/_sandbox.py`. If `./vault` doesn't exist yet, `run.py`
exits `2` with a `corpus not present` detail on every eval rather than crashing.

```bash
python3 evals/run.py --json
```
