---
description: Building a knowledge graph's first version from wikilinks, frontmatter, and tags alone — no model call, no hallucinated edges — before ever adding inferred similarity edges.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-02
created: 2026-02-02
kind: concept
topics:
  - knowledge-graphs
  - reliability
tags:
  - domain/toolkit-meta
---

# Deterministic vs. Inferred Graph Edges

A graph edge extracted straight from a wikilink is deterministic: the text contains a wikilink to
another note, so the edge exists, and re-running the extraction produces the identical graph every
time. An edge
proposed because two notes' embeddings sit above a similarity threshold is inferred: it can
change if the embedding model changes, and it can simply be wrong.

## Why the deterministic pass comes first

A graph built entirely from deterministic extraction can't rot — there is no model in the loop to
drift or hallucinate a connection that was never written. Building this layer first, and shipping
it alone as a complete v1, means the graph engine is trustworthy from day one even before anything
probabilistic is added. [[Gaiafield]] follows exactly this sequencing: wikilinks/frontmatter/tags
to a queryable graph first, similarity-threshold inference later, confidence-labeled per
[[Confidence-Labeling-for-Inferred-Edges]] once it arrives.

## The temptation to skip ahead

Inferred edges are more impressive in a demo — they surface connections nobody wrote down. But
shipping them before the deterministic baseline exists means there's no ground truth to compare
the inferred edges against, and no way to tell a real discovery from an artifact of the embedding
model's biases.

## Related

- [[Knowledge-Graphs-from-Wikilinks]]
- [[Confidence-Labeling-for-Inferred-Edges]]
- [[Surprise-Scoring]]
- [[Gaiafield]]
