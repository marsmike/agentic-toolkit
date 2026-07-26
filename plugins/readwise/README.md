# readwise plugin

Pulls Readwise highlights (Reader v3 — tweets, articles, videos, newsletters, PDFs, EPUBs
— plus Classic v2 for Kindle/Apple Books) into `01_Capture/` as origin-prefixed,
schema-conformant capture notes, with optional GitHub/YouTube metadata enrichment, a
daily digest, and pipeline status. Filesystem-first throughout
(`contract/KNOWLEDGE_API.md`) — no cross-plugin imports, no vendored environment.

## What it does

| Skill | Purpose |
|---|---|
| `ingest` | Pull new clippings from the Readwise API (windowed sync + mandatory backlog sweep), write each as a dedup-safe capture note in `01_Capture/`, gate deletion on a coverage check |
| `enrich` | Optional post-capture enrichment: GitHub repo metadata via `gh`, YouTube metadata + transcript via `yt-dlp` — both independent, both degrade cleanly when their CLI is absent |
| `daily` | Digest today's new captures from `01_Capture/` to stdout, grouped by category |
| `status` | Pipeline health: last sync, last processed, captures awaiting distillation, DLQ count |

Plus `scripts/` (see below) that back all four skills, and a `SessionStart` hook that
reports sync status — silently, when `READWISE_TOKEN` isn't set.

Use `obsidian:distill` for long-term vault integration once captures land here.

## Vault resolution

`TOOLKIT_VAULT` environment variable, else `./vault` relative to the repo root
(`contract/PROFILE.md`). Every script here resolves the vault the same way — see
`scripts/vault_utils.py`'s `resolve_vault()`. Tests and evals always target `./vault`
regardless of `TOOLKIT_VAULT`; a real vault reached via that env var is never touched by
this plugin's own eval suite.

## Profile

Reads `$VAULT/Config/toolkit/readwise.md` if present, per `contract/PROFILE.md`'s "fill
from Obsidian" convention. See `profile.example.md` for the exact frontmatter shape
(`enrichers`, `backlog_sweep`) and what each field controls. Every field also has a
`TOOLKIT_READWISE_<FIELD>` environment variable that overrides the note.

## Env vars

- **`READWISE_TOKEN`** — required for any live API call. Get one at
  https://readwise.io/access_token. Never written to the vault or the repo — see
  `contract/PROFILE.md`'s Secrets section.
- **`TOOLKIT_VAULT`** — vault location override, per `contract/PROFILE.md`.
- **`TOOLKIT_READWISE_<FIELD>`** — profile field overrides, see `profile.example.md`.

## Dependencies

`scripts/pyproject.toml` declares one dependency: PyYAML, for frontmatter I/O. The
Readwise API client (`readwise_api.py`) is stdlib-only (`urllib`) — no `requests`, no
`curl` shelling. GitHub and YouTube enrichment are optional external CLIs (`gh`,
`yt-dlp`) that `github_meta.py`/`youtube_meta.py` detect and degrade around; neither is a
hard dependency of `ingest`. Run any script via `uv run --project scripts python3
scripts/<name>.py ...` from the plugin root.

## Dead-letter queue

`00_Memory/dlq/` via `scripts/vault_utils.write_dlq_note()` — same convention the obsidian
plugin's scripts use (`description`/`status`/`created`/`confidence` frontmatter, a "What
happened / Why it's here / Resolution" body). `toolkit doctor` (in `core/`) surfaces the
count; `status.py` also reports it directly for this plugin.

## Dedup-before-distill

`contract/templates/VAULT_CLAUDE.md`'s distill rules cite a real collision: "Check for
prior distillation before writing. Overlapping capture sources collide more often than
expected `[earned: X-bookmark/Readwise double-distill collision, 2026-07-26]`." That rule
is primarily `obsidian:distill`'s job at the cross-origin level (a capture reaching the
vault via two different plugins). This plugin's share of it is idempotency within its own
pipeline: `build_captures.write_capture()`/`write_book_capture()` check `01_Capture/` for
an existing note carrying the same `readwise_doc_id` before writing, so re-running
`ingest` over a clipping already captured is a no-op, not a second near-duplicate file
for distill to collide on. See `evals/eval_dedup_guard.py`.

## What changed vs. v1 (`~/Developer/agentic-toolkit-legacy/readwise`)

### Ported and rewritten

- `readwise-api.sh` → `readwise_api.py` — Python port, stdlib `urllib` instead of
  `curl`/inline `python3 -c`; same endpoint coverage (Reader v3 list/get/archive/delete,
  Classic v2 export/highlight-delete), same pagination and `location: feed` filtering.
- `build_captures.py` — singleton-only (the cluster/concept-grouping mode is dropped, see
  below); rewritten to be dedup-safe by construction and to write
  `contract/VAULT_SCHEMA.md`-conformant frontmatter (`source`, `origin`,
  `readwise_doc_id`, `category`, `tags`) instead of the ad-hoc `status: capture` value,
  which isn't part of the vault's lifecycle enum and was never in scope for the check
  that enum backs anyway.
- `github-meta.sh` → `github_meta.py`, `fetch_video_transcript.sh` → `youtube_meta.py` —
  Python ports of the `gh api`/`yt-dlp` wrappers, same extraction logic (repo-slug
  `.git`-suffix trap, transcript consecutive-dedupe-only rule) preserved verbatim as
  comments citing the real failures that earned them.
- `readwise-daily.sh` → `daily_digest.py` — same digest logic, same "missing directory is
  an error, not an empty day" guard; the `Log.md`-write step is dropped (see below).
- `hooks/session-start.sh` — rewritten to degrade **silently** with no `READWISE_TOKEN`
  set, rather than printing a "plugin disabled" banner on every session for every user
  (see Dropped, and `evals/eval_hook_silent_noop.py`).
- `vault_utils.py` — new for this plugin, a small self-contained subset of the obsidian
  plugin's module of the same name (vault/profile resolution, tolerant frontmatter I/O,
  the DLQ writer) — copied rather than imported, per `contract/KNOWLEDGE_API.md`'s
  no-cross-plugin-imports rule.
- Vault path: `OBSIDIAN_VAULT_PATH` → `TOOLKIT_VAULT`/`./vault` resolution throughout.
- Config: `~/.claude/readwise.local.md` (machine-local, outside the vault) →
  `$VAULT/Config/toolkit/readwise.md` (the profile convention, `contract/PROFILE.md`).

### New in v2

- `evals/` — the R0 capability evals (see below).
- `profile.example.md`, `scripts/pyproject.toml`.
- 4 skills replacing v1's 9 (`ingest`/`classify`/`enrich`/`enrich-github`/`enrich-youtube`/
  `enrich-book`/`enrich-article`/`surface`/`status`) — see the consolidation note below.

### Dropped, with reasons

| Component | Reason |
|---|---|
| `build_captures.py`'s concept-cluster mode (`clusters.json`, cross-item grouping, GitHub-repo-table-per-cluster rendering) | v1's own skill already named singleton (one capture per clipping) as "the default... on every run since 2026-06-29" and the cluster path as something to reach for only on explicit request. Real, working code, but not what this plugin delivers by default — the singleton path covers the load-bearing behavior; cluster-mode's clustering heuristics (URL/keyword/semantic-similarity grouping) are a curation judgment call, not a mechanical port, and out of scope for a lean R0 port. |
| `skills/classify` | URL/content-type detection is intrinsic to writing a capture (`build_captures.write_capture()` reads `category` straight off the Reader API item) rather than a distinct workflow step — folded into `ingest`, not a separate skill. |
| `skills/enrich-book` (vault book-note merging into `Readwise/Books/`) | Tied to the folder convention the official Readwise-for-Obsidian community plugin creates — not a PARA folder under `contract/VAULT_SCHEMA.md`, and a second plugin's data model this one would have to reach into. Classic v2 book highlights are still captured (via `build_captures.write_book_capture()`), just as an ordinary `01_Capture/` note like everything else, not merged into a different plugin's folder. |
| `skills/enrich-article` (Kagi/Tavily summarization) | Both are separate plugins (`research:kagi-search`, `research:tavily-extract`) in the source repo — calling them directly is exactly the cross-plugin import `contract/KNOWLEDGE_API.md` prohibits. Composition across plugins happens through vault notes, not a direct call from one plugin's script into another's. |
| Tweet-thread reconstruction via `research:x-search` (`references/tweet-enrichment.md`'s x-search fetch, raw-thread stash to `01_Capture/.threads/`, X-Article recovery) | Same cross-plugin-import problem — `x-search` is a skill inside the `research` plugin. The Reader API's own `withHtmlContent=true` fetch (kept, in `readwise_api.reader_get()`) already recovers full tweet bodies when Readwise has them; the thread-reconstruction layer on top required a sibling plugin and is dropped along with it. |
| Wisereads-newsletter-specific handling (volume-slug permalink resolution, per-item WebFetch/Kagi/x-search-thread fetch orchestration in `enrichment.md`) | Deep, fragile, vendor-specific knowledge (issue-numbering drift, a particular newsletter's URL scheme) rather than general "newsletter capture" behavior. Newsletters are still captured as ordinary `email`-category items via the same `write_capture()` path everything else uses. |
| `hooks/session-start.sh`'s original "plugin disabled" banner | Printed on every session for every user, including people who have never configured Readwise — an error banner for users who never opted in, which the task's brief called out directly. Rewritten (see Ported) to exit 0 with zero output in that state; kept only the informational line for users who *have* set `READWISE_TOKEN`. |
| `Log.md` integration (`log_vault.py` calls in `surface.md`/`readwise-daily.sh`) | A direct call into the obsidian plugin's own script — cross-plugin import. Dropped; if a durable log entry is wanted, the invoking agent writes it itself, composed through the vault rather than through a sibling plugin's internals. |
| `clean_html.sh` (defuddle-cli wrapper) | An external Bun/npm-installed binary (`defuddle-cli`) for HTML cleanup; `build_captures.py` already ships a small last-resort HTML→Markdown fallback (`_html_to_md_basic()`, ported verbatim from v1) that needs nothing beyond the stdlib. Bringing in a whole third-party CLI dependency for a nicer version of the same fallback didn't clear the curation bar for a lean R0 port. |
| `settings/readwise.local.md.template` | Superseded by `profile.example.md` and the vault-profile convention (`Config/toolkit/readwise.md`) — the old machine-local `~/.claude/` config file is exactly what `contract/PROFILE.md` moves out of the repo/machine and into the vault. |

## Evals

`evals/run.py` runs four R0 capability evals against `./vault`, emitting JSON
`{eval, pass, detail}` per check — no network calls, fixture-driven:

| Eval | Asserts |
|---|---|
| `capture_note_formatting` | Given a fixture Reader-item payload (`evals/fixtures/reader_item.json`), `build_captures.write_capture()` produces an origin-prefixed (`Readwise-...`) note flat under `01_Capture/` with conformant frontmatter (`source`/`origin`/`readwise_doc_id`/`category`/`tags`) and a `## Full Text` section |
| `dedup_guard` | Calling `write_capture()` twice with the same fixture item writes exactly one capture file, not two — the second call returns `skipped-duplicate` |
| `book_capture_dedup` | Given a fixture Classic v2 book + highlights (`evals/fixtures/reader_book.json`), `build_captures.write_book_capture()` produces a conformant `category: book` note with the highlights rendered, and a second call over the same book dedups via the title+author slug key rather than writing a second file |
| `hook_silent_noop` | `hooks/session-start.sh`, run with `READWISE_TOKEN` unset and a scratch `$HOME`, produces zero stdout/stderr and exits 0 |

Every eval that writes runs against a throwaway copy (`evals/_sandbox.py`), so `./vault`
is never touched. If `./vault` doesn't exist yet, `run.py` exits `2` with a `corpus not
present` detail on every eval rather than crashing.

```bash
uv run --project scripts python3 evals/run.py --json
```
