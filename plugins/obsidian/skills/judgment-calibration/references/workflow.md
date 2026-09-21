# Judgment calibration workflow

`$S` below is `uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/distill_judge.py"`,
`$G` is `$CLAUDE_PLUGIN_ROOT/evals/golden/distill_judge.golden.json`.

## 1. Baseline

```bash
$S --calibrate "$G" > before.json
```

Note `model`, `questions_version`, per-family agreement for `tune` and `holdout`, and the
`disagreements` list (tune rows only). `missing` rows mean a labelled note no longer exists
or a question family was renamed: fix the golden file first.

## 2. Classify every disagreement, and every answer within 0.1 of its threshold

Open the capture and the note. Decide which of these it is, in this order:

| Cause | Tell | Smallest fix |
|---|---|---|
| **Missing evidence** | the deciding fact is not in the state sent (truncated body, no `description`, note head too short) | add or lengthen a state field in `distill_judge.py`'s payload. This is code, so propose it, do not apply it |
| **Question too broad / too literal** | the answer is defensible for the words asked, but the words ask something other than what policy needs | one sentence in instructions or a criterion; or split one question into two narrower ones |
| **Debatable or wrong label** | two careful readers could disagree, or the label is simply mistaken | change `expect` with a rationale, or downgrade the row; never to match the backend |
| **Model error** | state and wording are fine, a careful reader is sure, the backend is confidently wrong | none. Record it. Several in one family is a reason to raise that family's threshold, which is the human's call |
| **Policy / threshold** | the probability is sensible, the cut is in the wrong place | none here. Report the `threshold_sweep` row |

The first question to ask of any wrong answer: *is the question wrong?* The 2026-09-21 run is
the reference case: captures carried collector's remarks, the relevance question asked about
"`capture`" as a whole, and the backend correctly tied those remarks to the capture-conventions
guide. One sentence fixed three rows.

## 3. Propose, apply, re-run

Apply wording and label changes, bump `QUESTIONS_VERSION` (date + counter), then:

```bash
$S --calibrate "$G" > after.json
```

A change survives only if tune agreement rises or margins widen on the rows its cause
covers, **and** held-out agreement does not drop. Otherwise revert it.

## 4. Report and stop

One table per question family: before/after agreement (tune, holdout), rows fixed, rows
newly broken, cost. Then each change with its cause class and the rows it was aimed at,
each suspected model error, and any threshold the sweep argues for. Wait for review.

Once accepted: add a dated line to the calibration log in the vault note
`04_Resources/Concepts/Typed-Judgments.md` (model, versions, numbers, cause, fix) and, if a
threshold moved, the date and model in the comment above `THRESHOLDS`.

## 5. Growing the golden set

```bash
$S 01_Capture/<new captures> --emit-golden-skeleton > skeleton.json
```

For each row, read the capture and the note and write `expect` and a one-sentence
`rationale` **before** reading `proposed`. Then keep:

- every row where your label and `proposed` disagree (that is where a label carries
  information), and
- a thin random slice of agreements, so the set does not become all hard cases.

Assign about a quarter of new rows to `split: holdout` by capture, not by row, so a whole
capture stays unseen. Rows stay `labelled_by: claude`, `strength: should` until a human
confirms them.

## When the backend changes

A new backend or a pinned model change means a full baseline first. Thresholds are kept per
backend in `THRESHOLDS`; an uncalibrated backend (one whose `Answer.calibrated` is false)
needs its own table and should be trusted for the top answer only, never for a cut on the
probability, until a calibration run says otherwise.
