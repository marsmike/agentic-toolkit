---
description: Distinguishing what must be true even when no skill is running from what only needs to be known while a specific workflow executes — the sharper, file-placement version of progressive disclosure.
status: review
created: 2026-02-14
kind: concept
topics:
  - context-engineering
  - config-discipline
tags:
  - domain/toolkit-meta
---

# Ambient vs. On-Demand Context

*Status: review — drafted, awaiting a check against how the obsidian plugin's own skill split
actually turned out in practice before this is considered settled.*

Two kinds of context an agent needs: ambient (true at all times — placement rules, hard
requirements, what never to do) and on-demand (only relevant while a specific workflow is
running — the exact steps of a sixteen-part process, failure modes catalogued by name). Loading
on-demand content ambiently wastes budget on every turn that doesn't need it; loading ambient
content only on-demand means it's silently absent on every turn a skill *isn't* invoked, which for
a hard requirement is a correctness bug, not just an inefficiency.

## The placement test this implies

For any given rule, ask: does this need to hold even when the relevant skill hasn't been
invoked this turn? If yes, it belongs in the always-loaded file (a contract document, a vault
`CLAUDE.md`). If no — it's procedure, not a standing requirement — it belongs in that skill's
`references/`, loaded only when the skill runs.

## Related

- [[Progressive-Disclosure]]
- [[The-Instruction-Budget]]
- [[Delete-Over-Add-for-Stronger-Models]]
