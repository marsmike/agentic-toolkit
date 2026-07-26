# Ingest Workflow

## 1. Read state

```bash
uv run --project "$CLAUDE_PLUGIN_ROOT/scripts" python3 "$CLAUDE_PLUGIN_ROOT/scripts/status.py" --json
```

`lastSyncedAt` in `00_Memory/readwise-state.md` is the watermark for step 2. If the state
note doesn't exist, this is a first sync — default to 30 days ago and rely on the backlog
sweep (step 3) to catch anything older.

## 2. Windowed fetch

```python
import readwise_api as rw
items = rw.reader_list_all(updated_after=last_synced_at)          # Reader v3 — primary
books = rw.classic_export_all(updated_after=last_synced_at, category="books")  # Classic v2
```

One unfiltered `reader_list_all` call already filters `location: feed`; do not loop over
categories individually (see references/api.md — a category-loop can silently miss `pdf`/
`epub`).

## 3. Backlog sweep — mandatory, every run

`updatedAfter` is a watermark, not an inventory: it answers "what changed since last run",
not "what is still unprocessed." Anything saved before the window that was never captured
stays invisible forever, because every later run's window also excludes it. This isn't
hypothetical — the source project this plugin was ported from found a two-month-old
unread clipping this way, missed by two prior runs in a row.

```python
sweep_new = rw.reader_list(location="new")
sweep_later = rw.reader_list(location="later")
```

For every document in the sweep not already in the windowed fetch, reconcile against the
vault before acting — grep `01_Capture/`, `04_Resources/`, `05_Archive/` for the doc's
`source_url` or tweet id:

| Reconciliation result | Action |
|---|---|
| Found already | Already processed — Reader just wasn't cleared. Report it; don't auto-delete (it's the user's read-state, not garbage). |
| Not found anywhere | A genuine miss — ingest and capture it in this run like anything new. |
| Ambiguous (no stable id) | Match on title instead, and say so in the report. |

Record both counts in the run summary even when the sweep finds nothing — that's still
evidence the watermark is holding.

## 4. Fetch full content before writing

List responses return `content: null`. Fetch the real body per item before writing a
capture — a capture written from the list response alone is hollow even though its
`doc_id` is present (a naive coverage check won't catch this):

```python
for item in items:
    full = rw.reader_get(item["id"])
    item["html_content"] = full.get("html_content", "")
```

Make this loop resumable and retrying (references/api.md) — it's the one that 429s.

## 5. Write captures

```python
from pathlib import Path
import build_captures as bc

for item in items:
    path, status = bc.write_capture(vault, item)
    print(status, path)   # "written" or "skipped-duplicate"

for book, highlights in classic_books:  # grouped by source
    path, status = bc.write_book_capture(vault, book, highlights)
```

`write_capture`/`write_book_capture` are dedup-safe by construction (they check
`readwise_doc_id` against existing captures first) — re-running this step over the same
clipping never produces a second file.

## 6. Coverage check — gates deletion

Before deleting or archiving anything in Readwise, confirm every ingested `doc_id`
resolved to a written or already-existing capture:

```python
expected = {item["id"] for item in items}
written_ids = set()
for p in vault_utils.iter_captures(vault):
    fm, _ = vault_utils.read_frontmatter(p)
    if "readwise_doc_id" in fm:
        written_ids.add(str(fm["readwise_doc_id"]))
missing = expected - written_ids
```

Any non-empty `missing` is a hard stop: print exactly what's missing, delete nothing, and
tell the user. A partial run is recoverable; a partial run followed by a delete is not.
Also write a DLQ note for the gap via `vault_utils.write_dlq_note()` (see README's
dead-letter-queue convention) — the missing `doc_id`s and the sync window are exactly the
"why it's here" a future run needs to reconcile against, not just a line in this run's
chat output.

## 7. Update state

Write/update `00_Memory/readwise-state.md`'s frontmatter: `lastSyncedAt` (now),
`lastProcessedAt` (only after enrichment + cleanup, in the `process` flow). This note is
`00_Memory/` — operational state, never distilled into, never enriched from
(`contract/VAULT_SCHEMA.md`).

## 8. Cleanup (only if the user asked for it)

Delete from **both** APIs — a Reader v3 delete does not remove a Classic v2 mirror.
Ask "Delete N items from Readwise? [archive/delete/keep]" unless the original request
already authorized it.

## Status mode

Run `scripts/status.py --json` for last sync, unprocessed count, and DLQ count — see the
`status` skill for the full presentation.

## Daily mode

Digesting today's captures is a separate, smaller capability — see the `daily` skill.
