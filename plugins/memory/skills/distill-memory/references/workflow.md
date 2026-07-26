# distill-memory — workflow

## Phase 1: Analyze (read-only, always runs first)

1. Call `distill_memory.list_undistilled_sessions(vault)` — every note under
   `00_Memory/sessions/` without `distilled: true`.
2. For each session record: read its frontmatter (project, turns, first-message
   snippet) and, when the record alone isn't enough to judge, read the transcript at
   its `source` field directly. The record is a pointer, not a substitute for the
   transcript — don't classify a learning from the tool tally alone if the actual
   exchange matters.
3. For each candidate learning found, decide:
   - **Classification** — `sop` (a reusable how-to worth repeating verbatim next
     time), `warning` (a mistake, trap, or silent failure mode worth avoiding), or
     `fact` (a durable fact about the project/environment/tooling, not a procedure).
   - **Slug** — derive from the *learning's topic*, not the session (e.g.
     `uv-run-project-flag-required`, not `session-2026-07-26-abc123`). The slug is
     the note's stable identity across sessions — this is what makes distillation
     idempotent: the same lesson learned twice lands on the same note.
   - **New vs. update** — check whether `00_Memory/notes/<slug>.md` already exists.
     If it does and this session confirms the same lesson, this is an update (new
     `source`, not a new file). If it contradicts an existing note, flag it — do not
     silently overwrite (mirrors `contract/templates/VAULT_CLAUDE.md`'s enrichment
     rule: never a silent overwrite).
4. Present the full candidate list (slug, kind, title, new-or-update, source) and
   **stop**. Do not write anything in this phase.

Skip the stop only under an explicit `--auto`/non-interactive instruction from the
caller — the same exception `contract/templates/VAULT_CLAUDE.md` carves out for
distillation generally.

## Phase 2: Write (after confirmation)

For each confirmed candidate:

1. `distill_memory.write_memory_note(vault, kind, slug, title, body_text, source)`.
   Idempotent by `(slug, source)` — re-running Phase 2 on the same candidates is safe
   and produces no duplicate files or duplicate `sources` entries.
2. `distill_memory.mark_session_distilled(session_path)` on every session record that
   contributed at least one candidate this run. Never delete a session record — it's
   the provenance trail a memory note's `sources` field points back to.
3. Append one line to today's journal via `memory_vault.append_journal_line(vault, entry)`,
   in the vault's existing journal format (`00_Memory/README.md`):

   ```
   - [HH:MM] memory-distill | Distilled N session(s) into M note(s): slug-one, slug-two
   ```

   This is v1's `/journal` command's format, folded in here rather than kept as a
   separate skill (see `../../README.md`'s dropped-components table) — a plugin whose
   only job would be appending one line doesn't earn its own admission slot.

## Ambiguous cases

If a candidate can't be confidently classified, or an existing note's slug seems to
fit but the content genuinely conflicts, don't guess: call
`memory_vault.write_dlq_note(vault, slug=..., title=..., what_happened=..., why_recorded=...)`
instead of forcing a placement. Leave the session record undistilled so it's picked up
again next run.

## What this skill does not do

- No automatic/background invocation — this is deliberately on-demand, run when a
  user or agent asks for it. v1's automatic `claude -p` subprocess summarizer is not
  ported (see `../../README.md`).
- No note-maturity lifecycle (promotion/archival/TTL judgments) — that's a distinct,
  opinionated methodology out of scope here, same reasoning `plugins/obsidian/README.md`
  gives for dropping its own `scripts/pipeline/*`.
