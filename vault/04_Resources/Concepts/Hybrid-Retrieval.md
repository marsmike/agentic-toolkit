---
description: Fusing keyword (BM25) and dense-vector search at query time rather than picking one, because each covers the other's blind spot.
status: distilled
source: "(none — synthesized from general retrieval-systems literature, no single source)"
processed_date: 2026-07-23
created: 2026-07-23
kind: concept
topics:
  - retrieval
  - search
tags:
  - domain/toolkit-meta
  - domain/agent-systems
---

# Hybrid Retrieval

Keyword search (BM25) is precise on exact terms — identifiers, package names, error codes — but
blind to paraphrase. Dense-vector search catches paraphrase and thematic similarity but blurs past
exact tokens it hasn't seen framed that way. Neither alone is enough for a vault where a query
might be "the storage shelf" (exact term) or "why did the restore drill matter" (paraphrase of a
concept spread across several notes).

## Fusing rather than choosing

Hybrid retrieval runs both and fuses the ranked results — reciprocal rank fusion is the common
choice — rather than trying to pick the single better method per query. [[Farsight]] is this
toolkit's implementation: BM25 plus dense vectors over vault notes and PDF chunks, one engine, one
query interface.

## Where it still falls short

Hybrid retrieval answers "what matches this query" well. It does not answer "what's connected to
this note" or "what's the shortest path between these two ideas" — those are graph questions, not
retrieval questions. See [[Knowledge-Graphs-from-Wikilinks]] for the complementary layer, and
[[BM25-Dilution]] for a failure mode hybrid retrieval doesn't fully solve on its own: a long,
diffuse description can still drag down the keyword half of the fusion even when the vector half
compensates.

## Related

- [[BM25-Dilution]]
- [[Knowledge-Graphs-from-Wikilinks]]
- [[Farsight]]
- [[Semantic-Search-Score-Calibration]]
- [[Retrieval-Verification-Loop]]
- [[Toolkit-Maintenance]]
