---
description: Carries the self-improvement loop — research findings feed evals, evals feed the graduation pattern — the one second-wave plugin explicitly required to survive curation.
status: active
created: 2026-02-12
kind: tool-landmark
topics:
  - evals
  - research
tags:
  - domain/toolkit-meta
---

# Autoresearch Eval Loop

Closes the loop `docs/PLAN.md` calls the flywheel: research and capture feed the vault, distilled
findings surface capability gaps, those gaps become new low-bar evals under
[[The-Graduation-Pattern]], and passing evals graduate into the regression suite that gates trunk
merges. Marked in the curation plan as a plugin that must survive whatever else gets cut in later
waves, because without it the graduation pattern has no automatic source of new eval cases — it
would depend entirely on a human noticing gaps by hand.

## Relationship to Running Evals

[[Running-Evals]] documents how to invoke and read eval runs manually. This plugin is what
generates new candidate evals in the first place, from real research and capture activity rather
than from someone sitting down to write a test suite from scratch.

## Related

- [[The-Graduation-Pattern]]
- [[Running-Evals]]
- [[The-Ratchet]]
- [[Scope-Discipline-for-Curated-Systems]]
