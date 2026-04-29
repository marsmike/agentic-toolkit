# Design Brief Schema

The inferred-at-step-1 artifact that captures message architecture for a deck. Canonical JSON schema: [`../lib/design_brief.schema.json`](../lib/design_brief.schema.json).

## Example

```json
{
  "$schema": "feinschliff/design-brief/v1",
  "takeaway": "Polish time collapsed from 3 hrs to 15 min per deck",
  "audience": "exec",
  "audience_notes": "Time-poor, outcomes-driven; will stop listening after 30s of buildup.",
  "frame": "sparkline",
  "frame_rationale": "Vision pitch oscillating painful present with desirable future; PSSR rejected because there's no discrete 'search' phase.",
  "hook": {
    "technique": "contrast",
    "opener": "Five years ago this took a week. Today it takes 15 minutes."
  },
  "red_line": "Pain → Solution demo → Results → What this unlocks.",
  "slides": [
    {
      "index": 0,
      "role": "hook",
      "claim": "Polish time has collapsed — here's why that matters.",
      "audience_fit": "Lead with impact; skip architecture for exec."
    }
  ]
}
```

## Field-by-field

### `takeaway`

The single sentence Mike wants the audience to walk away repeating. Top of the Minto Pyramid. One deck → one takeaway.

### `audience` + `audience_notes`

`audience` is one of `exec | manager | developer | peer`. `audience_notes` is the inferred rationale — what they care about, what loses them. Both drive step-2 claim wording and step-4 audience-mismatch checks. See `audience-calibration.md`.

### `frame` + `frame_rationale`

`frame` is one of `scqa | pssr | sparkline | man-in-hole`. `frame_rationale` MUST name the runner-up frame and why it was rejected — this is the hint the user sees at step-1b for cheap override. See `narrative-frames.md`.

### `hook`

The opener. `technique` is one of 5 categories; `opener` is the actual line Claude will fill into the cover or first content slide. ≤20 words.

### `red_line`

One sentence capturing the deck's spine as a sequence. Step 4 uses this to check red-line-break defects.

### `slides[]`

One entry per planned slide. `role` comes from the frame's role set (see `narrative-frames.md`); `claim` is the slide's title-in-draft (subject to `slide-claim-test.md`); `audience_fit` is a one-sentence note for step 2's planner.

## Persistence

Written to the working directory at step 1, next to `content_plan.json`. Preserved through step 5 (not mutated on revise). Read by:
- step 2 (planning) — consumes `frame`, `audience`, `slides[].claim`, `slides[].role`.
- step 1b (presentation) — renders the summary block.
- step 4 (verify) — checks `audience-mismatch` against `audience`, `red-line-break` against `frame` + `slides[].role`.
- `/deck critique` mode — reconstructs the brief from an existing `.pptx`, writes the same shape.

## Validation

Every write of `design_brief.json` passes through `skills/deck/lib/design_brief.py::validate_brief()`, which loads the schema and runs `jsonschema.validate()`. Validation errors halt the pipeline — a brief that can't be validated is a broken inference.
