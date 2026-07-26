---
description: Splitting capture processing into an analyze-only phase with a human checkpoint, then a write phase — so an agent never files or enriches a note without a review step.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-01-28
created: 2026-01-28
kind: concept
topics:
  - distillation
  - capture
tags:
  - domain/toolkit-meta
---

# Two-Phase Distillation

**Phase 1 — analyze only.** Read the capture, search for related existing notes, propose
placement and enrichment levels, then stop. Nothing gets written yet. **Phase 2 — write,** only
after a human confirms, redirects, or narrows the proposal: create the note, execute the
enrichments, remove the capture from the inbox.

## Why one checkpoint and not zero or two

Zero checkpoints means every misjudged placement or over-eager enrichment silently becomes
permanent vault structure — see [[Enrichment-Levels]] for how bad this can get for the note being
enriched, not just the new one. More than one checkpoint turns a routine operation into a
negotiation, which most captures don't warrant. One checkpoint, positioned right before anything
becomes hard to undo, is the minimum that catches the failure modes that actually happen.

## The checkpoint is skippable, deliberately

An explicit `--auto` or "non-interactive" instruction skips the pause — batch-processing a large
capture backlog shouldn't require confirming each one individually if the operator has already
decided to trust the run. What doesn't count as that instruction: a generic "distill these files,"
which is not itself permission to skip review.

## Related

- [[Enrichment-Levels]]
- [[Dead-Letter-Queues-for-Automation]]
- [[Capture-Conventions]]
- [[The-Distill-Workflow]]
- [[Toolkit-Maintenance]]
