---
description: Shipping a capability behind a low-bar eval on day one, then raising the bar over time until it graduates into the regression suite that gates merges.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-01-18
created: 2026-01-18
kind: concept
topics:
  - evals
  - continuous-delivery
tags:
  - domain/toolkit-meta
  - evals
---

# The Graduation Pattern

The tension: continuous delivery wants to ship a capability as soon as it works at all; reliability
wants nothing to merge that isn't already proven solid. The graduation pattern resolves this by
making "proven solid" a moving target the capability grows into, rather than a gate it has to
clear before existing at all.

## How it works

1. Ship the capability with a small eval set, deliberately easy, that merely proves the thing does
   something and doesn't crash.
2. As real usage surfaces failure modes, add each one as a new eval case — this is
   [[The-Ratchet]] applied to evals specifically rather than to rules.
3. Once the eval set covers the failure modes anyone has actually hit, promote it into the
   regression suite: green regression suite gates trunk merges from that point on.

A capability's evals therefore start permissive and only get stricter, never the other way —
loosening a passing eval is a bigger decision than adding a new failing one.

## Why not just gate everything from day one

An eval suite written before any real usage encodes guesses about what will go wrong, not
observations. Guessed evals either miss the real failure modes or over-constrain the feature
before anyone has used it. The graduation pattern trades a period of lower confidence for evals
that are actually earned.

## Related

- [[The-Ratchet]]
- [[Judgment-Calls-vs-Deterministic-Failures]]
- [[Dead-Letter-Queues-for-Automation]]
- [[Running-Evals]]
- [[Open-Source-Maintenance]]
- [[Model-Tiering-for-Agent-Fleets]]
