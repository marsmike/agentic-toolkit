---
description: The shape a new plugin must follow to be curated onto the platform — depends only on core/contract, reads profiles the standard way, ships evals.
status: active
created: 2026-02-15
kind: guide
topics:
  - plugin-architecture
  - onboarding
tags:
  - domain/toolkit-meta
---

# Writing a Plugin

A new plugin earns curation by meeting a short, specific list of requirements — not by being
generally good software:

1. **Depends only on `core` and `contract`.** Never imports from a sibling plugin. Composition
   with another plugin happens through a documented vault-note contract — see
   [[Versioned-Inter-Plugin-Contracts]] — never a direct call.
2. **Reads identity through the profile convention.** If it needs configuration, it ships a
   `profile.example.md` and follows the resolution order in [[Fill-From-Obsidian-Profiles]] —
   nothing plugin-specific hard-coded in source.
3. **Respects `contract/VAULT_SCHEMA.md` placement rules.** Never writes into `05_Archive/`,
   never deletes irreversibly, tolerates unknown frontmatter fields on anything it reads (see
   [[Frontmatter-as-Floor-Not-Ceiling]]).
4. **Ships evals that follow the graduation pattern.** Starts permissive, tightens from observed
   failures — see [[The-Graduation-Pattern]] and [[Running-Evals]].
5. **Clears the scope test.** Someone can state, in one sentence, the specific behavior it
   delivers that nothing else curated already covers — see
   [[Scope-Discipline-for-Curated-Systems]].

## Where it lands

New plugins enter through a curation wave, documented in
[[Marketplace-and-Plugin-Curation]] — not added directly to the core wave without first proving
itself in a later one.

## Related

- [[Versioned-Inter-Plugin-Contracts]]
- [[Fill-From-Obsidian-Profiles]]
- [[The-Graduation-Pattern]]
- [[Scope-Discipline-for-Curated-Systems]]
- [[Marketplace-and-Plugin-Curation]]
