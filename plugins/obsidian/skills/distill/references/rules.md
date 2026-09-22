# Distillation Rules

## PARA placement logic

- **02_Projects** — direct application to active, specific-outcome work.
- **03_Areas** — ongoing responsibility maintenance, no end date.
- **04_Resources** — reference material for future use; the default when nothing more
  specific applies.
- **Never create new *knowledge* in 05_Archive.** No distilled note, concept, or
  synthesis is ever written there, and archived notes are never enriched or linked from
  active content. This is about content, not files — retiring a raw capture into
  `05_Archive/<Origin>-Captures-<YYYY-MM>/` is frozen provenance and
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

## Cluster mode (multiple captures → one hub, never one note)

**A synthesis never replaces the captures' own notes.** Measured 2026-09-22: five captures
merged into one 10 KB note kept 30 of 40 main points and 13 of 40 specifics (benchmark
figures, API details, the one number a reader comes back for), and 8 of 11 unanswerable
recall questions asked for exactly those. So:

- **One note per capture that has its own specifics** (a number, a mechanism, a worked
  example, a decision). It carries those specifics in full. A capture whose only unique
  contribution is its URL or a restatement is folded into the hub with its URL preserved.
- **One hub note for the cluster**: the shared principle, what each member adds in one
  line, and a link to every member note. The hub is where the enrichment of *other* notes
  points; the member notes are where the specifics live and are found.
- **The check before closing**: `distill_check.py` reports the capture's kept passages
  the note does not carry; a member note closes only when that list is empty or every
  miss is named in the handoff as deliberate.


When a batch holds several captures on one topic, one note per capture creates
near-duplicates that compete in search and dilute every score. Prefer a single
multi-source synthesis at `04_Resources/` root.

1. Read and judge **per capture**, not per cluster; decide the clustering at the
   checkpoint, after you know what is in each one.
2. The union of every constituent capture's substantive URLs must land in the one note.
3. **Uniqueness gate before writing:** for each capture, name at least one thing it
   contributes that no sibling in the cluster does. If a capture contributes nothing
   unique, say so explicitly in the Phase 1 handoff and record it as a deliberate merge
   — never drop it silently. A capture whose only unique contribution is its URL still
   gets that URL preserved.
   For a batch, `distill_judge.py`'s pairwise `cluster` block (does A add anything B
   lacks, asked both ways) is a first pass over exactly this question; you still name the
   unique contribution yourself.

Report the cluster's membership and each member's unique contribution in the Phase 1
handoff so the user can veto the grouping before anything is written.

## Enrichment rules

- Candidates: notes the dossier judged relevant (or, on the Python search path, at or
  above `search_score_gate`), in active folders only. Never enrich `05_Archive`; never
  link to `01_Capture/`.
- **L1 (default)**: a backlink in the note's Related section (create it if missing).
  **L2**: merge inline next to the specific sentence the new note extends, plus the L1
  backlink. **L3**: a contradiction callout adjacent to the contradicted claim, never a
  silent overwrite:

  ```markdown
  > [!warning] Contradicted by [[New Note]] (YYYY-MM-DD)
  > Brief summary of what changed.
  ```

  Each related note gets exactly one level; L2/L3 require the citable sentence.

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

Distill is conversational by design (the checkpoint), but even after
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
