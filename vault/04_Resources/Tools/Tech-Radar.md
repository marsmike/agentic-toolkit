---
description: Renders the toolkit's own state-of-the-art positioning into docs/ as a public radar view — second-wave plugin, and the carrier of this vault's unknown-frontmatter-keys test case.
status: active
created: 2026-02-09
kind: tool-landmark
topics:
  - positioning
  - documentation
tags:
  - domain/toolkit-meta
maturity: emerging
ring: trial
---

# Tech Radar

Second-wave plugin that renders the toolkit's own technology positioning into `docs/` as a public,
readable radar view — the same flywheel loop described in `docs/PLAN.md`: research and capture feed
the vault, the vault feeds this radar, the radar's public view feeds back into what gets curated
next.

## The `maturity` and `ring` fields above

Those two frontmatter keys appear nowhere in `contract/VAULT_SCHEMA.md`'s field table — they're
this plugin's own radar-specific vocabulary (`ring` being the classic tech-radar
adopt/trial/assess/hold quadrant, `maturity` a coarser adopt-readiness signal), added because this
plugin needed them, not because a core schema anticipated them. That's the live instance of
[[Frontmatter-as-Floor-Not-Ceiling]] this vault plants deliberately — see [[Test-Corpus-Map]] for
where else this pattern shows up.

## Relationship to other second-wave plugins

Ships alongside the fein-* media plugins ([[Feinschliff-Deck-Pipeline]]), [[Handoff-Skill]], and
[[Autoresearch-Eval-Loop]] — bundled by curation wave in `docs/PLAN.md`, not by any code
dependency between them (plugins never depend on siblings, per
[[Versioned-Inter-Plugin-Contracts]]).

## Related

- [[Frontmatter-as-Floor-Not-Ceiling]]
- [[Test-Corpus-Map]]
- [[Scope-Discipline-for-Curated-Systems]]
- [[Marketplace-and-Plugin-Curation]]
