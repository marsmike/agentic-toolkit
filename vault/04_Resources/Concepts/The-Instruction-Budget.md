---
description: Every always-loaded config file competes for the same shared pool of instruction slots — the budget is per-agent-context, not per-file, so adding to one file taxes all the others.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-11
created: 2026-02-11
kind: concept
topics:
  - context-engineering
  - config-discipline
tags:
  - domain/toolkit-meta
---

# The Instruction Budget

A global config file, a repo-level config file, and a vault-level config file all load into the
same context window at once. Thinking of each file's length limit independently misses the actual
constraint: there is one shared pool of instruction slots across every tier that loads
simultaneously, and a line added to any one of them subtracts from what the other tiers can afford
before the model's attention degrades.

## What this changes about writing a rule

The question isn't "does this file have room for one more paragraph" — it's "is this paragraph
worth its share of the budget every other always-loaded file is also drawing from." That's a much
higher bar, and it's why [[Progressive-Disclosure]] pushes procedural depth into skills instead:
a skill's reference material only draws from the budget on the turns it's actually loaded.

## Consequence for this toolkit's own files

The repo's own top-level `CLAUDE.md` is a router, not an answerer — it points into `contract/` and
`docs/` rather than duplicating their content, precisely so it stays cheap on every turn whether or
not those deeper files are needed.

## Related

- [[Progressive-Disclosure]]
- [[Delete-Over-Add-for-Stronger-Models]]
- [[Ambient-vs-On-Demand-Context]]
- [[The-Ratchet]]
