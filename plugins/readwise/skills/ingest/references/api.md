# Readwise API Reference

All calls go through `scripts/readwise_api.py` (a stdlib-only Python client — no `curl`
shelling, no third-party HTTP library). Token: `READWISE_TOKEN` environment variable.

```python
import readwise_api as rw
rw.auth()                                                    # -> bool
rw.reader_list_all(category="tweet", updated_after="2026-06-01")   # paginates, filters feed noise
rw.reader_get(doc_id)                                        # full HTML content
rw.reader_archive(doc_id)
rw.reader_delete(doc_id)
rw.classic_export_all(category="books", updated_after="...")
rw.classic_highlight_delete(highlight_id)
```

## Reader API (v3) — primary

Most clipped content (tweets, articles, videos, newsletters, PDFs, EPUBs) lands here.

| Function | Endpoint | Notes |
|---|---|---|
| `reader_list` / `reader_list_all` | `GET /list/` | Paginated; `reader_list_all` follows `nextPageCursor` and drops `location: feed` (RSS noise, never a clipping) unless you explicitly asked for that location |
| `reader_get` | `GET /list/?id=&withHtmlContent=true` | **Required before writing a capture** — list responses return `content: null`; the real body and every embedded URL only come back from this per-id fetch |
| `reader_archive` | `PATCH /update/{doc_id}/` | `{"location": "archive"}` |
| `reader_delete` | `DELETE /delete/{doc_id}/` | 204 on success |

`location` values: `new`/`later` are real saves (ingest these); `archive` is already
filed; `feed` is an RSS subscription item the user never explicitly saved — never a
clipping, always filtered.

`category` values: `tweet`, `article`, `video`, `email`, `pdf`, `epub`. All six are
ordinary saves — a loop that only covers the "obvious" four silently drops PDFs and
EPUBs. Prefer one unfiltered list call plus the `location != feed` filter over a
per-category loop: fewer requests, and a new category can't be missed by construction.

## Classic API (v2) — supplementary (Kindle/Apple Books)

| Function | Endpoint | Notes |
|---|---|---|
| `classic_export_all` | `GET /export/` | Paginated — **a single page is not the full library.** On a real 2026-07-24 run, one page returned 18 sources/656 highlights where the true library was 32 sources/1,056 — 44% invisible. Always paginate. |
| `classic_highlight_delete` | `DELETE /highlights/{id}/` | One request per highlight — there is no bulk or book-level delete; `DELETE /books/{id}/` returns 405 |

Classic v2 source objects have no stable numeric id (only `asin`/`readable_title`/`author`)
— `build_captures.write_book_capture()` dedups on a slug of author+title instead.

**Duplicate mirrors:** Twitter saves often appear twice — once as a Reader v3 `tweet`
document, once as a Classic v2 highlight under a synthetic source like "Tweets From
<Name>". Deduplicate by tweet id/highlight text before counting, and delete both copies
at cleanup — deleting the Reader doc does not remove the Classic mirror.

## Rate limits

- Reader v3 list: 20 req/min. `reader_list_all` paginates with a 3s delay by default.
- The per-id `withHtmlContent=true` fetch counts against the same budget and is the one
  that actually 429s in practice — make any fetch loop resumable (skip already-fetched
  `doc_id`s) and retrying (sleep and retry on 429) rather than fire-and-forget. A dropped
  body produces a hollow capture that a naive coverage check (doc_id present) won't catch.
- Classic v2 export: 20 req/min, handled by `classic_export_all`'s 3s delay.
- Highlight delete is far more permissive than export (~150/min observed, no 429s) — but
  still write the loop defensively and resumably.
