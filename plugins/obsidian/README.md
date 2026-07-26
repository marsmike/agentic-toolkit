# obsidian plugin

The reference implementation of the vault contract (`contract/`): filesystem-first vault
CRUD, a keyword-plus-optional-semantic search, the distill pipeline (captures →
integrated knowledge), vault-lint maintenance, and a retrieval-verification maintenance
loop for description quality.

## What it does

| Skill | Purpose |
|---|---|
| `vault-ops` | Read/create/edit/search notes directly on the filesystem; wikilinks, callouts, properties, `.canvas`/`.base` file formats; the Obsidian desktop CLI as an optional enhancement, never a requirement |
| `distill` | Process `01_Capture/` into linked, sourced knowledge notes — triage, single-file distill, or conversation-insight filing, all through one search-then-checkpoint-then-write workflow |
| `vault-lint` | Vault health (orphans, stale pages, broken links, Index.md drift) and metadata normalization (frontmatter, tags, source, summaries), audit-only unless `--fix` |
| `retrieval-verification` | Predict a note's content from title+description alone, score against the real body, flag weak descriptions for rewrite |

Plus `agents/knowledge-distillation-agent.md` for delegated/batch distillation runs, and
`scripts/` (see below) that back all four skills.

## Vault resolution

`TOOLKIT_VAULT` environment variable, else `./vault` relative to the repo root
(`contract/PROFILE.md`). Every script here resolves the vault the same way — see
`scripts/vault_utils.py`'s `resolve_vault()`. Tests and evals always target `./vault`
regardless of `TOOLKIT_VAULT`; a real vault reached via that env var is never touched by
this plugin's own eval suite.

## Profile

This plugin reads `$VAULT/Config/toolkit/obsidian.md` if present, per
`contract/PROFILE.md`'s "fill from Obsidian" convention. See `profile.example.md` for
the exact frontmatter shape (`search_score_gate`, `default_capture_prefixes`,
`inference_backend`/`inference_base_url`/`inference_model`, `enrichment_targets`) and
what each field controls. Every field also has a `TOOLKIT_OBSIDIAN_<FIELD>` environment
variable that overrides the note. No profile note and no `inference_model` set is a
normal, fully-functional state — LLM-assisted checks skip cleanly and say why; only
`links`' auto-fix and every other rule-based check are unaffected.

## Dependencies

`scripts/pyproject.toml` declares everything: PyYAML for the base install, an optional
`[semantic]` extra (`sentence-transformers`, `numpy`) for `search.py`'s semantic boost.
No vendored virtualenv, no Obsidian app requirement, no pre-existing embeddings store.
Run any script via `uv run --project scripts python3 scripts/<name>.py ...` from the
plugin root.

## Dead-letter queue

Every script that can fail ambiguously — rather than proceeding on a guess — writes a
note to `00_Memory/dlq/` via `scripts/vault_utils.write_dlq_note()`: `vault_normalize.py`
on unparseable frontmatter it refuses to write through, `retrieval_verification.py` on
an incomplete scores map, and the `distill` skill/agent on unresolved search/placement/
source ambiguity. `toolkit doctor` (in `core/`) surfaces the count. See
`00_Memory/dlq/*.md` in the example vault for the worked convention this follows:
`description`/`status`/`created`/`confidence` frontmatter, and a "What happened / Why
it's here / Resolution" body.

## Search: what's here now vs. what replaces it

`scripts/search.py` is the R0 placeholder: a dependency-light BM25 ranking over note
title/filename/Index.md-summary/body (always available, needs nothing beyond PyYAML)
with an optional semantic cosine layer if `sentence-transformers`/`numpy` are installed,
backed by a small cache this script builds and owns — never Smart Connections'
`.smart-env/` format. When the optional layer isn't installed, it says so explicitly and
returns keyword-only results rather than erroring or silently doing nothing.

**farsight** (`docs/PLAN.md`), a Rust hybrid BM25+vector engine, replaces this file in
R1. Nothing here is meant to be the final retrieval architecture.

## What changed vs. v1 (`~/Developer/agentic-toolkit/obsidian`)

### Ported and rewritten

- `vault_utils.py` — vault resolution switched to `TOOLKIT_VAULT`/`./vault`; YAML
  library switched from `ruamel.yaml` to PyYAML for consistency with `core`'s
  frontmatter handling (loses ruamel's comment/quote-style preservation on write-back —
  a minor nuance, not a lost capability); LLM config now resolved from the vault
  profile instead of `~/.config/vault-normalize.yaml`; added `write_dlq_note()` and
  `append_capture_note()`.
- `vault_lint.py`, `vault_normalize.py`, `checks/*.py`, `log_vault.py` — light-to-medium
  rewrites for the new `vault_utils` API (`llm_chat(..., vault=...)` instead of a
  `config` dict), contract-aligned `status` enum (`draft/review/distilled/active/
  archived`, dropping v1's `capture` since captures are out of this check's scope
  entirely), a generic starter tag taxonomy in `checks/tags.py` replacing the personal
  interest-graph taxonomy, and a personal example string removed from
  `checks/frontmatter.py`'s description-prompt examples.
- `checks/links.py` — same fuzzy+LLM resolution mechanism, but its note-existence index
  now covers the whole vault (minus `00_Memory/01_Capture/05_Archive`) instead of only
  `02-04`, so root-level/`Config/`-level notes (personas, profile notes) don't false-
  positive as broken links.
- `distill` skill — workflow rewritten filesystem-first throughout (no Obsidian-CLI
  mode, no Smart Connections/embeddings-store dependency, no Twitter/Readwise-specific
  URL-provenance logic); `preflight.sh` trimmed to vault resolution + generic
  `extract_urls`/`canonicalize_urls`.
- `obsidian-cli` skill → renamed **`vault-ops`** — reframed filesystem-first per
  `contract/KNOWLEDGE_API.md`; the Obsidian desktop CLI is now explicitly an optional
  enhancement, documented with its one hard trap (silent exit 0 when disabled), not the
  primary path. `markdown-syntax.md`, `json-canvas.md`, `obsidian-bases.md` ported
  unchanged (already generic Obsidian format references).
- `vault-lint` skill — `checks.md`/`taxonomy.md`/`backlink-workflows.md` rewritten to
  reference `search.py` instead of `semantic-search.sh`/Smart Connections, and the
  genericized taxonomy.
- `agents/knowledge-distillation-agent.md` — fully rewritten persona-neutral: no
  personal context, cites `contract/ROUTING.md`'s spawn-depth and escalation
  rules instead of a fixed personal tag/template list.

### New in v2

- `scripts/search.py` — see above.
- `scripts/retrieval_verification.py` + `skills/retrieval-verification/` — the
  description-quality loop, new per this release's brief.
- `evals/` — the R0 capability evals (see below), built against the shared example
  vault's planted fixtures rather than a private per-skill fixture copy.
- `profile.example.md`, `scripts/pyproject.toml`.

### Dropped, with reasons

| Component | Reason |
|---|---|
| `scripts/pipeline/*.py` (the "Silfen Path" note-maturity system: `access_log`, `archive`, `backfill`, `cli`, `debug_log`, `evening`, `judge_p3`, `promotion`, `retrieve`, `schema`, `tui`) and `scripts/bin/silfen` | A distinct, opinionated note-lifecycle methodology (seedling/developing/evergreen, P3/C3 judgments), not vault-interaction behavior. Real, working code — but it can't be named as "what the obsidian plugin delivers" (Osmani scope test); candidate for its own plugin if it earns readmission later. |
| `scripts/hybrid_search.py`, `vault_index.py`, `corpus.py`, `generate_embeddings.py`, `eval_retrieval.py`, `smart_search.py` | The whole Smart-Connections-coupled vector/graph/BM25-fusion search engine. Hard-required a pre-existing `.smart-env/` embeddings store that cannot exist on a fresh clone; `smart_search.py` was already superseded by `hybrid_search.py` in v1 itself. Replaced by `search.py` (BM25 always available, optional self-built semantic cache); farsight is the intended long-term replacement. |
| `scripts/index_build.py` | Bulk `Index.md` rebuilder; overlapping job with `checks/summary.py` + `vault_normalize.py`'s per-note summary maintenance, which stayed. Two components solving the same problem is exactly what the curation bar asks to collapse. |
| `scripts/llm_benchmark.py` | Model-comparison benchmarking harness, not vault-interaction behavior; also carried a personal tag reference in its taxonomy. |
| `scripts/ob-sync.sh`, `semantic-search.sh`, `semantic-search.ps1` | Obsidian-headless-server sync management and launchers for the dropped search engine. Vault sync (Obsidian Sync app, git, NAS) is the user's own concern, not this plugin's; `search.py` is invoked directly via `uv run`, no launcher script needed. |
| `references/agent-prompt.md` | A separate launch-prompt template for the agent that could drift from the agent definition itself; folded directly into `agents/knowledge-distillation-agent.md`. |
| `skills/distill/references/traps.md` | A failure catalog for tools this v2 plugin doesn't ship (Smart Connections, the Obsidian desktop CLI as a required path, Twitter/Readwise-specific URL handling). The two lessons that generalize — never trust a silent exit 0, never write `"unknown"` as a placeholder — are folded directly into `workflow.md`/`rules.md`. |
| `skills/distill/references/triage-workflow.md`, `insight-workflow.md` | Folded into `workflow.md` as short Triage/Insight sections; each was small enough that a separate file cost more in the skill's reference-loading budget than it saved. |
| `skills/obsidian-cli/references/daily-note-patterns.md`, `headless-sync.md`, `headless-sync-setup.md` | Machine-specific headless-server setup instructions, in tension with the filesystem-first stance (see `ob-sync.sh` above). |
| `skills/distill/evals/` (`evals.json`, `mechanical_checks.py`, `setup_sandbox.py`, `fixtures/demo-vault/`) | A different eval-harness contract (pressure-test prompts + a private fixture vault) than v2's Graduation Pattern JSON shape (`{eval, pass, detail}`) targeting the shared example vault. The underlying idea — mechanical checks against a sandboxed copy — carried over into `evals/_sandbox.py`. |
| `scripts/tests/`, `scripts/checks/tests/`, `scripts/tests/pipeline/` (the pytest suite, ~3,500 lines) | Not ported. The R0 capability evals cover the contract-facing guarantees of what actually shipped; porting a full unit-test suite for code this size was disproportionate to R0 scope. Open item for a follow-up PR if unit-level coverage is wanted alongside the evals. |

## Evals

`evals/run.py` runs four R0 capability evals against `./vault`, emitting JSON
`{eval, pass, detail}` per check:

| Eval | Asserts |
|---|---|
| `vault_lint_broken_link` | `checks/links.py`'s audit flags the vault's planted broken wikilink (`Test-Corpus-Map.md`'s edge-case table) |
| `distill_placement` | `search.propose_placement()` routes a synthetic capture drawn from the home-lab-migration project's own vocabulary to that project's folder, not the generic default |
| `retrieval_verification_report` | The sample→score→report cycle produces a correct JSON report and a `01_Capture/` summary note, using the vault's own BM25-dilution specimen pair as fixture |
| `dlq_on_missing_scores` | An incomplete scores map produces a DLQ note under `00_Memory/dlq/` with the expected frontmatter fields, instead of a silently-incomplete report |

Read-only evals run directly against the resolved vault; anything that writes runs
against a throwaway copy (`evals/_sandbox.py`) so the real `./vault` is never touched.
If `./vault` doesn't exist yet, `run.py` exits `2` with a `corpus not present` detail on
every eval rather than crashing — expected mid-build, before the example-vault content
lands.

```bash
uv run --project scripts python3 evals/run.py --json
```
