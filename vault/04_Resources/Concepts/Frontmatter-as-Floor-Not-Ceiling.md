---
description: The documented frontmatter field table is a guaranteed minimum, not an exhaustive schema — parsers must tolerate and preserve fields they don't recognize.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-01
created: 2026-02-01
kind: concept
topics:
  - vault-architecture
  - frontmatter
tags:
  - domain/toolkit-meta
maturity: stable
---

# Frontmatter as Floor, Not Ceiling

`contract/VAULT_SCHEMA.md` documents `description`, `status`, `source`, and a handful of other
fields — but a real vault accretes more over time: template-specific keys, project-specific keys,
fields a plugin invented for its own purposes and nobody formalized. That's expected, not drift to
correct.

## The rule this produces for tooling

A parser, linter, or plugin that reads frontmatter must tolerate a field it doesn't recognize and
must never drop it on a write-back. Validating against a fixed field set and rejecting anything
outside it is the failure mode this rule exists to prevent — it happened on a real vault
(`[earned: strict-parse failures on real vaults]`) and broke notes that were otherwise fine.

## Where the edge case lives in this vault

`04_Resources/Tools/Tech-Radar.md` carries `ring` and `maturity` fields that appear nowhere in
`contract/VAULT_SCHEMA.md`'s table, on purpose — a live check that nothing in this toolkit chokes
on an unrecognized key. See [[Test-Corpus-Map]] for the full list of planted cases like this one.

## Related

- [[Vault-First-Architecture]]
- [[Tech-Radar]]
- [[Test-Corpus-Map]]
- [[The-Ratchet]]
