# agentic-toolkit

This file routes; it does not answer. It is the one entry file for every agent (Claude Code
reads `AGENTS.md` when no `CLAUDE.md` is on the path, so there is none). [earned: 2026-09-23,
R12 — a `CLAUDE.md` next to it would silently win and hide this file]

| Question about | Read |
|---|---|
| What a vault is, frontmatter, folders, generated navigation | `contract/VAULT_SCHEMA.md` |
| Plugin config, "fill from Obsidian", own vault | `contract/PROFILE.md` |
| How plugins query knowledge | `contract/KNOWLEDGE_API.md` |
| Which model for which work | `contract/ROUTING.md` |
| Tuning judgments, auditing descriptions | `docs/MAINTAINING.md` |
| Running the pipeline as a Claude cloud routine | `docs/cloud-routine.md` |
| Why anything is the way it is | `docs/PLAN.md` |

## Skills

Six, each a plain Markdown file: any agent can read one and follow it, with or without the
plugin installed (`$CLAUDE_PLUGIN_ROOT` in a skill is its plugin folder, e.g. `plugins/obsidian`).

| Skill | File | For |
|---|---|---|
| `obsidian:distill` | `plugins/obsidian/skills/distill/SKILL.md` | captures → linked, sourced notes |
| `obsidian:pipeline` | `plugins/obsidian/skills/pipeline/SKILL.md` | the unattended run: sources, distill, index, maps, Now, commit |
| `obsidian:vault` | `plugins/obsidian/skills/vault/SKILL.md` | reading, writing and searching notes; vault health |
| `radar:radar` | `plugins/radar/skills/radar/SKILL.md` | the feed radar and Kagi |
| `handoff:handoff` | `plugins/handoff/skills/handoff/SKILL.md` | save or resume a session handoff |
| `memory:distill-memory` | `plugins/memory/skills/distill-memory/SKILL.md` | session records → agent memory notes |

Readwise has no skill: the pipeline runs `plugins/readwise/scripts/ingest.py`.

## Working on a real vault

A session in this repo (a Claude cloud task, or any machine) reaches the owner's vault through
git, never through a copy of the code in the vault:

```bash
scripts/cloud-vault.sh open                  # clone or update $TOOLKIT_VAULT_REMOTE into .vault-live/
export TOOLKIT_VAULT="$PWD/.vault-live"      # every script and skill now targets it
# read .vault-live/AGENTS.md first, then Now.md → Index.md → Maps/; work with the skills
scripts/cloud-vault.sh close --distilled N --note "cloud: <what>"   # rebuild, secret scan, commit, push
```

- `.vault-live/` is git-ignored here: never commit the vault into the toolkit.
- Keys come from the environment, never from a file; check them by name only (`open` prints
  which are set). Without a key, each script prints `SKIPPED` and the work goes on without it.
- Tests and evals still run against `./vault` only, never `.vault-live/`.

[earned: 2026-09-23, R12 — cloud sessions reach the vault through git, and the vault holds a live
key in files git ignores] **Removal condition:** drop this section if cloud sessions stop
working on a real vault, or the vault moves to a service with its own access control.

## Hard rules

Plugins depend on `core`/`contract` only, never on a sibling plugin.
Tests and evals run against `./vault` only — never against a user's vault.
Every new rule here cites the dated failure that earned it and names its removal condition.
