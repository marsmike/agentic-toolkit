# Property Schemas

Frontmatter fields this vault's tooling depends on holding still — see
`contract/VAULT_SCHEMA.md` for the normative table. That table is a floor, not a
ceiling: a note may carry additional fields no core tool defined, and every reader here
must tolerate and preserve them.

## Core fields (contract/VAULT_SCHEMA.md)

| Field | Meaning | Required for |
|---|---|---|
| `description` | One-sentence purpose | Resources, Areas |
| `source` | Provenance — URL or citation | Every distilled note |
| `status` | Lifecycle stage, see below | Every distilled note |
| `processed_date` | ISO date the note was distilled | Every distilled note |
| `kind` | Note kind (`concept`, `guide`, `research-finding`, `profile`, ...) | Resources |
| `topics` | Structured topical taxonomy | Resources |
| `tags` | Freeform and/or namespaced (`domain/*`, `status/*`) | All |
| `created` | Note creation date | Most notes |
| `enrichment_targets` | Notes/profiles to notify when this note is enriched | Opt-in |

## Lifecycle (`status`)

| Status | Meaning |
|---|---|
| `draft` | Written, not yet reviewed |
| `review` | Awaiting the human review checkpoint |
| `distilled` | Reviewed and integrated — terminal state for most knowledge notes |
| `active` | Live, in-use (projects, areas) rather than reference material |
| `archived` | Frozen; lives in or is destined for `05_Archive/` |

## Obsidian's own default properties

| Property | Type | Notes |
|---|---|---|
| `tags` | List | Searchable labels; may mix freeform and `domain/*`-namespaced forms |
| `aliases` | List | Alternative names for wikilink suggestion/resolution |
| `cssclasses` | List | CSS classes for styling in Obsidian's renderer |

## CLI form (optional Obsidian desktop CLI — see commands.md)

```bash
obsidian property:set name="status" value="distilled" file="Note Title"
obsidian property:set name="tags" value="ai,learning" file="Note Title"
```

Filesystem form (no CLI/app required) — edit the YAML frontmatter block directly with
the `Edit` tool, or use `scripts/vault_utils.py`'s `read_frontmatter`/`write_frontmatter`
if scripting a batch change; both preserve fields you didn't touch.

## Setting a newly-distilled note's properties

```yaml
---
status: distilled
processed_date: 2026-07-26
source: https://example.com/article
tags:
  - domain/ai-ml
  - domain/agent-systems
---
```

`source` must be set even when there truly is none — write `(none — <context>)`, never
`unknown`: an unparseable placeholder like `unknown` looks filled while carrying no
information, and for `processed_date` specifically it also breaks any date-scoped query.
