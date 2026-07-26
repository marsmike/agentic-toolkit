---
description: The end-to-end procedure for turning a raw capture into an integrated vault note — analyze, checkpoint, write, enrich.
status: active
created: 2026-02-04
kind: guide
topics:
  - distillation
  - capture
tags:
  - domain/toolkit-meta
---

# The Distill Workflow

The procedure behind [[Two-Phase-Distillation]], spelled out as steps rather than as the concept
alone:

1. Read the capture in full — don't skim; a distilled note built on a partial read is the source
   of most placement mistakes.
2. Search the vault for related existing notes (see [[Hybrid-Retrieval]] /
   [[Farsight]]). No search backend, no keyword fallback — if search fails, stop rather than
   guessing at relatedness.
3. Propose: placement (which PARA folder, existing note to enrich vs. new note), and enrichment
   levels for anything found above the search-score gate (see
   [[Semantic-Search-Score-Calibration]], [[Enrichment-Levels]]).
4. **Stop.** This is the checkpoint. Wait for confirmation, redirection, or narrowing.
5. Write the note: frontmatter per `contract/VAULT_SCHEMA.md`, `source` and `status: distilled` if
   applicable, execute the enrichments at their proposed levels, remove the capture from
   `01_Capture/`.

## Checking for prior distillation first

Before step 5, grep the capture's source identifier (an article URL, a tweet ID) against
same-week notes' `source` fields — captures from different origins collide on the same underlying
material more often than seems likely. See [[Capture-Conventions]] for the naming convention that
makes this grep tractable.

## Related

- [[Two-Phase-Distillation]]
- [[Enrichment-Levels]]
- [[Capture-Conventions]]
- [[Semantic-Search-Score-Calibration]]
- [[Hybrid-Retrieval]]
- [[Dead-Letter-Queues-for-Automation]]
