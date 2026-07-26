# Handoff workflow — full detail

## List existing handoffs

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/handoff.py" list
```

## Cross-tool (Codex / Gemini)

The handoff is portable markdown — no Claude-specific format. To continue elsewhere,
point the other CLI at `_handoff/HANDOFF.md` (the latest pointer). Consider symlinking
`AGENTS.md → _handoff/HANDOFF.md` in a repo where you routinely switch tools, so Codex
and Gemini pick it up automatically on startup.

## Auto-snapshot (safety net)

A `PreCompact` hook writes `_handoff/.autosnapshot.md` (git state only) right before
context compaction, so nothing volatile is lost if you forget to save. It is **not** a
substitute for a real handoff — it has no decisions or next step. The `handoff-resume`
skill surfaces it only when it is newer than the latest real handoff. Disable it via the
profile's `autosnapshot: false` (see `../../../profile.example.md`) or the
`TOOLKIT_HANDOFF_AUTOSNAPSHOT=false` env var.

## Chain integrity

Handoffs on the same stream link via `prev:` frontmatter and a rendered `follows` line.
Hand off at natural boundaries (feature done, bug resolved) — quality degrades across
many mid-task handoffs stacked on one stream.

## Storage model

- **Full handoff, in-repo** — `_handoff/HANDOFF-<stream>-NN.md`; `_handoff/HANDOFF.md`
  always points at the latest.
- **Cross-project index, in the vault** — one line appended to `$VAULT/<index_path>`
  (default `00_Memory/handoffs/index.md`), only when a vault is resolvable
  (`contract/PROFILE.md`: `TOOLKIT_VAULT` env var, else the bundled `./vault`). No vault
  resolvable → the handoff still saves in full; the index append is silently skipped,
  never an error.
- **Dead-letter queue** — a script failure that would silently lose a handoff (an
  unwritable `_handoff/`, or an index-append failure against a *resolvable* vault)
  writes a note to `$VAULT/00_Memory/dlq/` instead of failing silently. See
  `../../../README.md`'s Dead-letter queue section for the exact criteria.
