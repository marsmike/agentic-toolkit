# Vault Schema

The normative contract for what a vault is. Everything downstream — `core`, plugins, the Rust
engines, the example vault under `vault/` — is built against this file. The example vault is the
executable version of this contract: a schema change that isn't reflected there is a broken change
(see `docs/PLAN.md`).

## PARA folder layout

| Folder | Rules |
|---|---|
| `00_Memory/` | Agent self-memory — operational state, not vault content. Never distill into it, never enrich from it, never link to it from active notes. |
| `01_Capture/` | Inbox. Raw and untrusted, ephemeral. **Flat — no subfolders, ever.** Filenames are hyphenated and prefixed by origin (e.g. `Readwise-`, `Research-`, `<Source>-`) so a directory listing alone shows provenance. Never link *to* a capture from active content — a distilled note's source points at the original external source, never at the capture file. Remove a capture after distilling it via the vault's safe-delete surface (`contract/KNOWLEDGE_API.md`), never an irreversible raw delete. |
| `02_Projects/` | Active projects with a specific, closable outcome. One subfolder per project. |
| `03_Areas/` | Ongoing responsibilities with no end date. |
| `04_Resources/` | Reference material not tied to one project, grouped by kind. |
| `05_Archive/` | Frozen. Never create content here, never enrich here, never link here from new notes. |
| `Templates/` | Note templates. Not itself vault content. |

**Active-content filter** — semantic search, enrichment, and any generated index operate on
`02_Projects`, `03_Areas`, `04_Resources` only. `00_Memory`, `01_Capture`, and `05_Archive` are
always excluded from these operations.

## Frontmatter field table

Field names and meanings are stable — generated views, lint tooling, and plugin logic depend on
them holding still. Check whether an existing field fits before adding a new one.

| Field | Meaning | Required for |
|---|---|---|
| `description` | One-sentence purpose | Resources, Areas |
| `source` | Provenance — URL or citation | Every distilled note |
| `status` | Lifecycle stage, see below | Every distilled note |
| `processed_date` | ISO date the note was distilled | Every distilled note |
| `kind` | Note kind (`concept`, `guide`, `research-finding`, `profile`, plus project- and domain-specific values) | Resources |
| `topics` | Structured topical taxonomy | Resources |
| `methodology` | Methodology family, when applicable | Resources |
| `tags` | Freeform and/or namespaced — see below | All |
| `type` | Note type (`meeting-note`, `project-doc`, …), when applicable | — |
| `author`, `published` | Original author / publish date | External material |
| `created` | Note creation date | Most notes |
| `enrichment_targets` | Notes/profiles to notify when this note is enriched | Opt-in |

## Note lifecycle

`status` values, in the order a distilled note typically moves through them:

| Status | Meaning |
|---|---|
| `draft` | Written, not yet reviewed |
| `review` | Awaiting the human review checkpoint |
| `distilled` | Reviewed and integrated — the terminal state for most knowledge notes |
| `active` | Live, in-use (projects, areas) rather than reference material |
| `archived` | Frozen; lives in or is destined for `05_Archive/` |

## Wikilinks and tags

- Standard `[[Note Name]]` / `[[path\|Alias]]` wikilinks, used for backlinks, Related/See Also
  sections, and enrichment. Never link into `01_Capture/` or `05_Archive/` from active content.
- Tags may be plain freeform strings or namespaced `domain/value` pairs (e.g. `domain/*`,
  `status/*`) in the same `tags:` array — both forms coexist. Namespacing is a convention layered
  onto one field, not a separate mechanism.

## The frontmatter table is a floor, not a ceiling

> **Normative.** The table above is the guaranteed minimum, not an exhaustive schema. Notes carry
> additional fields in practice — template- or project-specific keys (`maturity`, `ring`,
> `aliases`, and others) accrete over a vault's life that no core tool defined. Parsers and tools
> that read frontmatter **must tolerate and preserve unknown fields**; they must never validate
> against a fixed field set, reject a note for carrying an extra key, or silently drop what they
> don't recognize on a write-back. `[earned: strict-parse failures on real vaults]`
