---
description: Writing a description field that serves both a human skimming and BM25 scoring it — condensed, high-IDF terms over grammatical completeness.
status: active
created: 2026-02-16
kind: guide
topics:
  - retrieval
  - note-taking
tags:
  - domain/toolkit-meta
---

# Writing Good Descriptions

A note's `description` field is read by a human deciding whether to open the note, and weighed
heavily by keyword search deciding whether to surface it — see [[BM25-Dilution]] for why those two
jobs can pull in different directions. This guide is the practical version of that concept.

## The heuristic

Favor 3–5 distinguishing terms over a complete sentence. "Home-lab migration, weekly review,
2026-07-20" beats "This is the weekly review for the home-lab migration project, covering the
week of July 20th, 2026" — every note in a project already knows what a weekly review is; the
words doing the actual distinguishing work are the project name and the date.

## Checking your own work

Run the [[Retrieval-Verification-Loop]] against a note you've just written: predict its content
from the description alone, score the prediction, and rewrite if it scores below 3. See
[[Retrieval-Verification-Loop-Long-Description-Specimen]] and its condensed sibling for a worked
before/after pair.

## When a longer description is actually fine

Areas and Resources with only a handful of near-duplicate siblings don't need the same discipline
as a project generating dozens of near-identical weekly reviews — dilution only bites when there's
real competition for the same keyword space.

## Related

- [[BM25-Dilution]]
- [[Retrieval-Verification-Loop]]
- [[Retrieval-Verification-Loop-Long-Description-Specimen]]
- [[Retrieval-Verification-Loop-Condensed-Description-Specimen]]
