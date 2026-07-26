<!--
Maintainers: this file is installed by `toolkit vault init` as the CLAUDE.md of every new vault.
It is always loaded, so it carries only hard requirements — rules that must hold even when no
skill has been invoked. Procedural depth (the full distill workflow, placement heuristics, failure
modes by name) belongs in a skill's references/, loaded only on invocation. If you're tempted to
add detail here, it probably belongs in a skill instead. See ../KNOWLEDGE_API.md and
../VAULT_SCHEMA.md for the rules this file assumes.
-->

# CLAUDE.md — This Vault

An agentic knowledge base. The agent owns the structure; you source material, direct analysis, and
review output. Depth lives in skills, loaded on demand — this file carries only what must hold
when no skill is running.

## Placement (PARA)

| Folder | Use |
|---|---|
| `00_Memory/` | Agent self-memory. Never distill into it, enrich from it, or link to it. |
| `01_Capture/` | Inbox. Flat, no subfolders. Origin-prefixed filenames. Never link to a capture from active content. |
| `02_Projects/` `03_Areas/` `04_Resources/` | Active content — the only folders search/enrichment/index consider. |
| `05_Archive/` | Frozen. Never create, enrich, or link here from new notes. |

Full schema: `contract/VAULT_SCHEMA.md`.

## Distilling captures — non-negotiable

1. **Two phases, one checkpoint.** Phase 1: analyze only — read the capture, search existing
   notes, propose placement and enrichments, then **stop** for review. Phase 2 (after
   confirmation): write the note, execute the enrichments, remove the capture. Skip the checkpoint
   only on an explicit `--auto`/non-interactive instruction.
2. **Check for prior distillation before writing.** Overlapping capture sources collide more often
   than expected. `[earned: X-bookmark/Readwise double-distill collision, 2026-07-26]`
3. **Enrichment levels**, applied only to related notes scoring above the vault's configured
   search-score gate (default 0.70 — recalibrate per embedding model): Level 1 backlink (default),
   Level 2 merge inline (needs a citable section), Level 3 flag contradiction (never a silent
   overwrite).
4. **Every distilled note carries its source** and gets `status: distilled`.

## Frontmatter

Unknown keys are allowed — the field table in `contract/VAULT_SCHEMA.md` is a floor, not a
ceiling. Don't reject or "fix" a note for carrying a field you don't recognize.
