---
description: A similarity score's meaning is specific to the embedding model that produced it — 0.70 on one model is not 0.70 on another, so the enrichment gate must be recalibrated per model.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-06
created: 2026-02-06
kind: concept
topics:
  - retrieval
  - profiles
tags:
  - domain/toolkit-meta
---

# Semantic Search Score Calibration

A cosine similarity of 0.70 means something different depending on which embedding model produced
the vectors — a small, English-centric model and a large multilingual one don't distribute scores
the same way at all. Treating "0.70" as a universal constant rather than a per-model calibration
is a quiet source of bad enrichment decisions: too permissive on one model floods a note with
irrelevant backlinks, too strict on another silently drops real connections.

## Where the number actually lives

The default gate ships as a documented placeholder (0.70) in `contract/PROFILE.md`, and a real
vault overrides it in its own profile note — see
[[Config/toolkit/obsidian.md|this vault's example profile]], which sets
`search_score_gate` explicitly rather than trusting the shipped default to be right for whatever
embedding model is actually configured.

## Consequence for enrichment

[[Enrichment-Levels]] only apply above this gate. Recalibrating the gate after a model swap isn't
optional maintenance — until it happens, every enrichment decision made in between is working off
thresholds tuned for a different model's score distribution.

## Related

- [[Enrichment-Levels]]
- [[Fill-From-Obsidian-Profiles]]
- [[Hybrid-Retrieval]]
- [[Calibration-Bias]]
- [[Toolkit-Maintenance]]
