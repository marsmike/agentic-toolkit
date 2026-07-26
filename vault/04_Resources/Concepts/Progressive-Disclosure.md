---
description: Loading only what the current step needs — an always-loaded core plus depth that surfaces on demand — applied to agent context the way UI design applies it to interfaces.
status: distilled
source: "(none — originated from toolkit design work; the UX term predates this application)"
processed_date: 2026-01-20
created: 2026-01-20
kind: concept
topics:
  - context-engineering
  - config-discipline
tags:
  - domain/toolkit-meta
  - domain/agent-systems
---

# Progressive Disclosure

In interface design, progressive disclosure means showing a novice the common controls first and
hiding advanced ones behind a click. Applied to agent context, the same shape solves a different
problem: an always-loaded file (a `CLAUDE.md`) competes for the same limited instruction budget as
every other always-loaded file, while a skill's `references/` only costs tokens when that skill
actually runs.

## The rule this produces

Anything that must hold even when no skill is invoked belongs in the always-loaded file. Anything
that's procedural depth — the full workflow, the failure modes by name, the edge-case handling —
belongs in a skill's reference material instead. See [[The-Instruction-Budget]] for why this
split exists at all, and [[Ambient-vs-On-Demand-Context]] for the sharper version of the same
distinction applied specifically to skills vs. contract files.

## The trap

It's tempting to add "just one more paragraph" to the always-loaded file because it feels safer
than trusting a skill to load correctly. Every paragraph added there is paid on every single turn,
not just the turns that need it — the cost is invisible per-addition and only shows up in
aggregate.

## Related

- [[The-Instruction-Budget]]
- [[Ambient-vs-On-Demand-Context]]
- [[Delete-Over-Add-for-Stronger-Models]]
- [[Vault-First-Architecture]]
- [[The-Ratchet]]
