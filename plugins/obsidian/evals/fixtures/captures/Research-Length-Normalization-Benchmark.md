---
captured: 2026-08-05
origin: research-session
source: https://example.org/ir-notes/bm25-length-normalization-benchmark
---

# BM25 length normalization benchmark

Ran the numbers instead of trusting the folklore. With the standard length normalization
(b = 0.75) a long field does NOT lose ranking against a short one for the same query terms:
across 400 queries over note-sized documents, padding a field to five times its length moved
the target document's rank by less than one position on average. The claim that a verbose
description "dilutes" keyword weight and hurts retrieval did not reproduce; the effect only
appears with normalization switched off (b = 0), which nobody ships. Conclusion: writing
descriptions as terse keyword lists to please BM25 is unnecessary.
