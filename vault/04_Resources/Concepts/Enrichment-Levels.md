---
description: Three graded responses to a related note found above the search-score gate — backlink, inline merge, or contradiction flag — matched to how specific the relationship actually is.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-01-29
created: 2026-01-29
kind: concept
topics:
  - distillation
  - knowledge-graphs
tags:
  - domain/toolkit-meta
---

# Enrichment Levels

When a new note scores above the configured search-score gate (see
[[Semantic-Search-Score-Calibration]]) against an existing one, the response is graded rather than
binary:

- **Level 1 — backlink.** Adjacent topic, nothing specific to strengthen. Append one line to the
  existing note's Related section. This is the default and the safest choice when in doubt.
- **Level 2 — merge inline.** The new note extends or strengthens a *specific* existing section —
  insert at that exact point, plus the Level 1 backlink. Requires being able to point at the
  section; if you can't, it's Level 1.
- **Level 3 — flag contradiction.** The new note contradicts something the existing note asserts.
  Flagged adjacent to the contradicted claim, dated, never a silent overwrite of the old content.

## Why silent overwrite is the one forbidden move

Overwriting loses the fact that the vault used to believe something different, which is itself
information — a contradiction flag preserves both claims and their timestamps, letting a reader
see the history of belief rather than just its current state. This is the same instinct
[[The-Ratchet]] applies to rules: don't erase the trace of why something changed.

## Related

- [[Two-Phase-Distillation]]
- [[Semantic-Search-Score-Calibration]]
- [[The-Ratchet]]
- [[Dead-Letter-Queues-for-Automation]]
- [[Toolkit-Maintenance]]
