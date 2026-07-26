---
description: Retrieval-verification loop, condensed-description specimen, BM25 test pair.
status: distilled
source: "(none — originated from toolkit design work; deliberately-condensed specimen)"
processed_date: 2026-02-09
created: 2026-02-09
kind: concept
topics:
  - retrieval
  - test-corpus
tags:
  - domain/toolkit-meta
---

# Retrieval-Verification Loop — Condensed-Description Specimen

Same content as [[Retrieval-Verification-Loop-Long-Description-Specimen]] — this is the paired
sibling for the [[BM25-Dilution]] test corpus, described in high-IDF terms instead of full
sentences. See [[Test-Corpus-Map]] for how the pair is meant to be used in a search eval.

The idea both specimens describe: predict a note's content from its description alone, score the
prediction against the real content on a 1–5 scale, flag anything under 3. That's
[[Retrieval-Verification-Loop]] in full; this note and its long-description sibling exist only to
make the BM25 effect checkable rather than asserted.

## Related

- [[BM25-Dilution]]
- [[Retrieval-Verification-Loop]]
- [[Retrieval-Verification-Loop-Long-Description-Specimen]]
- [[Test-Corpus-Map]]
- [[Farsight]]
