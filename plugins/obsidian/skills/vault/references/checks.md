# Vault Lint — Check Details

## `vault_lint.py` (structure, report-only)

### Orphan detection

Notes with zero inbound wikilinks from other notes in active folders (02-04).

- Scans `.md` files in `02_Projects/`, `03_Areas/`, `04_Resources/`.
- Parses wikilinks (`[[Target]]` and `[[Target|Display]]`) from each file.
- Builds an inbound-link map by basename (matching how Obsidian itself resolves
  wikilinks); notes with zero non-self inbound links are orphans.
- Notes in `01_Capture/`, `05_Archive/` are never scanned or reported. A root-level or
  `Config/`-level note (e.g. a persona note) can legitimately have zero inbound links
  from active content without being a "problem" — orphan detection is about active
  content's own internal connectivity, not vault-wide reachability.

**Output per orphan:** note name, file path, creation date.

### Stale page detection

Notes not modified within the staleness threshold (default 180 days), via `git log -1`
where available, falling back to filesystem mtime.

**Priority:** a stale orphan (0 inbound links) is higher-priority than a stale note with
many inbound links — it's both disconnected and unmaintained.

### Missing concept detection

Wikilink targets that don't resolve to any note, referenced from 2+ different active
notes (the 2+ threshold avoids flagging a single typo as a "concept gap").

**Output per missing concept:** term, reference count, up to 5 example source notes.

### Index.md drift

Compares `Index.md` against the filesystem: entries with no matching file (`dangling`),
files with no entry (`missing`), and a count of entries still carrying the bootstrap
marker (⚙, meaning a non-Claude process wrote that summary and it hasn't been reviewed).

## `vault_normalize.py` checks (metadata, audit + fix)

### `links` — broken wikilink resolution

No LLM needed for the common case: a Levenshtein distance ≤1 against another note's
stem auto-fixes typos. Distance 2 is reported but not auto-applied. Beyond that, if an
`inference_model` is configured, the LLM is given the broken link's context plus the
top 30 candidates (by keyword overlap) and asked to pick a match or say `none` — it
never invents a target that isn't in the candidate list.

### `frontmatter` — rule-based audit, LLM-assisted fix

Checks: `status` present and one of `draft/review/distilled/active/archived`; `tags` is
a list; `description` present; distilled notes carry `source` and `processed_date`.
Missing `status`/`description` are LLM-generated (skipped cleanly if no model is
configured); missing `source`/`processed_date` on a distilled note get the
`(none — ...)`/today's-date treatment (see distill's rules.md) — never the string
`unknown`, which silently breaks any future date-scoped selection.

### `tags` — domain taxonomy classification

Classifies a note into 1-3 `domain/*` tags from a small, closed, JSON-schema-constrained
set (`DOMAIN_TAGS` in `checks/tags.py` — a starter list, edit it for your vault) and
migrates known legacy free-form tags onto it. The JSON-schema constraint matters: an
unconstrained LLM call emits markdown-fenced or malformed JSON at a high rate on small
local models, which silently produces nothing while looking like it ran.

### `source` — missing `*Source: ...*` line

For distilled notes only. If frontmatter has no `source:` and the body has no
`*Source:*` line, asks the LLM to extract one from the note content; writes
`(none — pre-existing vault note)` if the model says `none`.

### `summary` — Index.md entry quality

Only touches entries still carrying the ⚙ bootstrap marker (skips entries a real
process already wrote). Flags/regenerates entries under 5 or over 25 words.
