---
description: The hybrid BM25+vector search engine — Rust, CLI-in/JSON-out, queries vault notes and PDF chunks with one engine.
status: active
created: 2026-02-04
kind: tool-landmark
topics:
  - retrieval
  - engines
tags:
  - domain/toolkit-meta
---

# Farsight

The toolkit's search engine: hybrid BM25 + dense-vector retrieval over vault notes and PDF chunks,
one Rust binary, CLI-in/JSON-out per [[CLI-in-JSON-out-Contracts]]. Replaces what used to be a
Python hybrid-search script, then a separate embeddings-generation step, then a reference-search
core maintained elsewhere — one engine now serves all three call sites.

## What it queries

A single `query` command returns fused, ranked results with per-source scores, so a caller can see
whether a hit came from the keyword side, the vector side, or both. See [[Hybrid-Retrieval]] for
why both sides matter and [[BM25-Dilution]] for a failure mode fusion doesn't fully absorb.

## What it deliberately doesn't do

Farsight answers "what matches this query," not "what connects to this note" — that's
[[Gaiafield]]'s job. The two are complementary, queried separately, composed by whoever's calling
them rather than merged into one do-everything engine.

## Where this vault exercises it

[[Toolkit-Maintenance]] spot-checks Farsight against real queries over
[[Field-Guide-Project|field-guide]] and [[Home-Lab-Migration|home-lab-migration]] content, and
[[Test-Corpus-Map]] documents the planted specimens ([[Retrieval-Verification-Loop-Long-Description-Specimen]]
and its sibling) this engine's eval suite should score against.

## Related

- [[Hybrid-Retrieval]]
- [[Gaiafield]]
- [[CLI-in-JSON-out-Contracts]]
- [[BM25-Dilution]]
- [[Toolkit-Maintenance]]
- [[Test-Corpus-Map]]
