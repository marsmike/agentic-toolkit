---
name: judgment-calibration
description: Tune the typed-judgment questions and golden labels behind distill's advisory judgments. Use after a questions or backend/model change, when advisory judgments look wrong in real distill runs, or to grow the golden set from new captures.
allowed-tools:
  - Bash
  - Read
  - Edit
---

# Judgment Calibration

The typed-judgment backend answers narrow questions fast and cheaply; it does not write
them. You do: a reasoning model reads each disagreement, decides *why* it happened, and
proposes the smallest fix. This is an **agent-executed workflow with a human checkpoint**,
the same shape as distill's Phase 1.

Mechanical halves: `scripts/distill_judge.py --calibrate` (agreement, disagreements,
threshold sweep) and `--emit-golden-skeleton` (unlabelled rows). Full procedure and the
cause taxonomy: `references/workflow.md`.

## Hard requirements

- **You may edit two files:** `scripts/judgments/questions.py` (wording, plus a
  `QUESTIONS_VERSION` bump) and `evals/golden/distill_judge.golden.json` (labels). Never
  `THRESHOLDS` or any policy in `distill_judge.py`: report the sweep and let the human decide.
- **Classify the cause before proposing a fix**, and justify every wording change by that
  cause, never by the score alone.
- **No example-specific patches.** A criterion may not name a note, a title or a term from
  the row that failed. If the fix only works for that row, the cause is misdiagnosed.
- **Held-out rows stay unseen.** Run `--calibrate` without `--show-holdout`. A wording
  change ships only if held-out agreement does not drop.
- **Label blind.** When labelling new rows, read the capture and the note and write
  `expect` *before* looking at the backend's `proposed` value.
- **A backend's answer is never a label.** Your labels are `labelled_by: claude`,
  `strength: should`. Only a human sets `labelled_by: human` or `strength: must`.
- Runs against `./vault` (or a sandbox copy), needs a judgment key in the environment,
  writes no vault content, never runs in CI. Stop for review before anything is committed.
