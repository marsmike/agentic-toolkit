---
description: Treating the wikilinks that already exist in a note-taking vault as a knowledge graph, rather than building a separate graph layer that requires its own maintenance.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-01-16
created: 2026-01-16
kind: concept
topics:
  - knowledge-graphs
  - vault-architecture
tags:
  - domain/toolkit-meta
  - knowledge-graph
---

# Knowledge Graphs from Wikilinks

Most note-taking vaults already contain a graph — every wikilink is an edge, every note is a
node — and it was built for free as a side effect of normal writing, not as a deliberate
graph-construction exercise. The cheapest knowledge graph a system can have is the one that
already exists in the notes people were going to write anyway.

## Deterministic first, inferred second

Extracting this graph deterministically (parse wikilinks, frontmatter references, shared tags)
requires no model call and cannot hallucinate an edge that isn't there — see
[[Deterministic-vs-Inferred-Graph-Edges]]. Only once that baseline exists does it make sense to
add inferred edges (similarity above a calibrated threshold) on top, each one confidence-labeled
per [[Confidence-Labeling-for-Inferred-Edges]] so a consumer can tell which kind of edge it's
looking at.

## What the graph is for

Graph queries answer a different question than [[Hybrid-Retrieval|search]] does: not "what
matches this query" but "what connects to this note, and how many hops away." That's the
multi-hop, whole-neighborhood question search alone can't answer — see
[[Community-Detection-and-Bridge-Notes]] for the clustering questions this unlocks once the graph
is dense enough to have real structure.

## Related

- [[Vault-First-Architecture]]
- [[Deterministic-vs-Inferred-Graph-Edges]]
- [[Confidence-Labeling-for-Inferred-Edges]]
- [[Community-Detection-and-Bridge-Notes]]
- [[Surprise-Scoring]]
- [[Hybrid-Retrieval]]
- [[Gaiafield]]
