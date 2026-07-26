# distill-memory — note schemas

Both schemas use only the flat scalars/lists `scripts/memory_vault.py`'s codec
supports. Fields beyond this table are tolerated on read (floor, not ceiling, per
`contract/VAULT_SCHEMA.md`) but this plugin never writes any others itself.

## Session record — `00_Memory/sessions/<date>-<project>-<session-id-prefix>.md`

Written automatically by the SessionEnd hook. One per session that met the
`min_human_turns_to_archive` threshold (default 1 — see `profile.example.md`).

| Field | Meaning |
|---|---|
| `description` | One-line: project + turn count |
| `kind` | Always `session` |
| `status` | Always `archived` |
| `created` | Date the session ended |
| `source` | Absolute path to the raw transcript JSONL (pointer, not copied in) |
| `session_id` | The session's id, as given by the hook payload |
| `project` | `cwd`'s directory name at session end |
| `end_reason` | The hook payload's `reason` field, verbatim |
| `turns` | Human-turn count (mechanical count, not a judgment) |
| `distilled` | `false` until `distill-memory` has processed it; then `true` |
| `tags` | `[agent/session, domain/toolkit-meta]` |

Body: a first-message snippet, a tool-usage tally, and a files-touched list — all
extracted mechanically, no LLM involved. Never rewritten except to flip `distilled`.

## Memory note — `00_Memory/notes/<slug>.md`

Written/updated by `distill_memory.write_memory_note()`. One per distilled lesson;
`slug` is the lesson's stable identity, not tied to any one session.

| Field | Meaning |
|---|---|
| `description` | The lesson, one line |
| `kind` | `sop` \| `warning` \| `fact` |
| `status` | Always `active` (this plugin never archives a memory note itself) |
| `created` | Date first distilled |
| `updated` | Date a new source most recently confirmed this lesson |
| `sources` | List of `00_Memory/sessions/*.md` paths that produced/confirmed this |
| `tags` | Defaults to `[agent/memory, domain/toolkit-meta]`; override via `tags=` |

Body: the lesson itself, written to be useful on its own — a future session reading
this note shouldn't need to open the sources to understand it.

## Idempotency contract

`write_memory_note(vault, kind, slug, title, body_text, source, today=...)` called
twice with an identical `(slug, source)` pair is a byte-for-byte no-op on the second
call — this is what `evals/eval_distill_idempotent.py` asserts, and what makes
re-running Phase 2 on the same confirmed candidates safe.
