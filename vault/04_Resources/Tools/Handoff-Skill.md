---
description: Saves a portable snapshot of in-progress work so another session or tool can resume it — a second-wave plugin built directly on vault-first architecture.
status: active
created: 2026-02-11
kind: tool-landmark
topics:
  - continuity
  - vault-architecture
tags:
  - domain/toolkit-meta
---

# Handoff Skill

Writes a portable handoff note — enough state that a different session, or a different tool
entirely, can pick up unfinished work without re-deriving context from scratch. A direct
application of [[Vault-First-Architecture]]: the handoff is a plain file, not a proprietary session
export, so anything that can read the vault can resume from it.

## Where it fits relative to agent memory

A handoff note is deliberately not the same thing as this vault's `00_Memory/` journal — memory is
this agent's own ongoing operational state; a handoff is a one-shot snapshot meant to be picked up
by *any* session, including a different agent or a human. The two don't compete for the same
folder or the same lifecycle.

## Related

- [[Vault-First-Architecture]]
- [[Two-Phase-Distillation]]
- [[Toolkit-Maintenance]]
