---
description: The core Python CLI — vault init, doctor, and profile resolution — the surface every plugin and every new user touches first.
status: active
created: 2026-02-06
kind: tool-landmark
topics:
  - cli
  - vault-architecture
tags:
  - domain/toolkit-meta
---

# Toolkit CLI

`core`'s command-line surface, three commands wide by design (see
[[Scope-Discipline-for-Curated-Systems]] for why that's a feature, not a gap):

- **`toolkit vault init [path]`** — scaffolds a new vault from this example vault's template:
  the PARA folders, `Templates/`, and a `CLAUDE.md` copied from `contract/templates/VAULT_CLAUDE.md`.
  Defaults to `./vault` when no path is given.
- **`toolkit doctor`** — reports which vault is active and how it was resolved (env var vs.
  fallback), PARA folder/note counts, frontmatter parse errors, profile completeness per plugin,
  and surfaces any dead-letter entries waiting for review (see
  [[Dead-Letter-Queues-for-Automation]]). Since R3 it also reports a graph section — node/edge/
  dangling/boundary counts and index freshness when a [[Gaiafield]] binary and database are
  present, `"gaiafield not present"` otherwise — and since R5 (v2), an `inference` sub-section
  nested under it: model name, high/low gates, and inferred/ambiguous edge counts once `gaiafield
  infer` has run, distinguishing a v1 binary ("engine lacks inference") from a v2 binary that just
  hasn't been inferred yet ("not inferred") via [[Capability-Probing]] rather than a version
  string. Doctor only ever reports this state — it never runs `index` or `infer` itself.
- **`toolkit profile`** — inspects a plugin's resolved profile: which of env var, vault note, or
  shipped default supplied each setting. See [[Fill-From-Obsidian-Profiles]].

## Resolution order it implements

`TOOLKIT_VAULT` environment variable, then `./vault` as fallback — documented normatively in
`contract/PROFILE.md`. Tests and evals always target `./vault` regardless of what
`TOOLKIT_VAULT` is set to in the running environment, so a real vault reached that way is never
touched by CI.

## Related

- [[Fill-From-Obsidian-Profiles]]
- [[Dead-Letter-Queues-for-Automation]]
- [[Scope-Discipline-for-Curated-Systems]]
- [[Quick-Start]]
- [[Using-Your-Own-Vault]]
- [[Troubleshooting-Toolkit-Doctor]]
- [[Gaiafield]]
- [[Capability-Probing]]
