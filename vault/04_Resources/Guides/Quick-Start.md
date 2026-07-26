---
description: Clone the repo, install a plugin, run one skill against the example vault — the shortest path from zero to a working toolkit.
status: active
created: 2026-02-01
kind: guide
topics:
  - onboarding
tags:
  - domain/toolkit-meta
---

# Quick Start

The whole point of this example vault is that a fresh clone works immediately, against it, with
no setup beyond the clone. This guide is the shortest path proving that.

## Steps

1. Clone the repo. `./vault` — this vault — is already present; nothing to initialize.
2. Add the marketplace and install a plugin: `claude plugin marketplace add <path-to-repo>`, then
   install `obsidian` (see [[Obsidian-Plugin]]).
3. Run `toolkit doctor` (see [[Toolkit-CLI]]) — it should report `./vault` as the active vault,
   resolved by fallback (no `TOOLKIT_VAULT` set), and profile completeness for the plugin just
   installed.
4. Invoke the plugin's distill skill against something in `01_Capture/` — any of the three example
   captures work — and follow [[The-Distill-Workflow]].

## What "it works" means here

Concretely: the skill reads a capture, proposes a placement somewhere under `02_Projects`,
`03_Areas`, or `04_Resources`, searches for related notes, and stops for review before writing
anything. If that loop completes, the stranger test this repo's own `docs/PLAN.md` describes has
passed.

## Next steps

- Point the toolkit at your own vault instead: [[Using-Your-Own-Vault]].
- Understand the profile convention before customizing anything: [[Profiles-and-Config]].

## Related

- [[Toolkit-CLI]]
- [[Obsidian-Plugin]]
- [[The-Distill-Workflow]]
- [[Using-Your-Own-Vault]]
- [[Profiles-and-Config]]
