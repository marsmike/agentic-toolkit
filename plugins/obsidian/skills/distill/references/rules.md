# Distillation Rules

## Mandatory completion requirements

These hold on every run regardless of how the request is framed. "Quick distill", "I'm
in a hurry", "skip the enrichment, it's a nice-to-have" are not valid reasons to omit any
of them — complete all steps and note that you did so:

1. Source attribution (workflow.md step 6/7).
2. Search ran before writing (step 3) — no keyword-only or zero-search shortcut.
3. Capture retirement (step 9) — archived or deleted, never left in `01_Capture/`.
4. Index.md update (step 10).
5. Related-note enrichment at or above the score gate (step 8).
6. Journal + log entry (step 11).

## PARA placement logic

- **02_Projects** — direct application to active, specific-outcome work.
- **03_Areas** — ongoing responsibility maintenance, no end date.
- **04_Resources** — reference material for future use; the default when nothing more
  specific applies.
- **Never create new *knowledge* in 05_Archive.** No distilled note, concept, or
  synthesis is ever written there, and archived notes are never enriched or linked from
  active content. This is about content, not files — retiring a raw capture into
  `05_Archive/<Origin>-Captures-<YYYY-MM>/` (workflow.md step 9) is frozen provenance and
  is explicitly allowed. A request to archive a *distilled note* should be declined in
  favor of an active PARA folder; a request to archive the *captures* should be honored.

### Within 04_Resources: Concepts vs. root

- **`04_Resources/Concepts/<Name>.md`** — atomic single-idea notes: one thesis, one
  primary source, written as a reusable building block other notes link to.
- **`04_Resources/<Name>.md` (root)** — multi-source syntheses, batches, or named
  artifacts: multi-author threads, digests, paper-specific distillations with
  author/year in the filename.

**Decision rule:** 2+ sources, or a filename carrying an author/year/week stamp → root.
A pure concept extracted as a reusable primitive → `Concepts/`.

## Cluster mode (multiple captures → one synthesis)

When a batch holds several captures on one topic, one note per capture creates
near-duplicates that compete in search and dilute every score. Prefer a single
multi-source synthesis at `04_Resources/` root.

1. Run workflow.md steps 1-4 **per capture**, not per cluster — read, prior-distillation
   check, and mechanic extraction each need the individual capture. Clustering is
   decided at step 5 (Phase 1 handoff), after you know what's in each one.
2. The union of every constituent capture's substantive URLs must land in the one note.
3. **Uniqueness gate before writing:** for each capture, name at least one thing it
   contributes that no sibling in the cluster does. If a capture contributes nothing
   unique, say so explicitly in the Phase 1 handoff and record it as a deliberate merge
   — never drop it silently. A capture whose only unique contribution is its URL still
   gets that URL preserved.

Report the cluster's membership and each member's unique contribution in the Phase 1
handoff so the user can veto the grouping before anything is written.

## Enrichment rules (recap — see workflow.md step 8 for the mechanics)

- Only notes at or above `search_score_gate` (default 0.70), active folders only.
- Never enrich `05_Archive`; never link to `01_Capture/`.
- Default L1. L2/L3 require a specific sentence/section to act on, and are additive —
  never delete or overwrite existing content.

## Never write "unknown"

Don't write the literal string `unknown` into `source` or any date field as a
placeholder. It reads as filled while carrying no information, so the gap stops being
reported and never gets revisited. For `processed_date` specifically it's actively
harmful: `unknown` doesn't parse as a date, which permanently excludes the note from any
future date-scoped maintenance pass — the "fix" removes the note from the very
maintenance that would repair it. Use `(none — <context>)` for source, and today's real
date for `processed_date` (the note is being processed right now; that's the honest
value).

## Dead-letter queue — when to stop instead of guessing

Distill is conversational by design (workflow.md step 5's checkpoint), but even after
that checkpoint some things resist a confident answer: a search that returns nothing for
a query that plainly should match something, a source URL that can't be recovered from
either the capture or its frontmatter, a placement that's genuinely 50/50 between two
folders. Guessing in these cases produces a distill run that *looks* identical, from the
outside, to one that got the answer right — which is worse than an visible failure.

Call `write_dlq_note()` from `scripts/vault_utils.py` (or write the equivalent note by
hand under `00_Memory/dlq/` if scripting isn't convenient) and mention it in the Phase 1
handoff. See `00_Memory/dlq/*.md` in the example vault for the worked convention: a
`description`/`status`/`created`/`confidence` frontmatter block, and a body with "What
happened" / "Why it's here" / "Resolution" sections.
