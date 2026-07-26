---
description: No automation writes vault content from an inferred edge without explicit human confirmation in that session — the contract rule that keeps a wrong statistical guess from silently corrupting the vault while reporting success.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-07-26
created: 2026-07-26
kind: concept
topics:
  - knowledge-graphs
  - reliability
tags:
  - domain/toolkit-meta
---

# Report-Only Inference

`contract/KNOWLEDGE_API.md`'s v2 section states its first rule in order of importance: report-
only, forever. No automation may write vault content — a link, an enrichment, a note — from an
inferred edge without explicit human confirmation in that session. An inferred edge is a candidate
for a human decision, never an input to an autonomous write.

## The successful-corruption guard

The reason this is rule 1, not rule 4, is what it prevents: a wrong inferred edge that auto-applied
wouldn't look wrong. It would render exactly like a correct one, and the automation that applied it
would signal success — there's no error to catch downstream. `[earned: gaiafield R2 deletion bug,
2026-07-26 — the deterministic layer already produced one silent-corruption class (see
[[Deterministic-vs-Inferred-Graph-Edges]]); the statistical layer, which is wrong far more often by
construction, does not get the chance to produce a second one]`.

## Distinct from labeling

[[Confidence-Labeling-for-Inferred-Edges]] is about a consumer knowing how much to trust an edge.
This rule is stricter and orthogonal: it applies even to an edge labeled INFERRED at the highest
confidence the model produces. A high score changes how prominently a candidate gets surfaced,
never whether it can write on its own.

## What this looks like in practice

Every v2 surface in [[Gaiafield]] — `infer`, `candidates`, `surprise` — only ever reads and
reports; none of them touch vault content. `plugins/obsidian/scripts/graph.py`'s inferred-edge
functions are pure read paths over the CLI's JSON output. The `distill` skill's phase 1 presents
inferred candidates as a separately labeled block in its handoff — never merged into the
deterministic backlink/bridge lists a human might skim past and treat as equally certain.

## The companion rules it doesn't stand alone

This pairs with three more from the same contract section: inference never mutates an `extracted`
row (deleting all inferred edges restores the exact v1 graph); gates are model-calibrated, never
universal (see [[Calibration-Bias]]); traversal defaults to deterministic edges unless a caller
explicitly asks for inferred ones. Together they're why a v2 gaiafield binary can be handed to an
agent with no additional supervision — the worst it can do is show a wrong suggestion, never make
one.

## Related

- [[Confidence-Labeling-for-Inferred-Edges]]
- [[Deterministic-vs-Inferred-Graph-Edges]]
- [[Calibration-Bias]]
- [[Dead-Letter-Queues-for-Automation]]
- [[Gaiafield]]
- [[Surprise-Scoring]]
