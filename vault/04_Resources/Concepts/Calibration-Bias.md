---
description: Pooling similarity statistics across clusters of very different sizes lets the biggest cluster's internal noise masquerade as the whole vault's separation signal — a lesson learned calibrating gaiafield's inference gates.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-07-26
created: 2026-07-26
kind: concept
topics:
  - knowledge-graphs
  - reliability
  - statistics
tags:
  - domain/toolkit-meta
---

# Calibration Bias

`gaiafield calibrate` measures whether an embedding model actually separates same-topic from
different-topic content, against a spec naming known clusters. Its first implementation shipped
with a bug that's worth understanding on its own terms, independent of gaiafield: **pooling every
pairwise comparison into one mean, weighted implicitly by cluster size, lets the biggest cluster
dominate a number that's supposed to describe the whole population.**

## What went wrong, concretely

This vault has three planted clusters: `toolkit-concepts` (57 notes — a broad grab-bag), `birding`
(7 notes), `homelab` (7 notes). Pooling every intra-cluster pair across all three gives
toolkit-concepts ~1596 pairs against birding's and homelab's 21 apiece — toolkit-concepts alone is
about 97% of every intra-pair in the pool, purely because pair count grows quadratically with
cluster size. The reported numbers (`intra_mean: 0.622, cross_mean: 0.542, separation: 0.080`) were
measuring the grab-bag, not the signal. The tell: birding's and homelab's notes scored **0.630**
similarity to *each other* — a genuine cross-cluster pair — higher than toolkit-concepts' own
diluted intra-mean of 0.617. A "different topic" pair out-scored a "same topic" one, and the gates
derived from that gap flagged 1405 of all non-linked pairs in the vault, most of them noise.

## The fix: an objective, self-excluding tightness rule

For each cluster, compute a leave-one-out reference: the pooled cross-cluster mean over every pair
*not involving* that cluster. A cluster is "tight" only if its own intra-mean beats that reference.
Recompute the real `intra_mean`/`cross_mean` over tight clusters' own pairs only — a pair touching
a non-tight cluster is dropped entirely, not folded into either side. On this vault: `birding` and
`homelab` both clear their bar; `toolkit-concepts` does not — it self-excludes exactly as its own
diluted intra-mean predicted it should. Recalibrated this way: separation more than doubles to
0.177, gates land at 0.72/0.67, and flagged pairs drop from 1405 to 480 (226 INFERRED + 254
AMBIGUOUS) — a birding note's default candidate view narrows from 31 mostly-noise hits to a single,
correct same-cluster one.

## The generalizable lesson

This isn't specific to embeddings. Any pooled comparison across naturally uneven groups — A/B
groups of very different size, cohorts, cluster labels from an upstream process — can produce a
headline number that's actually describing its largest group's internal noise. The fix generalizes
too: either weight explicitly instead of pooling raw pairs, or add an objective test (like the
leave-one-out tightness rule) for whether a group is coherent enough to trust before including it
in the comparison at all.

## Related

- [[Semantic-Search-Score-Calibration]]
- [[Confidence-Labeling-for-Inferred-Edges]]
- [[Inference-Write-Policy|Report-Only Inference]]
- [[Surprise-Scoring]]
- [[The-Observer-Pattern]]
- [[Gaiafield]]
- [[The-Ratchet]]
