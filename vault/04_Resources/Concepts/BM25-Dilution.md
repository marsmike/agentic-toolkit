---
description: A long, verbose description field dilutes the keyword weight of the terms that actually matter, hurting BM25-side retrieval even when the content itself is good.
status: distilled
source: "(none — synthesized from general information-retrieval literature, no single source)"
processed_date: 2026-07-24
created: 2026-07-24
kind: concept
topics:
  - retrieval
  - search
tags:
  - domain/toolkit-meta
---

# BM25 Dilution

BM25 scores a document partly by term frequency relative to document length — a longer field
spreads the same term count thinner, so a query's high-value terms contribute less to the score
even when they're present. A note's `description` field, if written as a paragraph rather than a
sentence, quietly makes that note harder to find by the exact terms someone would actually search
for.

## The practical fix: condense to high-IDF terms

A description written for BM25 to score well favors the 3–5 terms with the highest inverse
document frequency in the vault — the rare, distinguishing words — over grammatical completeness.
"Weekly review, home-lab migration project" beats a full sentence explaining what a weekly review
is, because every note in the vault already knows what a weekly review is; the words doing the
distinguishing work are "home-lab migration."

## A live specimen pair

This vault deliberately carries two versions of the same idea to make the effect checkable rather
than asserted: [[Retrieval-Verification-Loop-Long-Description-Specimen]] and its condensed sibling
[[Retrieval-Verification-Loop-Condensed-Description-Specimen]] — same underlying content, two
description styles, for a search eval to score against directly.

## Related

- [[Hybrid-Retrieval]]
- [[Retrieval-Verification-Loop]]
- [[Retrieval-Verification-Loop-Long-Description-Specimen]]
- [[Retrieval-Verification-Loop-Condensed-Description-Specimen]]
- [[Test-Corpus-Map]]
- [[Farsight]]
