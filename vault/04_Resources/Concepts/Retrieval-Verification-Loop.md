---
description: Predicting a note's content from its description alone, scoring the prediction against the real content, and flagging low scores — a maintenance loop that catches descriptions that mislead search.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-08
created: 2026-02-08
kind: concept
topics:
  - retrieval
  - vault-maintenance
tags:
  - domain/toolkit-meta
---

# Retrieval-Verification Loop

A note's `description` field does two jobs at once: it's what a human reads to decide whether to
open the note, and it's the field search weighs most heavily when matching a query. Those two jobs
can silently diverge — a description can be perfectly readable and still be a poor retrieval
signal, or vice versa.

## The check

Predict what the note probably contains from the description alone, score the prediction against
the note's actual content on a 1–5 scale, and flag anything scoring below 3 for a rewrite. This
runs as a maintenance skill over a batch of notes, not a one-off manual check — the value is in
catching drift as a vault grows, not in a single pass.

## Two specimens, deliberately paired

This vault carries a worked example of what the loop is meant to catch:
[[Retrieval-Verification-Loop-Long-Description-Specimen]] (a verbose, BM25-diluting description)
and [[Retrieval-Verification-Loop-Condensed-Description-Specimen]] (the same content, described in
3–5 high-IDF terms). See [[BM25-Dilution]] for the retrieval mechanism the condensed version is
optimizing for.

## Related

- [[BM25-Dilution]]
- [[Hybrid-Retrieval]]
- [[Retrieval-Verification-Loop-Long-Description-Specimen]]
- [[Retrieval-Verification-Loop-Condensed-Description-Specimen]]
- [[Vault-Maintenance-and-Linting]]
