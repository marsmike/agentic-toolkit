---
description: The knowledge-graph engine — deterministic wikilink/frontmatter/tag extraction (v1, shipped) plus a report-only statistical inference layer (v2, shipped) — never conflated.
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

The toolkit's graph engine (`crates/gaiafield/`, currently **0.2.0**), built on the premise in
[[Knowledge-Graphs-from-Wikilinks]]: the graph already exists in a vault's wikilinks, frontmatter,
and tags, so the first version only has to extract it faithfully. Two layers now ship, never
conflated: `extracted` edges (deterministic, v1) and `inferred` edges (statistical, v2).

## Version sequencing — v1 and v2 are both shipped

- **v1 (R2, 0.1.0; corrected 0.1.1)** — deterministic extraction only: wikilinks, frontmatter, and
  tags into a queryable SQLite store. No model call, no edge that can hallucinate. See
  [[Deterministic-vs-Inferred-Graph-Edges]]. 0.1.1 fixed a real corruption bug: deleting a note left
  other notes' edges *into* it as resolved rows, so `neighbors` crashed and `path` silently routed
  through deleted nodes — incoming edges are now re-flagged `dangling = 1` on node removal. See
  [[The-Observer-Pattern]] for how this was caught.
- **v2 (R5, 0.2.0)** — inferred edges, confidence-labeled EXTRACTED / INFERRED / AMBIGUOUS per
  [[Confidence-Labeling-for-Inferred-Edges]], embedded with model2vec-rs + `potion-base-8M`
  (deterministic, offline, 256-dim static embeddings — no ONNX/libtorch runtime, zero C/C++ in the
  embedding stack, verified by build-log inspection). New subcommands: `infer`, `candidates`,
  `surprise`, `calibrate`. Governed entirely by [[Inference-Write-Policy|Report-Only Inference]] — see that note for the
  full rule set.
- **v3 (not yet built)** — community detection ([[Community-Detection-and-Bridge-Notes]]), causal
  edge types, and an OKF-compatible export for interoperability with external graph tooling.

## Query verbs

v1: `index`, `neighbors <note> [--depth] [--direction]`, `stats`, `path <from> <to>` — CLI-in/
JSON-out per [[CLI-in-JSON-out-Contracts]]. v2 adds `infer`, `candidates <note>`, `surprise`,
`calibrate --clusters <spec.json>`; `neighbors`/`path` gain `--include-inferred`, off by default —
traversal defaults to `extracted` edges only (contract rule 4). No plugin reads gaiafield's
internal SQLite store directly. `context` is named in `contract/KNOWLEDGE_API.md` as reserved but
not yet implemented — the same incremental-delivery pattern farsight used for its own vector half.

## Calibration: the bias lesson

The first calibration pass was statistically broken — see [[Calibration-Bias]] for the full story.
In short: pooling similarity scores across clusters of very different sizes let this vault's
57-note toolkit-concepts grab-bag dominate the pooled statistics, reporting a separation of 0.08
that was mostly noise (a cross-cluster pair scored *higher* than the pooled "same-topic" average).
Recalibrated on tight clusters only (an objective, self-excluding leave-one-out rule): separation
0.177, gates **0.72/0.67**, flagged pairs dropped from 1405 to 480 on this vault, and a birding
note's default candidate view narrowed from 31 noisy hits to the single correct same-cluster one.

## `--reset` and incremental indexing

`infer --reset` deletes every inferred row and restores the exact v1 graph — provably, since
inference never mutates an `extracted` row (contract rule 2). `index` re-extracts only
changed/removed notes by comparing mtime+size; `--full` rebuilds from scratch.

## Surprise scoring

`candidates`/`surprise` share one formula: `surprise = score * (1 - 1/(1 + det_distance))` when a
deterministic path exists between the two notes, or `score * 1` when it doesn't — a same-
neighborhood inferred edge is unsurprising even at a high score; an edge with no deterministic
route at all is maximally surprising. See [[Surprise-Scoring]] for the full shape, including the
per-row `label`/`model` fields a coordination bug once left off.

## What this vault gives it to chew on

Three roughly-recognizable clusters (toolkit concepts, the birding project, the home-lab project)
connected by a handful of documented bridge notes — see [[Test-Corpus-Map]] — plus a planted
broken wikilink and an archived note that active content correctly never links to, both useful
negative cases for a graph extractor's test suite.

## Related

- [[Knowledge-Graphs-from-Wikilinks]]
- [[Deterministic-vs-Inferred-Graph-Edges]]
- [[Confidence-Labeling-for-Inferred-Edges]]
- [[Inference-Write-Policy|Report-Only Inference]]
- [[Calibration-Bias]]
- [[Community-Detection-and-Bridge-Notes]]
- [[Surprise-Scoring]]
- [[Test-Corpus-Map]]
- [[Farsight]]
- [[The-Observer-Pattern]]
