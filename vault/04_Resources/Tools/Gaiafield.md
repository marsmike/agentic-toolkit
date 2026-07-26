---
description: The knowledge-graph engine — extracts the graph that already exists in wikilinks, frontmatter, and tags into a queryable store, deterministic first.
status: active
created: 2026-02-05
kind: tool-landmark
topics:
  - knowledge-graphs
  - engines
tags:
  - domain/toolkit-meta
---

# Gaiafield

The toolkit's graph engine, built on the premise in
[[Knowledge-Graphs-from-Wikilinks]]: the graph already exists in a vault's wikilinks, frontmatter
references, and shared tags, so the first version just has to extract it faithfully, not infer
anything.

## Version sequencing

- **v1** — deterministic extraction only: wikilinks, frontmatter, tags, into a queryable store.
  No model call, no edge that can hallucinate. See [[Deterministic-vs-Inferred-Graph-Edges]].
- **v2** — inferred edges above a calibrated similarity threshold, each one confidence-labeled
  EXTRACTED / INFERRED / AMBIGUOUS per [[Confidence-Labeling-for-Inferred-Edges]].
- **v3** — community detection ([[Community-Detection-and-Bridge-Notes]]), causal edge types,
  [[Surprise-Scoring]], and an OKF-compatible export for interoperability with external graph
  tooling.

## Query verbs

`neighbors` and `context` are the two CLI-in/JSON-out query verbs a plugin calls — see
[[CLI-in-JSON-out-Contracts]]. No plugin reads Gaiafield's internal store directly.

## What this vault gives it to chew on

Three roughly-recognizable clusters (toolkit concepts, the birding project, the home-lab project)
connected by a handful of documented bridge notes — see [[Test-Corpus-Map]] — plus a planted
broken wikilink and an archived note that active content correctly never links to, both useful
negative cases for a graph extractor's test suite.

## Related

- [[Knowledge-Graphs-from-Wikilinks]]
- [[Deterministic-vs-Inferred-Graph-Edges]]
- [[Confidence-Labeling-for-Inferred-Edges]]
- [[Community-Detection-and-Bridge-Notes]]
- [[Surprise-Scoring]]
- [[Test-Corpus-Map]]
- [[Farsight]]
