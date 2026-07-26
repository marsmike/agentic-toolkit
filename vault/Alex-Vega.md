---
description: Profile note for this example vault's fictional persona — resolution target for the "fill from Obsidian" convention.
kind: profile
status: active
created: 2026-01-12
tags:
  - profile
  - domain/toolkit-meta
enrichment_targets:
  - "[[Toolkit-Maintenance]]"
---

# Alex Vega

> **This person does not exist.** Alex Vega is a fictional persona invented for this example vault
> so that plugins, profile examples, and the two demo projects below have someone to belong to. No
> field on this page refers to a real individual.

Alex maintains a small open-source CLI tool (see [[Open-Source-Maintenance]]) and runs this vault
as their personal knowledge base — the same way the toolkit's own docs recommend. Two active
projects and a handful of ongoing areas below are Alex's, not the toolkit's.

## Snapshot

- **Role:** Independent open-source maintainer, part-time.
- **Current projects:** [[Field-Guide-Project|field-guide]] (writing a regional birding field
  guide), [[Home-Lab-Migration|home-lab-migration]] (moving self-hosted services to new hardware).
- **Ongoing areas:** [[Birding]], [[Home-Network-Administration]], [[Toolkit-Maintenance]],
  [[Open-Source-Maintenance]].
- **Vault habits:** distills captures weekly, keeps [[Index.md|Index]] current by convention
  rather than by hand — see [[Vault-First-Architecture]].

## Why a profile note

This note is the worked example behind [[Fill-From-Obsidian-Profiles]]: a plugin reading Alex's
identity finds it here or in `Config/toolkit/*.md`, never hard-coded in the plugin's own source.
The `enrichment_targets` field above means a distill run touching maintenance topics should flag
this note for review.

## Related

- [[Fill-From-Obsidian-Profiles]]
- [[Vault-First-Architecture]]
- [[Toolkit-Maintenance]]
- [[Open-Source-Maintenance]]
- [[Birding]]
- [[Home-Network-Administration]]
- [[PARA-Method]]
