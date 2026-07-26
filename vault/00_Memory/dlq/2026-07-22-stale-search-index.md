---
description: Dead-letter entry — a distill run that could not confidently place a capture and stopped rather than guessing.
status: active
created: 2026-07-22
tags:
  - domain/toolkit-meta
confidence: low
---

# DLQ — stale search index during distill, 2026-07-22

**What happened:** the distill workflow searched for related notes before filing
`Readwise-Hybrid-Search-Landscape.md`, and the search backend returned zero hits for a query that
should have matched at least [[Hybrid-Retrieval]] and [[Semantic-Search-Score-Calibration]]
directly. Rather than filing the capture with no enrichment (which would silently look like "no
related notes exist"), the run stopped and wrote this entry instead.

**Why it's here and not just a skipped step:** a distill run that finds nothing and proceeds
looks identical, from the outside, to a distill run that correctly found nothing. The failure
mode this guards against is silent — the note gets filed either way; only the DLQ entry records
that the *search step itself* was untrustworthy that time. See [[Dead-Letter-Queues-for-Automation]]
for the general pattern this is an instance of.

**Resolution:** on manual retry the index had gone stale after an unrelated bulk edit; a reindex
fixed it and the capture was refiled normally. Confidence label: **low** — auto-retry was not
attempted because a stale index and a genuinely-empty result look the same from the caller's side,
and guessing wrong here means a silent miss, not a visible error.

## Related

- [[Dead-Letter-Queues-for-Automation]]
- [[Semantic-Search-Score-Calibration]]
- [[Hybrid-Retrieval]]
- [[Two-Phase-Distillation]]
