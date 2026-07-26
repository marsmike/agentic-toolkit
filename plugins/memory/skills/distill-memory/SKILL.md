---
name: distill-memory
description: On-demand — turn archived session records in 00_Memory/sessions/ into durable notes in 00_Memory/notes/. Two-phase review (propose, then confirm), idempotent on re-run. Use to distill or review session memory.
---

# distill-memory

Archived session records (`00_Memory/sessions/`, written automatically by this
plugin's SessionEnd hook) are raw material, not knowledge — a mechanical pointer plus
some tool/file tallies. This skill is the on-demand step that turns them into durable,
reusable memory: a small set of notes under `00_Memory/notes/` classified as **SOP**
(a reusable procedure), **warning** (a gotcha or failure mode to avoid), or **fact**
(a durable fact worth remembering), each carrying its own provenance back to the
session(s) it came from.

This is judgment work — done by you, the invoking agent, in the current turn. There is
no subprocess or background LLM call; that is deliberate (see
`../../README.md`'s mechanism-vs-content note on why v1's automatic summarizer isn't
ported).

## Quick start

> Distill session memory

1. List undistilled sessions: `distill_memory.list_undistilled_sessions(vault)`.
2. Run the two-phase workflow in `references/workflow.md`.
3. Write confirmed candidates via `distill_memory.write_memory_note(...)` — idempotent,
   see `references/schema.md`.

## Two-phase review — non-negotiable

Phase 1 (analyze) proposes and stops; Phase 2 (write) only runs after the user
confirms. Skip the checkpoint only on an explicit `--auto`/non-interactive
instruction. This is the same discipline `contract/templates/VAULT_CLAUDE.md` requires
of every vault-write workflow — see `references/workflow.md` for the full procedure.

## References

- `references/workflow.md` — the full two-phase procedure, classification guidance,
  and the ambiguous-case DLQ path.
- `references/schema.md` — frontmatter shapes for session records and memory notes.
