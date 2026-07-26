---
description: Every standing rule in a config or contract cites the dated incident that earned it, so the rule set only ever tightens in response to a real failure, never on speculation.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-01-18
created: 2026-01-18
kind: concept
topics:
  - config-discipline
  - reliability
tags:
  - domain/toolkit-meta
---

# The Ratchet

A rule earns its place by citing the dated failure it prevents — `[earned: <short name>,
<date>]` — rather than by sounding prudent in the abstract. This does two things at once: it makes
the rule set self-documenting (anyone can trace a rule back to why it exists) and it makes rules
removable on the same evidence basis they were added on — a rule whose cited failure mode no
longer applies (a dependency upgraded, a tool fixed) can be deleted, not just accumulated forever.

## The ratchet only turns one way per rule

New rules only get added in response to something that actually happened — never "this seems like
it could go wrong." That discipline keeps the rule set from growing unboundedly on precaution
alone, which is the same failure mode [[The-Instruction-Budget]] describes at the level of the
whole config, not just individual rules.

## Pairs with a removal condition

A rule without a stated removal condition tends to outlive the failure it was written for. Every
rule in this toolkit's own contract states one — see [[Delete-Over-Add-for-Stronger-Models]] for
the companion argument that stronger models need fewer standing constraints, not more.

## Related

- [[The-Graduation-Pattern]]
- [[Judgment-Calls-vs-Deterministic-Failures]]
- [[The-Instruction-Budget]]
- [[Delete-Over-Add-for-Stronger-Models]]
- [[Dead-Letter-Queues-for-Automation]]
- [[Open-Source-Maintenance]]
- [[Anonymized-Failure-Repros]]
