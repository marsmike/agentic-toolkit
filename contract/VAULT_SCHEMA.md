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

Root-level notes (directly in the vault root) join active content only when their own
frontmatter declares `status: active` — e.g. a persona/profile note; `Index.md` and `AGENTS.md`
never qualify (no frontmatter). Notes under `Config/` are configuration, not content: links into
them are neither dangling nor violations, just unmodeled. [earned: gaiafield R2 node-scope
conflict — the bridge persona note was unreachable under a literal reading, 2026-07-26]
**Removal condition:** fold into the folder table above if root-level notes are ever migrated
into a PARA folder.

## Generated navigation

Rebuilt by the pipeline's `end` step from the notes themselves, never edited by hand, and not
active content: no search, enrichment or lint counts them, and a link from them is navigation,
not a note's inbound link.

| Path | Built by | What it is |
|---|---|---|
| `Index.md` | `index_build.py` | One line per active note, from its `description` |
| `Now.md` | `now_build.py` | The homepage, short enough to read at a glance: a status line (last run, stuck, inbox, the Signal Radar's early warnings), health (`watchdog.health()`), the last run's receipt with the reason for every drop, new topics (Concept notes first distilled this week, and strong outside things not in the vault yet), then the live `Recently changed` and `Recently distilled` views, then this week's new and enriched notes, radar and per-day chart folded away. Every count comes from frontmatter or the ledger, never from git history |
| `00_Daily/<YYYY-MM-DD>.md` | `daily_build.py` | One note per UTC day for Obsidian's Daily notes and Calendar: what was distilled, changed, found by the radar and run that day. The generator owns only the block between `%% daily:start %%` and `%% daily:end %%`; text outside it is the owner's and is never touched |
| `Maps/<domain>.md`, `.canvas` | `map_build.py` | One map per `domain/*` tag on three or more notes (or configured in `maps.md`); `Maps/Overview` lists them |
| `Boards/Pipeline.md` | `now_build.py` | The same state as Now.md as a Kanban board; drags are overwritten |
| `Imports.md` | `imports_log.py` | What every run imported and what became of each item (note, dropped with its reason, duplicate, waiting, missing), one `## day` section per day that says how many runs it had, runs newest first; data in `00_Memory/imports.jsonl` |
| `00_Memory/imports.jsonl` | `pipeline_run.py end`, `retire_capture.py` | The one ledger every count comes from, never `git log` (a cloud checkout can be shallow). A **run row** (`kind: run`, `at`, `distilled`, `dropped`, `failed`, `shallow`, `summary`, `items`) per run, quiet ones included; a **retired row** per capture (`kind: new\|enriched\|dropped\|duplicate`, `notes`, `reason`, `what`, and `linked` for notes that only got a backlink). Twelve-week window: `end` prunes rows older than 84 days, git keeps them. Rows written before this shape are not backfilled and render from their manifest line |
| `00_Memory/last-run-report.html` | `report_build.py` | The last run's ingestion report as an Artifact page (every import with its links, what it became, the notes written); the routine publishes it to `report_artifact_url` |
| `00_Memory/radar/Signal-Radar.html`, `.md`, `Signal-Radar-scope.svg`, `Signal-Radar-momentum.svg`, `signal.json` | radar `radar.py signal` | What is taking off: named things across feeds, sensors, the vault and its graph, each with a signal strength; the routine publishes the page to `signal_artifact_url`; the note embeds the two SVGs, so Obsidian shows the same radar the browser page does |
| `Dashboard.html` | `dashboard_build.py` | Twelve weeks of distilling for a browser: per day, by source, domain and kind, with the notes and the runs |
| `Atlas.html` | `atlas_build.py` | The whole vault and the way in, for a browser: every imported item from its source through what it became to the domains it fed, the radar's funnel, the routines' runs; every active note by domain with its links, topics and growth. The routine publishes it to `atlas_artifact_url` |
| `Log.md` | `log_vault.py` | One line per run |

A map's title, intro and sections come from `Config/toolkit/maps.md`; everything else comes from
the notes' tags, `kind`, `description` and links. In a vault under git, a note git ignores is in
no generated view and no lint report: a clone never has it, and a build on each side must agree. [earned: 2026-09-23, about 80 hand-made MOCs
had gone stale] **Removal condition:** none while the vault forbids hand-maintained MOCs.

## Frontmatter field table

Field names and meanings are stable — generated views, lint tooling, and plugin logic depend on
them holding still. Check whether an existing field fits before adding a new one.

| Field | Meaning | Required for |
|---|---|---|
| `description` | One-sentence purpose | Resources, Areas |
| `source` | Provenance — URL or citation | Every distilled note |
| `status` | Lifecycle stage, see below | Every distilled note |
| `processed_date` | ISO date the note was distilled (back-compat; equals `distilled_at`'s date) | Every distilled note |
| `ingested_at` | ISO 8601 UTC timestamp, with time and `Z` (e.g. `2026-09-28T18:59:34Z`) — when the item entered the vault as a capture | Required going forward: every new capture and every note distilled from one, stamped in code. Backfilled onto an existing note only where `backfill_timestamps.py` found real evidence (a capture file or git history); left absent, never guessed, where none existed — on a real vault this reaches most but not all distilled notes (60% measured on ~/Documents/TheVoid, 2026-09-28). Absent is a legitimate value here, not a gap to chase. |
| `ingested_at_estimated` | `true` when `ingested_at` was inferred (e.g. by `backfill_timestamps.py` from git history) rather than recorded at capture time — mirrors `processed_date_estimated` | Opt-in, on an estimated `ingested_at` |
| `distilled_at` | ISO 8601 UTC timestamp, with time and `Z` — when the note was distilled from its capture(s) | Required going forward: every note distilled in code carries it, and `backfill_timestamps.py` back-dates it (with `distilled_at_estimated: true`) onto every pre-existing distilled note from `processed_date`, which is never itself missing. In practice this one reaches 100% of distilled notes once backfilled. |
| `distilled_at_estimated` | `true` when `distilled_at` was inferred the same way — the same convention, one flag per field | Opt-in, on an estimated `distilled_at` |
| `updated_at` | ISO 8601 UTC timestamp, with time and `Z` — when the pipeline last changed the note: set at distillation and again on every L2 enrichment and every L1 backlink (`retire_capture.py --linked`) | Required going forward on every note a retired capture produced or changed, stamped in code by `retire_capture.py` (never by the LLM); `pipeline_run.py`'s `end` stamps any changed note it missed. Never backfilled: an older note has none, and the `Recently changed` view falls back to `distilled_at`, then `processed_date` |
| `kind` | Note kind (`concept`, `guide`, `research-finding`, `profile`, plus project- and domain-specific values) | Resources |
| `topics` | Structured topical taxonomy | Resources |
| `methodology` | Methodology family, when applicable | Opt-in — no generator or skill sets it today (unlike `kind`/`topics`, which the distill skill always fills); add it by hand where it earns its keep. |
| `tags` | Freeform and/or namespaced — see below | All |
| `type` | Note type (`meeting-note`, `project-doc`, …), when applicable | — |
| `author`, `published` | Original author / publish date | External material |
| `created` | Note creation date | Most notes |
| `enrichment_targets` | Notes/profiles to notify when this note is enriched | Opt-in |

**Which date counts.** A note counts as distilled on a day only when it was distilled (`distilled_at` present or `status: distilled`) and the date is real: `distilled_at`, else `processed_date`, and never a value flagged `*_estimated` (a backfill stamped 1,096 notes) nor a `status: review` note that merely carries a `processed_date`. `vault_utils.distilled_when` is that rule; `now_build`, `daily_build`, `dashboard_build`, `atlas_build` and the report all use it, so a week's number is the same on every surface. Radar's rising-tag test uses the same idea plus a minimum baseline (at least 2 of the 4 earlier weeks and 20 notes), and says 'no baseline yet' until it has one.

Going forward, `ingested_at`, `distilled_at` and `updated_at` are set deterministically in code — a writer
script or a retirement step stamps `datetime.now(UTC)` at the moment it acts, never left to an
LLM to guess (`processed_date` stays as the date-only back-compat field, and
`processed_date_estimated` stays as its own estimated flag — unchanged by this pair). That does
not make either field present on every note that predates the pair: `backfill_timestamps.py`
back-fills what evidence supports (real git history for `distilled_at`, a still-present capture
or its git history for `ingested_at`) and leaves the rest absent rather than guessing — so
`distilled_at` reaches every distilled note in practice (`processed_date` always has a date to
back-date from) while `ingested_at` does not (not every distilled note's source capture survives
or has usable git history). `checks/frontmatter.py` and `core/tests/test_contract.py` both treat
this honestly: neither ever asserts `ingested_at`/`distilled_at` presence as a hard requirement,
only their shape when present. [earned: 2026-09-28 — the owner asked for the ingest and distill
date and time on every report and note; measured against the real vault the same day, `ingested_at`
turned out to reach 60% of distilled notes and `distilled_at` 100%]

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
