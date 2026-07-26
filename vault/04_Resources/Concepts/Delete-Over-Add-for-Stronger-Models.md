---
description: A stronger model needs fewer standing constraints, not more — config rules written to compensate for a weaker model's judgment become conflicting noise once the model improves.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-12
created: 2026-02-12
kind: concept
topics:
  - context-engineering
  - config-discipline
tags:
  - domain/toolkit-meta
---

# Delete-Over-Add for Stronger Models

A rule added to compensate for a model's poor judgment on some edge case is a bet on that model's
current capability level, not a timeless truth. As models get better at exactly the judgment the
rule was propping up, the rule stops helping and starts actively conflicting with the model's own
(now better) instincts — two sources of guidance disagreeing reads as noise, not safety.

## The evidence this leans on

Anthropic's own system-prompt work for Claude Code cut the large majority of its instructions with
no eval regression once the underlying model improved enough not to need them. That's the strongest
available argument that config discipline should default toward removing constraints as models
improve, not accumulating them indefinitely.

## Why this pairs with the ratchet, not against it

[[The-Ratchet]] says every rule cites the failure that earned it. This concept adds the other
half: every rule should also state what would make it safe to delete — usually "once eval X covers
this and stays green," per [[The-Graduation-Pattern]]. A ratchet without a removal condition only
ever tightens; this is what keeps it honest.

## Related

- [[The-Ratchet]]
- [[The-Instruction-Budget]]
- [[Progressive-Disclosure]]
- [[The-Graduation-Pattern]]
