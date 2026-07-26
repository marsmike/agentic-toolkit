---
description: The core-wave plugin — distill workflow, capture handling, and the retrieval-verification maintenance skill, ported from the v1 monorepo.
status: active
created: 2026-02-07
kind: tool-landmark
topics:
  - vault-maintenance
  - distillation
tags:
  - domain/toolkit-meta
---

# Obsidian Plugin

The first plugin curated onto the platform, and the one this example vault is built to exercise
end to end. Owns the [[The-Distill-Workflow|distill workflow]]
([[Two-Phase-Distillation]], [[Enrichment-Levels]]), capture-inbox conventions
([[Capture-Conventions]]), and a maintenance skill implementing
[[Retrieval-Verification-Loop|the retrieval-verification loop]] over a batch of existing notes.

## What changed from the v1 version

Vendored dependencies dropped in favor of `uv`-managed ones; the profile convention
([[Fill-From-Obsidian-Profiles]]) replaced hard-coded identity; the retrieval-verification
maintenance skill is new, not carried over. Skill reference files stay within the budget
documented in this repo's design notes — see [[The-Instruction-Budget]] and
[[Ambient-vs-On-Demand-Context]] for why that split matters.

## What it depends on

`core` and `contract` only — never a sibling plugin, per
[[Versioned-Inter-Plugin-Contracts]]. Where it needs search or graph queries, it calls
[[Farsight]] or [[Gaiafield]] through their CLI, falling back to grep-based search until an engine
ships that capability.

## Related

- [[The-Distill-Workflow]]
- [[Two-Phase-Distillation]]
- [[Enrichment-Levels]]
- [[Capture-Conventions]]
- [[Fill-From-Obsidian-Profiles]]
- [[Retrieval-Verification-Loop]]
