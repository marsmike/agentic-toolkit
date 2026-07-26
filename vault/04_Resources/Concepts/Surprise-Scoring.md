---
description: Scoring a graph edge by how unexpected it is given the deterministic graph's own structure, so a genuinely novel cross-domain connection ranks above a thousand predictable within-cluster ones.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-07-26
created: 2026-02-03
kind: concept
topics:
  - knowledge-graphs
  - retrieval
tags:
  - domain/toolkit-meta
---

# Surprise Scoring

Most edges in a dense graph are unsurprising: two notes in the same project link to each other
because of course they do. The interesting edges are the ones a naive "shared cluster" prior
wouldn't predict — a bridge note connecting two clusters that otherwise share almost nothing (see
[[Community-Detection-and-Bridge-Notes]]). Surprise scoring ranks edges by exactly that: low
surprise for expected within-cluster links, high for the rare cross-cluster ones.

This shipped in [[Gaiafield]] 0.2.0 (R5), not v3 as first sketched — it turned out to be a small
enough formula to land alongside the rest of the inferred-edge work rather than waiting for
community detection.

## The formula

`candidates` and `surprise` share one implementation, never reimplemented twice:

```
det_distance = BFS distance over extracted edges only (undirected), or null if unreachable
surprise     = score * (1 - 1 / (1 + det_distance))   if det_distance is finite
             = score * 1                               if det_distance is null (unreachable)
```

A same-neighborhood inferred edge (small `det_distance`) is unsurprising even at a high similarity
score; an edge between two notes with no deterministic route at all is maximally surprising —
exactly the cross-domain lead worth a human's attention. `same_subtree` is a cheap structural
heuristic alongside it (the first two path segments, or the whole path for a root note), not the
planted cluster labels themselves.

## Why a real corpus, not a synthetic one, mattered

Calibrating what counts as "surprising" needed a graph with actual cluster structure and actual
bridge notes in it — a synthetic graph built to test the scorer would just encode the same
assumptions the scorer is supposed to discover. This vault's planted three-cluster structure with
its documented bridge notes ([[Test-Corpus-Map]]) is what `gaiafield calibrate` and the `surprise`
tests actually run against — see [[Calibration-Bias]] for what the first calibration pass got wrong
and how it was corrected.

## Every row carries its label and model — a fix, not the original design

`surprise` rows are pair-shaped (`a`/`b`, both vault-relative paths — there's no single "queried
note" the way `candidates` has), each carrying `score`, `surprise`, `det_distance`,
`same_subtree`, and — as of a same-release fix — **`label`** (INFERRED/AMBIGUOUS) and **`model`**.
The CLI spec this was originally built against had neither field, which meant `surprise` could leak
the AMBIGUOUS band by default with no way for a caller to even see which label a row carried —
violating [[Inference-Write-Policy|Report-Only Inference]]'s rule that AMBIGUOUS is surfaced only on request, never
proactively. Both builders had faithfully implemented an inconsistent spec; a stub-driven eval kept
the gap invisible until [[The-Observer-Pattern|an observer's first real-binary integration]]
exposed it. `gaiafield surprise --include-ambiguous` (default: excluded) now mirrors `candidates`
exactly.

## Related

- [[Community-Detection-and-Bridge-Notes]]
- [[Confidence-Labeling-for-Inferred-Edges]]
- [[Inference-Write-Policy|Report-Only Inference]]
- [[Calibration-Bias]]
- [[Deterministic-vs-Inferred-Graph-Edges]]
- [[The-Observer-Pattern]]
- [[Gaiafield]]
- [[Test-Corpus-Map]]
