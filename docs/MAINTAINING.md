# Maintaining the toolkit

Two loops that improve the toolkit itself rather than a vault. They ran as skills until R12;
they are maintainer procedures, run from the repo root a few times a year, so they live here
and stay out of every session's skill list. [earned: 2026-09-23, R12 — 15 skills cut to six]
Their scripts are unchanged.

## Judgment calibration

Tunes the typed-judgment questions and golden labels behind distill's advisory block and the
radar. Run it after a question, backend or model change, when judgments look wrong in real runs,
or to grow the golden set. The backend answers narrow questions; a reasoning model reads each
disagreement, decides *why* it happened, and proposes the smallest fix, then a human reviews.

Mechanics: `plugins/obsidian/scripts/distill_judge.py --calibrate` (agreement, disagreements,
threshold sweep) and `--emit-golden-skeleton` (unlabelled rows). Full procedure and the cause
taxonomy: [maintaining/judgment-calibration.md](maintaining/judgment-calibration.md).

- **Two files may change:** `scripts/judgments/questions.py` (wording, plus a
  `QUESTIONS_VERSION` bump) and `evals/golden/distill_judge.golden.json` (labels). Never
  `THRESHOLDS` or any policy in `distill_judge.py`: report the sweep and let the human decide.
- **Classify the cause before proposing a fix**, and justify every wording change by that
  cause, never by the score alone.
- **No example-specific patches.** A criterion may not name a note, a title or a term from the
  row that failed. If the fix only works for that row, the cause is misdiagnosed.
- **Held-out rows stay unseen.** Run `--calibrate` without `--show-holdout`. A wording change
  ships only if held-out agreement does not drop.
- **Label blind.** Read the capture and the note and write `expect` *before* looking at the
  backend's `proposed` value.
- **A backend's answer is never a label.** A model's labels are `labelled_by: claude`,
  `strength: should`; only a human sets `labelled_by: human` or `strength: must`. A row labelled
  with the backend's answer in view is `labelled_by: claude-anchored`: its own split, never
  swept, never part of pass/fail.
- Runs against `./vault` (or a sandbox copy), needs a judgment key, writes no vault content,
  never runs in CI. Stop for review before anything is committed.

## Retrieval verification

Audits note descriptions: a description earns its keep only if a reader could predict the note's
content from title and description alone. Run it after a bulk distill or import. The predicting
and scoring are the agent's own reasoning, done blind to the body;
`plugins/obsidian/scripts/retrieval_verification.py` does the sampling and the report.
Why predict-then-score, BM25 dilution, sample sizes:
[maintaining/retrieval-verification.md](maintaining/retrieval-verification.md).

1. **Sample** N active notes, title and description only (the body is withheld on purpose):
   `uv run --project plugins/obsidian/scripts python3 plugins/obsidian/scripts/retrieval_verification.py sample --n 15 --json > samples.json`
2. **Predict, then read, then score**, per note, in that order: write what you expect the body
   to hold, only then read the note, and score 1–5 (5: the description leads straight to this
   content; 3: plausible but generic; 1: misleading, or says nothing the title did not). A note
   without a description is flagged automatically.
3. **Report**: build `{"<path>": {"score": N, "predicted": "...", "note": "why"}}` for every
   sampled path and run `… retrieval_verification.py report --samples samples.json --scores scores.json`.
   It writes `00_Memory/retrieval-verification/<timestamp>.json` and a summary capture in
   `01_Capture/`. A sampled path without a score writes a DLQ note instead of a report that
   looks complete.
4. **Rewrite flagged descriptions** (score < 3) by hand; the loop surfaces, it never rewrites.
