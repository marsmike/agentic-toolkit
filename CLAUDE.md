# agentic-toolkit

This file routes; it does not answer.

| Question about | Read |
|---|---|
| What a vault is, frontmatter, folders | `contract/VAULT_SCHEMA.md` |
| Plugin config, "fill from Obsidian", own vault | `contract/PROFILE.md` |
| How plugins query knowledge | `contract/KNOWLEDGE_API.md` |
| Which model for which work | `contract/ROUTING.md` |
| Why anything is the way it is | `docs/PLAN.md` |

Hard rules: plugins depend on `core`/`contract` only, never on a sibling plugin.
Tests and evals run against `./vault` only — never against a user's vault.
Every new rule here cites the dated failure that earned it and names its removal condition.
