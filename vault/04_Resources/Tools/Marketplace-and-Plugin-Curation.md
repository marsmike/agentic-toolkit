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
is `claude plugin marketplace add <path>` against this repo. As shipped, that file registers
exactly three plugins — this is the current, verified reality, not a roadmap summary:

- **obsidian** — the vault-contract reference implementation: CLI operations, search, graph-aware
  distill, retrieval-verification maintenance. See [[Obsidian-Plugin]].
- **readwise** — Readwise ingestion into origin-prefixed `01_Capture/` notes. See
  [[Readwise-Plugin]].
- **memory** — session-end capture and on-demand distillation into `00_Memory/`.

[[Farsight]] and [[Gaiafield]] are **not** marketplace entries — they're native Rust engine
binaries that plugins shell out to (see [[CLI-in-JSON-out-Contracts]]), not Claude Code plugins
themselves, so they have no `plugins/` source and never appear in `marketplace.json`.

## Roadmap — not yet reality

`docs/PLAN.md` lays out further curation waves as the plan of record, but none of the following has
landed in `marketplace.json` as of this writing. Treat everything below as intent, not a shipped
inventory:

- **Planned core wave** — research, techref, feinschliff joining the three above.
- **Planned second wave** — [[Tech-Radar]], the fein-* media plugins
  ([[Feinschliff-Deck-Pipeline]]), [[Handoff-Skill]], [[Autoresearch-Eval-Loop]]: adds capability
  without being required for the walking skeleton.
- **Planned private repo** — anything carrying identity-specific data that doesn't belong in a
  public repo at all, kept entirely separate rather than gated by a flag.
- **Planned archive** — the frozen v1 plugins that didn't clear
  [[Scope-Discipline-for-Curated-Systems|the admission bar]] this round; re-entry is possible if
  one earns it later, not a permanent exile.

Re-verify against `.claude-plugin/marketplace.json` directly before citing this note as proof of
what's installable — the roadmap section drifts out of sync with reality by design (it's staged
work, not a snapshot). `scripts/docscheck.sh` mechanically diffs this note's shipped-list against
the marketplace file so the two can't silently diverge further.

## Related

- [[Scope-Discipline-for-Curated-Systems]]
- [[Obsidian-Plugin]]
- [[Readwise-Plugin]]
- [[Farsight]]
- [[Gaiafield]]
- [[CLI-in-JSON-out-Contracts]]
- [[Tech-Radar]]
- [[Autoresearch-Eval-Loop]]
- [[Versioned-Inter-Plugin-Contracts]]
