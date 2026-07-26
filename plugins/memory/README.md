# memory plugin

Session-end capture and on-demand distillation into vault memory. A `SessionEnd` hook
archives a lightweight, deterministic record of every session into
`00_Memory/sessions/`; the `distill-memory` skill later turns archived sessions into
durable, deduplicated notes in `00_Memory/notes/`, on demand, under the same
two-phase-review discipline every vault write follows.

## Mechanism vs. content

This plugin ships the **mechanism** only — where things get archived, what a session
record and a memory note look like, how idempotency works. It ships with **no
identity content**: no name, no persona, no "who I am" self-model, no fixed
communication channel or schedule. Your own agent identity — its name, its goals, its
voice — is yours to define in your own vault (or not at all; the hook and skill work
fine with none of that). Per `docs/PLAN.md`, that split is deliberate: identity
*content* belongs in a private vault/repo; a public plugin carries only the mechanics
that content would plug into.

Concretely: v1 of this plugin (`~/Developer/agentic-toolkit-legacy/memory`) carried a
full agent self-model — `00_Memory/self/identity.md`, `way-of-working.md`,
`self/goals.md` — plus a WhatsApp-delivered daily check-in cadence, all built around
one specific agent's persona. None of that ships here. See "Dropped, with reasons"
below for the itemized cut.

## What it does

| Component | Purpose |
|---|---|
| `hooks/` (`SessionEnd`) | Archives a deterministic session record — project, human-turn count, a tool-usage tally, files touched, a transcript pointer — into `$VAULT/00_Memory/sessions/`. No LLM call; "zero-cost" in the literal sense of no API spend. |
| `skills/distill-memory` | On demand, turns undistilled session records into classified (`sop`/`warning`/`fact`) notes under `$VAULT/00_Memory/notes/`, via the same analyze-then-confirm two-phase discipline `contract/templates/VAULT_CLAUDE.md` requires of every vault write. |

## Hook behavior and no-op conditions

The `SessionEnd` hook (`hooks/session-end.sh` → `hooks/lib/session_capture.py`) is
stdlib-only Python — no `pip`/`uv` dependency, no `jq`, nothing beyond `python3` on
PATH — so it can never fail merely because a venv wasn't set up.

- **No vault resolvable** (`TOOLKIT_VAULT` env var unset and `./vault` doesn't exist
  relative to the repo root, per `contract/PROFILE.md`) → **silent no-op**. A hook
  must never nudge, warn, or error for a user who hasn't configured a vault.
- **Fewer human turns than `min_human_turns_to_archive`** (default `1`, see
  `profile.example.md`) → no-op; trivial sessions aren't archived.
- **Any other failure** (unreadable transcript, unwritable vault, a bug) → a DLQ note
  under `$VAULT/00_Memory/dlq/` instead of raising, and the hook still exits `0`. A
  hook that raises breaks the session it's attached to; that's worse than losing one
  archive.

## Dead-letter queue

`00_Memory/dlq/` — same convention `plugins/obsidian` established (`description`/
`status`/`created`/`confidence` frontmatter, a "What happened / Why it's here /
Resolution" body). Two writers: the SessionEnd hook (a capture failure) and the
`distill-memory` skill (a candidate it can't confidently classify or place). `toolkit
doctor` (in `core/`) surfaces the count, same as for `plugins/obsidian`.

## Profile

Reads `$VAULT/Config/toolkit/memory.md` per `contract/PROFILE.md`. See
`profile.example.md` for the exact shape (`min_human_turns_to_archive`,
`max_transcript_bytes`, `default_tags`) and what each field controls. No profile note
is a normal, fully-functional state — every field falls back to a shipped default.

## Dependencies

None. `scripts/memory_vault.py` hand-rolls the narrow, flat-scalars-and-lists subset
of YAML frontmatter this plugin ever reads or writes, rather than depending on
PyYAML — deliberately, so the hook path never needs a venv. No `pyproject.toml`, no
optional extras. `evals/eval_codec_parity.py` imports `pyyaml` for one cross-check
against `yaml.safe_load` — dev-only, and only in the eval — and degrades to a
pass-with-detail (not a failure) if `pyyaml` isn't installed.

## What changed vs. v1 (`~/Developer/agentic-toolkit-legacy/memory`)

### Ported and generalized

- **`hooks/session-end.sh` → SessionEnd capture** — kept the "archive on session end"
  behavior; dropped the `claude -p` subprocess call v1 used to produce an LLM summary
  automatically, on every session end, with no user in the loop (recursion guards,
  idle-debounce locking, a hard-coded `$0.10` per-call budget). An automatic, silent
  LLM spend baked into a hook is exactly the kind of surprise this port removes —
  archiving is now purely mechanical (turn counts, tool tally, files touched, a
  transcript pointer), and the judgment work moved to the on-demand
  `distill-memory` skill, run in a normal agent turn with no subprocess.
- **v1's SOP/Warning/Fact classification** (from its `MEMORY.md` distillation
  design) — kept as `distill-memory`'s `kind: sop|warning|fact` field; this is a
  useful, generic taxonomy independent of any specific agent's persona.
- **`commands/journal.md`'s format** — the `- [HH:MM] project | summary` shape (with
  optional `learned`/`friction`/`decided`/`sources` sub-bullets) already matches the
  vault's own established convention (`00_Memory/README.md` in the example vault).
  Folded into `scripts/memory_vault.append_journal_line()`, called from
  `distill-memory`'s Phase 2 — not kept as a standalone command; appending one line
  doesn't earn its own skill slot (see Osmani scope test, `docs/PLAN.md`).
- **`skills/pipeline`'s consolidate-and-decide idea** (`commands/think.md`'s
  Phase 2: check if already captured → ADD/UPDATE/DELETE/NOOP) — the underlying
  new-vs-update-vs-no-op decision generalizes directly into `distill-memory`'s
  idempotent write step (`write_memory_note`'s no-op-on-repeat, update-on-new-source
  behavior). The rest of that command (WhatsApp, German status messages, P3/C3
  judgment pipeline) did not survive — see below.

### Dropped, with reasons

| Component | Reason |
|---|---|
| `hooks/stop.sh` + the idle-debounce half of `hooks/lib/dispatch.py` | Built entirely to work around a hook-timeout limitation (spawning a detached `nohup` background process that polls for session idleness, then calls `claude -p`). With the automatic LLM-summarizer call removed (see above), there is nothing left for a Stop-time debounce to gate — `SessionEnd` alone covers deterministic archiving. |
| `hooks/session-start.sh` (the "`/memory-orient` available" nudge) | An unconditional stdout hint on every session start, gated on a personal `OBSIDIAN_VAULT_PATH` env var. The vault's own `00_Memory/README.md` already documents the orientation protocol for any agent that opens it; a second hook whose only job is printing a pointer to a command this port doesn't ship added noise without a clear owner. |
| `commands/memory-orient.md` | Reads a fixed list of persona files (`self/identity.md`, `way-of-working.md`, `self/goals.md`) that this port doesn't ship (see next row) — the command has nothing left to orient into. |
| `skills/memory/` (`self/identity.md`, `way-of-working.md`, `self/goals.md`, `self/strengths.md`, `self/interests.md`, `self/questions.md`, `self/budget.md`, `reflections/`) | This *is* the agent-identity content the mechanism/content split exists to keep out of a public plugin (`docs/PLAN.md`) — not a mechanism to generalize, the content itself. Stays in the private vault/repo. |
| `commands/evening.md` (WhatsApp evening check-in) | Hard-coded to a WhatsApp delivery channel (a separate, private-repo plugin per `docs/PLAN.md`), a German-language personal tone, and the Silfen Path pipeline (next row). No channel-agnostic mechanism survives independent of those three. |
| `commands/think.md` (daily thinking phase) | Same WhatsApp/German-tone dependency as `evening.md`, plus the Silfen Path P3/C3 judgment pipeline (next row). Its one generalizable idea (consolidate-then-decide) is folded into `distill-memory`, see above. |
| `skills/pipeline/*` (the "Silfen Path" note-maturity system: `judge_p3`, `promotion`, `archive`, `schema`, evening-render `modes.md`) | A distinct, opinionated note-lifecycle methodology (seedling/developing/evergreen, P3/C3 judgments) — not session-memory behavior. `plugins/obsidian/README.md` drops its own copy of this exact system for the same reason ("can't be named as what the [plugin] delivers"); candidate for its own plugin if it earns readmission later. |

## Evals

`evals/run.py` runs three R0 capability evals against `./vault`, emitting JSON
`{eval, pass, detail}` per check:

| Eval | Asserts |
|---|---|
| `session_capture` | `hooks/lib/session_capture.capture_session()`, given a fixture transcript, produces a schema-conformant note in `00_Memory/sessions/` (required frontmatter fields, correct turn count, tool names present in the body) |
| `distill_idempotent` | `distill_memory.write_memory_note()` is idempotent: an identical `(slug, source)` call twice is byte-for-byte unchanged after the second call; a genuinely new source for the same slug updates the same note in place rather than duplicating it |
| `codec_parity` | `memory_vault`'s hand-rolled frontmatter codec round-trips unknown fields, unicode, and a colon-in-value string unchanged (cross-checked against `yaml.safe_load` when `pyyaml` is available), and raises `ValueError` — per its documented codec contract — instead of silently mis-parsing a nested mapping or a `\|` block scalar |

Every eval here writes, so every eval runs against a throwaway copy
(`evals/_sandbox.py`) — the real `./vault` is never touched. If `./vault` doesn't exist
yet, `run.py` exits `2` with a `corpus not present` detail on every eval rather than
crashing.

```bash
python3 evals/run.py --json
```
