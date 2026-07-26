---
description: The Projects/Areas/Resources/Archive folder structure this vault and the toolkit's own schema are built on.
status: distilled
source: "Tiago Forte's PARA method (organizational framework, name-dropped as prior art)"
processed_date: 2026-01-13
created: 2026-01-13
kind: concept
topics:
  - vault-architecture
  - organization
tags:
  - domain/toolkit-meta
---

# PARA Method

Four folders, distinguished by one question each: does this have a specific, closable outcome
(**Project**), is it an ongoing responsibility with no end date (**Area**), is it reference
material not tied to either (**Resource**), or is it frozen and done (**Archive**)? See
`contract/VAULT_SCHEMA.md` for this toolkit's normative version of the layout.

## The distinction that actually matters day to day

Project vs. area is the one people misplace most: [[Field-Guide-Project|writing a field guide]]
is a project (it ends when the manuscript ships); [[Birding|birding itself]] is an area (it
doesn't end, the project just draws on it). The same pair repeats with
[[Home-Lab-Migration|the home-lab migration]] (project) and
[[Home-Network-Administration|home network administration]] (area) — a project is often just an
area's backlog reaching critical mass.

## Why archive is the strict one

`05_Archive/` is the only folder with a one-way door: nothing gets created there, nothing gets
enriched there, and active notes never link into it. That asymmetry matters for
[[Knowledge-Graphs-from-Wikilinks|graph tooling]] — an archived note with zero inbound links from
active content is the expected, healthy state, not a bug to fix.

## Related

- [[Vault-First-Architecture]]
- [[Field-Guide-Project]]
- [[Home-Lab-Migration]]
- [[Birding]]
- [[Home-Network-Administration]]
- [[Alex-Vega]]
