---
description: Two hook classes — one auto-enforces a deterministic, unambiguous failure, the other stops and asks because the right answer depends on judgment a hook can't encode.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-15
created: 2026-02-15
kind: concept
topics:
  - automation
  - reliability
tags:
  - domain/toolkit-meta
---

# Judgment Calls vs. Deterministic Failures

Not every guardrail should behave the same way when triggered. A **ratchet hook** catches a
deterministic failure — a delete against a protected path, a malformed frontmatter write — where
the correct response is unambiguous and safe to automate: block it, every time, no exceptions. A
**stop-and-ask hook** catches something that needs a judgment call — an enrichment that might be
Level 2 or might be Level 3, a placement that could go in either of two areas — where forcing an
automated answer risks a confidently wrong one.

## Why conflating the two is the failure mode

Auto-enforcing a judgment call produces silent bad decisions at scale — exactly the corruption
[[Confidence-Labeling-for-Inferred-Edges]] and [[Dead-Letter-Queues-for-Automation]] guard against
elsewhere. Treating a deterministic failure as a judgment call, on the other hand, produces
needless interruptions for something that never needed a human in the loop at all. The two hook
classes exist so each failure gets routed to the response that actually fits it.

## Where the line gets drawn

If two competent operators would give the same answer without discussion, it's deterministic —
automate it, no exceptions. If they might reasonably disagree, it's judgment — log it as a
decision, don't silently pick one.

## Related

- [[Dead-Letter-Queues-for-Automation]]
- [[Confidence-Labeling-for-Inferred-Edges]]
- [[The-Ratchet]]
- [[The-Observer-Pattern]]
- [[Open-Source-Maintenance]]
