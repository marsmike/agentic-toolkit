---
description: Finding densely-connected clusters in a wikilink graph, and the sparse cross-cluster notes — bridges — that make the clusters discoverable from each other.
status: distilled
source: "Community-detection literature (Leiden algorithm, Traag et al.) name-dropped as prior art"
processed_date: 2026-01-27
created: 2026-01-27
kind: concept
topics:
  - knowledge-graphs
  - retrieval
tags:
  - domain/toolkit-meta
---

# Community Detection and Bridge Notes

A vault with enough wikilinks in it develops visible clusters: notes about one topic link mostly
to each other and only occasionally out. Community-detection algorithms (Leiden improves on the
older Louvain by guaranteeing every detected community is actually connected, not an artifact of
merge order) find these clusters automatically from the link structure alone, no topic labels
required.

## Bridge notes are the interesting output, not a side effect

A note with links into two clusters that otherwise barely touch is more informative than a note
deep inside one cluster — it's the answer to "how does idea A relate to idea B" for a reader who
didn't know to ask. This note is itself one: it lives in the toolkit-concepts cluster but reasons
about clusters using [[Field-Guide-Project|field-guide]] and
[[Home-Lab-Migration|home-lab-migration]] — two other clusters entirely — as its examples.

## Resolution tuning is the hard part

Too coarse a resolution parameter merges distinct clusters that share only a couple of bridge
notes (see this vault's own capture on the topic, not yet distilled). Too fine, and every small
project fragments into its own singleton community. There's no universal default — it has to be
tuned against a real corpus, which is exactly what this vault exists to provide.

## Related

- [[Knowledge-Graphs-from-Wikilinks]]
- [[Surprise-Scoring]]
- [[Confidence-Labeling-for-Inferred-Edges]]
- [[Gaiafield]]
- [[Test-Corpus-Map]]
- [[Toolkit-Maintenance]]
