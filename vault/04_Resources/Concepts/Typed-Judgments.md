---
description: Asking a model many narrow yes/no and pick-one questions that come back as probabilities, and keeping every threshold and consequence in code — the division of labor behind the distill run's advisory judgments.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-09-21
created: 2026-09-21
kind: concept
topics:
  - model-routing
  - reliability
tags:
  - domain/toolkit-meta
  - domain/agent-systems
---

# Typed Judgments

Most of what a distill run has to decide is small: is this found note about the same mechanism
or does it only share vocabulary, does the capture extend a passage or merely sit next to it,
which folder, does this capture add anything its sibling lacks. A frontier model can decide all
of that by reading prose rules, and it did, once per capture, with nothing to show for how sure
it was. A similarity score could decide some of it, until the score stopped meaning anything:
once [[Farsight]] supplied raw BM25 scores, the 0.70 enrichment gate became "informational
only" (see [[Semantic-Search-Score-Calibration]]).

A **typed judgment** is the third option. One request carries a shared `state` (the capture,
the found notes) and a dictionary of narrow questions; each comes back as a probability, never
as text. `plugins/obsidian/scripts/judge.py` is the seam, `distill_judge.py` the first caller.

## The division of labor

- **The model supplies the number.** One judgment per question, worded so a high value means
  yes, with criteria that describe concrete situations and always a way to say "none of these".
- **Code owns the policy.** Thresholds, gates and what a number leads to live in the calling
  script, per backend. A number tuned on a calibrated model does not transfer to an
  uncalibrated one, the same lesson as [[Calibration-Bias]] one layer up.
- **Wording is data.** Every question lives in `scripts/judgments/questions.py` with a
  `QUESTIONS_VERSION`; every emitted block carries backend, model and that version.
- **Narrow heads, never a holistic one.** "Is this capture good?" averages the signal away;
  "does `notes.N03` discuss the same mechanism?" separates.
- **Advice, not action.** A judgment is report-only under the same rule as an inferred edge
  ([[Inference-Write-Policy|Report-Only Inference]]). It reaches the human through the distill
  run's Phase 1 handoff, where the frontier model also says where it disagrees.

## Who tunes whom

The cheap model answers; the reasoning model writes and debugs the questions. When an answer is
wrong, the first suspect is the question, then the state, then the label, and only then the
model: see the `judgment-calibration` skill, which classifies every disagreement by cause before
proposing the smallest fix, keeps a held-out slice away from the tuning step, and never accepts
a backend's own answer as a label.

## Calibration log

- **2026-09-21, jev-1.13, questions .1 → .2.** First run on the three bundled captures: 30/35
  tune, 9/10 held out. Three of five misses shared one cause: the captures carry collector's
  remarks ("raw, not yet distilled", "check overlap before distilling"), so the relevance and
  relation questions linked them to [[Capture-Conventions]]. Cause class: *question read too
  broadly*. Fix: judge "the subject matter of `capture`", and name collection/processing
  overlap in the false criterion. After: 31/35 tune, held out unchanged, the false relevance
  gone and the false "strengthens" probability down from 0.76 to 0.40. Thresholds untouched;
  the relevance sweep suggests 0.60 over 0.50 but 13 rows do not justify a policy change.

## Related

- [[Model-Tiering-for-Agent-Fleets]]
- [[Inference-Write-Policy|Report-Only Inference]]
- [[Confidence-Labeling-for-Inferred-Edges]]
- [[Semantic-Search-Score-Calibration]]
- [[Calibration-Bias]]
- [[Dead-Letter-Queues-for-Automation]]
- [[The-Distill-Workflow]]
