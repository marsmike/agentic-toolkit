---
description: An automation that can't confidently resolve something writes a record of the failure instead of guessing — borrowed from message-queue dead-letter patterns.
status: distilled
source: "(none — originated from toolkit design work; pattern name borrowed from message-queue architecture)"
processed_date: 2026-01-19
created: 2026-01-19
kind: concept
topics:
  - automation
  - reliability
tags:
  - domain/toolkit-meta
---

# Dead-Letter Queues for Automation

In message queuing, a dead-letter queue holds messages a consumer couldn't process, instead of
dropping them or retrying forever. The same shape applies to agentic automation: when a scheduled
job or distill run hits a case it can't confidently resolve — an ambiguous placement, a search
backend returning suspiciously empty results — it should write a labeled record of the failure
rather than silently guessing or silently skipping.

## Why "silently" is the operative word

A guess that turns out wrong and an explicit skip both *look* like nothing happened, from the
outside — the corruption is invisible until someone notices the missing or wrong result much
later. A dead-letter entry makes the uncertainty itself visible at the moment it occurred, which is
strictly better than a confident-looking wrong answer. See this vault's own agent memory for a
worked example of the pattern (not linked here — memory is never linked to from active notes).

## Confidence labels gate the response

Not every uncertain case deserves a full stop: a **high**-confidence guess might auto-apply with
the dead-letter entry as an audit trail; a **low**-confidence one should always stop and ask. This
is the same high/low split as [[Judgment-Calls-vs-Deterministic-Failures]] applied to a single
automation run rather than to a whole class of hooks.

## Related

- [[Judgment-Calls-vs-Deterministic-Failures]]
- [[The-Ratchet]]
- [[The-Graduation-Pattern]]
- [[Capability-Probing]]
- [[Toolkit-Maintenance]]
- [[Open-Source-Maintenance]]
- [[Two-Phase-Distillation]]
