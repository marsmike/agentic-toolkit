---
description: A component earns its place in a curated system only if someone can name the specific behavior it delivers — a scope test that caps the listing budget at what stays nameable.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-10
created: 2026-02-10
kind: concept
topics:
  - curation
  - config-discipline
tags:
  - domain/toolkit-meta
---

# Scope Discipline for Curated Systems

A curated set of plugins, skills, or tools has a natural ceiling: past roughly two to three dozen
items, a person choosing among them can no longer hold the full set in mind, and discovery starts
to degrade regardless of how good each individual item is. Scope discipline is the practice of
admitting new items against a bar rather than letting the set grow until it hits that ceiling by
accident.

## The admission bar

If nobody can name, in one sentence, the specific behavior a component delivers that isn't already
covered by something else in the set, it doesn't belong yet — or doesn't belong at all. This is a
stronger bar than "it's useful," because almost anything is useful in isolation; the question is
whether it's *distinctly* useful next to what's already there.

## How this interacts with the graduation pattern

[[The-Graduation-Pattern]] governs whether a capability is *reliable* enough to gate merges. Scope
discipline governs whether it's *distinct* enough to be worth including at all. A component can
pass every eval and still fail this test if it duplicates something already curated — reliability
and scope are independent questions.

## Related

- [[The-Graduation-Pattern]]
- [[The-Instruction-Budget]]
- [[Marketplace-and-Plugin-Curation]]
