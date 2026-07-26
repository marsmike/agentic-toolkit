---
description: Labeling a graph edge EXTRACTED, INFERRED, or AMBIGUOUS so a consumer knows how much to trust it, instead of presenting every edge with equal certainty.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-01-25
created: 2026-01-25
kind: concept
topics:
  - knowledge-graphs
  - reliability
tags:
  - domain/toolkit-meta
---

# Confidence Labeling for Inferred Edges

Once a knowledge graph includes edges the system inferred rather than found verbatim (a wikilink,
a shared frontmatter reference), every edge needs a label saying which kind it is:

- **EXTRACTED** — read directly off the text; a wikilink is a wikilink, no judgment involved.
- **INFERRED** — added because two notes scored above a similarity threshold; a model's guess,
  not a fact.
- **AMBIGUOUS** — scored near the threshold either way; worth surfacing but not worth asserting.

## Why this guards against "successful corruption"

An inferred edge that's wrong doesn't look wrong — it renders identically to a real one unless
labeled. A graph tool that silently treats INFERRED edges as equal to EXTRACTED ones will
eventually present a confident wrong connection as fact, and nothing about the output signals that
it should be double-checked. Labeling is the difference between a system that can be audited and
one that can only be trusted or not trusted wholesale.

## Related

- [[Deterministic-vs-Inferred-Graph-Edges]]
- [[Surprise-Scoring]]
- [[Knowledge-Graphs-from-Wikilinks]]
- [[Dead-Letter-Queues-for-Automation]]
- [[Gaiafield]]
