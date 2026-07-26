---
description: Where every deliberately-planted test case in this vault lives, and the three link clusters plus bridge notes this vault's density was built to demonstrate.
status: active
created: 2026-02-19
kind: guide
topics:
  - test-corpus
  - vault-maintenance
tags:
  - domain/toolkit-meta
---

# Test Corpus Map

This vault is documentation, a `vault init` template, and a deterministic test corpus at once
(see `docs/PLAN.md`, "The example vault"). Everything below is planted on purpose so a test suite
or eval can assert against a known-good answer rather than guessing at what the vault "should"
contain.

## The three clusters

- **toolkit-concepts** — everything under `04_Resources/Concepts/`, `04_Resources/Guides/`,
  `04_Resources/Tools/`, plus [[Alex-Vega]] and [[Config/toolkit/obsidian.md]]. The largest
  cluster, densely self-linked.
- **birding** — [[Field-Guide-Project]] and its siblings in `02_Projects/field-guide/`, plus the
  [[Birding]] area.
- **homelab** — [[Home-Lab-Migration]] and its siblings in `02_Projects/home-lab-migration/`,
  plus the [[Home-Network-Administration]] area.

## Bridge notes (deliberately cross-cluster)

- [[Alex-Vega]] — root persona, links into all three clusters as the one person who owns
  everything in the vault.
- [[Toolkit-Maintenance]] — an area in the toolkit-concepts cluster that explicitly links out to
  both project clusters as dogfooding examples for [[Farsight]] and [[Gaiafield]].
- [[Running-Evals]] — a toolkit guide that names both projects' notes as eval fixtures.
- [[Farsight]] — references both [[Field-Guide-Project|field-guide]] and
  [[Home-Lab-Migration|home-lab-migration]] content as example query targets.

## Planted edge cases

| Case | Path |
|---|---|
| Unknown frontmatter keys (`maturity`, `ring`) | `04_Resources/Tools/Tech-Radar.md` |
| Broken wikilink to a nonexistent note | `04_Resources/Guides/Vault-Maintenance-and-Linting.md` (links to a note named `Nonexistent-Note-For-Linting-Demo`, which does not exist) |
| Unicode / umlauts in title and body | `04_Resources/Concepts/Vault-Größe-und-Skalierungsschwellen.md` |
| Same title, different folders | `02_Projects/field-guide/Weekly-Review.md` and `02_Projects/home-lab-migration/Weekly-Review.md` |
| Long-prose description (BM25-dilution specimen) | `04_Resources/Concepts/Retrieval-Verification-Loop-Long-Description-Specimen.md` |
| Condensed-description sibling of the above | `04_Resources/Concepts/Retrieval-Verification-Loop-Condensed-Description-Specimen.md` |
| No frontmatter at all (parser-tolerance case) | `04_Resources/Guides/Migrating-Notes-From-Plain-Markdown.md` |
| Archived note that active notes must not link to | `05_Archive/Deprecated-Plugin-Notebooklm.md` |

Each row is a single, clearly-named note so a test can assert against an exact path rather than a
fuzzy description. If any of these paths move, this table and the corresponding test/eval
assertions both need updating in the same change — that's the point of documenting them together.

## Density target

Active notes (`02_Projects`, `03_Areas`, `04_Resources`) aim for ≥85% carrying at least one
wikilink, averaging roughly 8–12 per note, weighted toward the Related-section convention used
throughout this vault.

## Related

- [[Community-Detection-and-Bridge-Notes]]
- [[Surprise-Scoring]]
- [[Frontmatter-as-Floor-Not-Ceiling]]
- [[BM25-Dilution]]
- [[Running-Evals]]
