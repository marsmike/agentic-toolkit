# /deck Modes

Three user-facing modes. All share the same pipeline described in `pipeline.md`; they differ in which steps run.

## create (default)

```
/deck "content brief"
```

Runs the full pipeline (steps 0–5). New deck from scratch. **Verify (step 4) always runs at least once** — no matter how obviously-correct the first build looks. Completion requires `out/verify_report.json`; see `pipeline.md` step 4.

## polish

```
/deck polish rough.pptx
/deck polish rough.pptx "make it 5 slides, executive-focused"
```

Ingests an existing `.pptx`, reflows into brand layouts. Same steps as create; step 1 starts from existing content instead of a brief. **Verify is mandatory here too** — reflowing into brand layouts doesn't guarantee the result fits the slots.

## critique

```
/deck critique existing.pptx
```

Read-only defect analysis. Runs steps 1 → 1b → 4 only. No build, no revise.

### Procedure

1. **Ingest** (step 1) — open the existing `.pptx` with python-pptx, extract content per slide into `content_plan.json`.
2. **Derive brief** (step 1 continued) — infer `design_brief.json` from the extracted content. The `frame` inference looks at slide-role ordering in the existing deck; the `audience` inference looks at jargon density and bullet structure.
3. **Present brief** (step 1b) — print the derived brief + slide list in the usual summary format. The user can edit (same edit-handling as create/polish modes) if the inferred audience or frame is off; this is useful because a critique against the wrong audience produces spurious `audience-mismatch` flags.
4. **Verify** (step 4) — render the existing `.pptx` to PNGs; LLM-eyeball for all 11 defect classes.
5. **Emit outputs** — next to the source `.pptx`:
   - `<name>-critique.md` — defects grouped by slide with suggested fixes, plus a summary count at the top.
   - `design_brief.json` — the brief Claude derived.

### `<name>-critique.md` format

```markdown
# Critique: <name>.pptx

Derived audience: **exec** — _time-poor, outcomes-driven_.
Derived frame: **SCQA** — _pitch-style answer-first deck (runner-up: PSSR)_.

**Summary:** 7 defects across 4 / 12 slides.

---

## Slide 3 — "Our Approach"

- **claim-title**: title "Our Approach" is a topic noun.
  **Fix:** Rewrite as a claim, e.g. "We ship daily because we test first".
- **bullet-dump**: 6 peer-level bullets, no hierarchy.
  **Fix:** Group under 2 sub-headings; drop weakest two bullets.

## Slide 7 — "Q1 Results"

- **red-line-break**: slide's role is `context` but sits after `recommendation` (slide 5 was the rec).
  **Fix:** Move to earlier in the deck, or re-role as `evidence`.

---
```

### No iteration loop

Critique mode is a single pass. No revise loop, no budget cap. If the user wants fixes applied, they should run `/deck polish existing.pptx` afterwards — polish mode is the write path.

## Step 1b approval-gate format

Regardless of mode, step 1b prints a compact brief + plan and asks once. Example:

```
📋 Design brief

  Audience:   exec — time-poor, outcomes-driven
  Takeaway:   "Polish time collapsed from 3 hrs to 15 min per deck"
  Frame:      Duarte Sparkline — alternating What Is / What Could Be
              (runner-up: PSSR, less fit without a discrete 'search' phase)
  Hook:       contrast — "Five years ago this took a week…"
  Red line:   Pain → Solution demo → Results → What this unlocks

🎞  Plan (8 slides)
   1. title-orange      HOOK         "Five years ago…"
   2. kpi-grid          COMPLICATION "3 hrs × 40 decks/week = 120 hrs lost"
   …

Approve? (press enter) · Edit: say what to change · Redo from scratch: type 'redo'
```

Empty input = approve. Free-form edit triggers a targeted revision. `redo` re-infers from scratch.
