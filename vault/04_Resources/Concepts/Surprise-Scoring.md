---
description: Scoring a graph edge by how unexpected it is given the rest of the graph's structure, so a genuinely novel connection ranks above a thousand predictable within-cluster ones.
status: draft
created: 2026-02-03
kind: concept
topics:
  - knowledge-graphs
  - retrieval
tags:
  - domain/toolkit-meta
---

# Surprise Scoring

*Draft — this is a v3-milestone idea for the graph engine, written down early because the shape
is clear even though the calibration work hasn't happened yet. Not yet reviewed against a real
corpus.*

Most edges in a dense graph are unsurprising: two notes in the same project link to each other
because of course they do. The interesting edges are the ones a naive "shared cluster" prior
wouldn't predict — a bridge note connecting two clusters that otherwise share almost nothing (see
[[Community-Detection-and-Bridge-Notes]]). Surprise scoring tries to rank edges by exactly that:
low surprise for expected within-cluster links, high surprise for the rare cross-cluster ones.

## Why this needs a real corpus, not a synthetic one

Calibrating what counts as "surprising" requires a graph with actual cluster structure and actual
bridge notes already in it — a synthetic graph built to test the scorer would just encode the
same assumptions the scorer is supposed to discover. This vault's planted three-cluster structure
with a handful of documented bridge notes (see [[Test-Corpus-Map]]) exists partly for this reason.

## Related

- [[Community-Detection-and-Bridge-Notes]]
- [[Confidence-Labeling-for-Inferred-Edges]]
- [[Deterministic-vs-Inferred-Graph-Edges]]
- [[Gaiafield]]
- [[Test-Corpus-Map]]
