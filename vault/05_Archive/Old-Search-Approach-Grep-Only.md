---
description: The grep-only search approach used before the hybrid retrieval engine existed — frozen, superseded.
status: archived
created: 2025-11-02
kind: guide
tags:
  - domain/toolkit-meta
---

# Old Search Approach — Grep Only

Before a hybrid BM25+vector engine existed, "search the vault" meant grepping for literal
substrings and nothing else. It found exact matches reliably and missed every paraphrase, every
synonym, and anything where the right note used different words than the query.

This approach is frozen here as a record of what preceded the current retrieval design — it is
not maintained, not linked to from active content, and not a fallback path any current plugin
should reach for. The retrieval engine that replaced it is documented in the active vault, not
here.

*Archived 2026-01-05 when the current retrieval approach was adopted.*
