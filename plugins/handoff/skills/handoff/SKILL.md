---
name: handoff
description: Save a portable handoff of current work to _handoff/ so another session, machine, or tool (Codex, Gemini) can continue without re-deriving context.
allowed-tools: Bash, Read, Write
---

# Handoff

Portable, tool-agnostic session continuity. A handoff is plain markdown written to
`_handoff/` **inside the current repo** (travels with the code to any machine or tool),
with a one-line pointer appended to the vault's discovery index — best-effort, silently
skipped when no vault is resolvable (see `../../README.md`).

The deterministic mechanics live in `../../scripts/handoff.py`. Your job is the
**narrative** — the part only conversation context can produce. Write **forward**: for
what the *next* window needs to act, not a log of finished work.

## Quick start

> Save a handoff of what we're doing so I can continue later

1. **Pick a stream tag** — short kebab-case name for this line of work (e.g. `auth-fix`,
   `html-export`). Reuse the same tag across sessions on the same effort so they chain
   (seq 1 → 2 → 3). If the user passed one via `$ARGUMENTS`, use it.
2. **Write the narrative** to `_handoff/.draft.md` using the section template in
   [references/template.md](references/template.md). Fill every section from the
   conversation. The two highest-value sections are **Tried & Ruled Out** (so the next
   session never re-explores dead ends) and **Next Step** (the exact action to take,
   with file:line pointers). Keep it tight — decisions and direction, not narration.
3. **Assemble & write** by running the script (it adds frontmatter, git state, the chain
   link, and the vault index line):
   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/handoff.py" save \
     --stream <tag> --title "<one-line title>" \
     --body-file _handoff/.draft.md
   ```
4. **Report** the saved path and vault-index line back to the user, and surface the
   script's own `Suggested:` line — it already reads the profile's `default_visibility`
   (`commit` for team/cross-machine continuity, `gitignore` for private single-machine
   use) so you don't have to guess.

Full procedure detail — listing existing handoffs, cross-tool (Codex/Gemini) handoff,
the auto-snapshot safety net, chain integrity, and the storage model — lives in
[references/workflow.md](references/workflow.md).
