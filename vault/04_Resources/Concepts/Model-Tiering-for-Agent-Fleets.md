---
description: Routing mechanical, high-volume work to cheap models and judgment calls to frontier models, with fan-out restricted to the frontier tier so spawn depth stays bounded.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-05
created: 2026-02-05
kind: concept
topics:
  - agent-orchestration
  - routing
tags:
  - domain/toolkit-meta
  - domain/agent-systems
---

# Model Tiering for Agent Fleets

Not every task in a multi-agent run deserves the same model. Bulk mechanical work — reformatting,
rote transforms, high-volume low-judgment passes — runs fine on a cheap or local model. Judgment
calls, and anything where a wrong call is expensive to detect after the fact, need a frontier
model doing the reasoning. See `contract/ROUTING.md` for this toolkit's normative version.

## The spawn-depth rule this implies

A cheap-tier subagent never spawns further subagents — fan-out only happens at the frontier tier.
Without this rule, a chain of cheap-model agents can spawn each other indefinitely, each one a
little worse at judging when to stop than the last, with no frontier-level check anywhere in the
chain. On ambiguity, a subagent escalates to its parent rather than guessing or spawning a helper
to resolve it — escalation keeps the judgment call at the level equipped to make it.

## An aspiration, clearly marked as one

A local-model fallback for when the API is unavailable is not yet implemented in this toolkit —
it's documented as an aspiration specifically so nothing gets built as if it already exists, with
an explicit removal condition once it ships and has eval coverage.

## Related

- [[The-Graduation-Pattern]]
- [[Judgment-Calls-vs-Deterministic-Failures]]
- [[Filesystem-vs-MCP-for-Agent-Tool-Access]]
