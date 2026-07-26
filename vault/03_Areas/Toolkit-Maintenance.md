---
description: Alex's ongoing responsibility for keeping this vault and its toolkit plugins healthy — the area that dogfoods the toolkit against Alex's own projects.
status: active
created: 2026-01-12
tags:
  - domain/toolkit-meta
  - area
enrichment_targets:
  - "[[Alex-Vega]]"
---

# Toolkit Maintenance

Keeping this vault and its plugin configuration healthy: running `toolkit doctor` periodically,
distilling the capture inbox before it grows stale, and re-tuning profile settings like the search
score gate in [[Semantic-Search-Score-Calibration]] when the embedding model changes.

## Why this note is a bridge

This area is where the toolkit's own concepts get exercised against Alex's actual content, not
just described abstractly. Concretely:

- [[Running-Evals]] uses notes from both [[Field-Guide-Project|field-guide]] and
  [[Home-Lab-Migration|home-lab-migration]] as fixtures when checking that search and enrichment
  behave sensibly on ordinary project notes, not just on concept notes about themselves.
- [[Farsight]] and [[Gaiafield]] get manually spot-checked against queries over both projects —
  "find everything related to the storage shelf" should surface [[Hardware-Inventory]] and
  [[Weekly-Review]] without also pulling in birding notes that happen to share a word.
- [[Two-Phase-Distillation]] and [[Enrichment-Levels]] are the rules this area's weekly distill
  pass actually follows, not just documents.

## Related

- [[Alex-Vega]]
- [[Running-Evals]]
- [[Farsight]]
- [[Gaiafield]]
- [[Two-Phase-Distillation]]
- [[Enrichment-Levels]]
- [[Semantic-Search-Score-Calibration]]
- [[Open-Source-Maintenance]]
- [[Dead-Letter-Queues-for-Automation]]
