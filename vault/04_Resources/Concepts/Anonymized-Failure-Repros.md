---
description: Turning a real, dated failure into a minimal, anonymized regression case — the public half of the ratchet, shareable without exposing what actually broke or for whom.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-20
created: 2026-02-20
kind: concept
topics:
  - reliability
  - evals
tags:
  - domain/toolkit-meta
---

# Anonymized Failure Repros

[[The-Ratchet]] says every rule cites the dated failure that earned it. That citation is easy to
keep private-safe when the rule lives in an internal contract — but a public, open-source ratchet
needs the failure itself to be shareable too, not just referenced. An anonymized repro is the
smallest version of a real incident that still reproduces the failure, with anything
identifying — names, specific data, which vault or customer hit it — stripped out.

## Why minimal matters as much as anonymized

A repro that keeps every irrelevant detail from the original incident is harder to turn into a
regression case: the eval ends up asserting against incidental specifics rather than the actual
mechanism that failed. Reducing to the smallest reproducing case is the same discipline
[[Atomic-Notes]] applies to note-sizing, applied here to failure cases instead of ideas.

## How it feeds the graduation pattern

Once anonymized and minimal, a repro becomes a new eval case under [[The-Graduation-Pattern]] —
this is the mechanism by which "a real failure happened" turns into "the regression suite now
catches this," which is the whole point of citing failures in the first place rather than just
writing rules from intuition.

## Related

- [[The-Ratchet]]
- [[The-Graduation-Pattern]]
- [[Atomic-Notes]]
- [[Running-Evals]]
- [[Autoresearch-Eval-Loop]]
