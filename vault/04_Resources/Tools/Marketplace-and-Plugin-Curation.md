---
description: How plugins are added to the marketplace.json and the curation waves that stage them in — core wave, second wave, private repo, archive.
status: active
created: 2026-02-13
kind: tool-landmark
topics:
  - curation
  - plugin-architecture
tags:
  - domain/toolkit-meta
---

# Marketplace and Plugin Curation

`.claude-plugin/marketplace.json` lists every plugin under `plugins/` as a source; installing one
is `claude plugin marketplace add <path>` against this repo. Curation happens in waves rather than
all at once, per `docs/PLAN.md`:

- **Core wave** — obsidian, readwise, memory, research, farsight, techref, gaiafield, feinschliff:
  the load-bearing set a fresh clone needs to be useful immediately.
- **Second wave** — [[Tech-Radar]], the fein-* media plugins ([[Feinschliff-Deck-Pipeline]]),
  [[Handoff-Skill]], [[Autoresearch-Eval-Loop]]: adds capability without being required for the
  walking skeleton.
- **Private repo** — anything carrying identity-specific data that doesn't belong in a public repo
  at all, kept entirely separate rather than gated by a flag.
- **Archive** — the frozen v1 plugins that didn't clear
  [[Scope-Discipline-for-Curated-Systems|the admission bar]] this round; re-entry is possible if
  one earns it later, not a permanent exile.

## Related

- [[Scope-Discipline-for-Curated-Systems]]
- [[Tech-Radar]]
- [[Autoresearch-Eval-Loop]]
- [[Versioned-Inter-Plugin-Contracts]]
