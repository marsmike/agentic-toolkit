# agentic-toolkit — The Next Big Iteration

## Context

The toolkit (24 plugins, one private monorepo) and feinschmiede (media rendering) are being consolidated into **one open-source, vault-first monorepo**, continuously delivered, with personal data moved out of code and into the Obsidian vault. This session produced the full design through: a survey of the v1 repo, web research on graphify.com and the GraphRAG framework landscape, two deep research passes over TheVoid vault (which contained Mike's own half-drafted spec in `02_Projects/agentic-toolkit/Knowledge-Graph-Integration.md`), and a critical review of the plan against the vault's harness-engineering research. This document is the founding artifact of the iteration: every decision citing the vault note that earned it (the ratchet, practiced from line one).

## The seven goals (verbatim intent, the plan's acceptance criteria)

1. Consolidate research + plugin activities into one effort
2. Vault first: every plugin can use vault memory and knowledge
3. Others can reuse everything — including setting up the knowledge base itself
4. Media creation skills integrate cleanly as fully standalone plugins — no external ecosystem dependencies
5. Differentiation: the repo showcases state-of-the-art agentic engineering and feeds Mike's social presence
6. No AI slop: small perfect code, on-point skills, everything working together
7. Continuous delivery; consolidate plugins to a curated core, archive the rest

## Architecture

```
agentic-toolkit/                    # NEW public repo, fresh git history (privacy), MIT
  .claude-plugin/marketplace.json   # sources: ./plugins/<name>
  contract/                         # the constitution — no code
    VAULT_SCHEMA.md                 #   from TheVoid CLAUDE.md; frontmatter table is a FLOOR
    KNOWLEDGE_API.md                #   the only way plugins query knowledge
    PROFILE.md                      #   "fill from Obsidian" convention
    ROUTING.md                      #   multi-model hard rules (DeRonin pattern)
    templates/                      #   vault CLAUDE.md template for `vault init`
  core/                             # Python (uv workspace member): toolkit CLI + lib
    toolkit_core/{profile,vault,knowledge}.py
    cli: `toolkit vault init` · `toolkit doctor` · `toolkit profile`
  crates/                           # Rust (cargo workspace), CLI-in/JSON-out only
    farsight/                       #   hybrid BM25+vector search (vault + PDF chunks)
    gaiafield/                      #   knowledge graph over existing wikilinks → SQLite
  plugins/                          # flat, curated, added one release at a time
  vault/                            # the example vault (see below)
  docs/                             # PLAN.md, architecture, plugin-authoring, rendered tech-radar
  .github/workflows/                # path-filtered CI, gitleaks, release-binaries
```

**Hard rules:** plugins depend on `core`/`contract` only, never on siblings — cross-plugin behavior composes through vault notes. Rust engines are process-boundary binaries (no PyO3); prebuilt for macOS/Linux/Windows via tag-triggered CI, Python fallback until parity. Repo keeps the name `agentic-toolkit`; v1 repo is frozen as the archive. Reserved names in use: **farsight**, **gaiafield** (Void Trilogy); private evictions go to a separate private repo (querencia/eigenwerk, named later).

## Core concepts (each cites the vault note that earned it)

1. **Profiles ("fill from Obsidian")** — resolution order env → `$VAULT/Config/toolkit/<plugin>.md` → shipped default. Identity lives in the vault, repo ships behavior. Secrets stay in `~/.env`/keychain — never in the vault, never in the repo. *Precedent: `Mike.md` "AI Assistant Context Summary", `04_Resources/AboutMe/` style prompts.*
2. **Eval gates (Graduation Pattern)** — every plugin ships capability evals that start low and graduate into a regression suite; green regression suite gates trunk merges. This resolves the CD-vs-reliability tension. *`Concepts/Graduation-Pattern.md`; SkillsBench: ungated skills degrade −1.3pp; `Reliability-Over-Capability.md`.*
3. **The public ratchet** — every contract/CLAUDE.md rule cites the dated failure that earned it; changelog links rule → incident → regression case. *Osmani field survey: "every line traces to a specific historical failure."*
4. **Two hook classes** — *ratchet hooks* (deterministic failures, auto-enforced) vs *stop-and-ask hooks* (judgment calls → decision log/ADR). *web3nomad's judgment-vs-bug counter in the Osmani note; arscontexta fix-vs-report gate.*
5. **Dead-letter question as acceptance criterion** — every shipped automation names where its failures go; `toolkit doctor` surfaces the DLQ. Confidence labels gate auto-apply vs report (guards gaiafield against "successful corruption"). *arscontexta DLQ claim.*
6. **Dual-channel descriptions** — retrieval-verification loop (predict-from-description, score 1–5, flag <3) ships as an obsidian-plugin maintenance skill; BM25 queries condensed to 3–5 high-IDF terms. *arscontexta BM25-dilution claims.*
7. **Listing budget** — curated set capped by the ~25–30 item Tier-1 discovery ceiling; Osmani scope test as admission bar: "if you cannot name the behaviour a component delivers, remove it." *`Skills-Architecture-Redesign-Research-Findings`.*
8. **Inter-plugin output contracts** — versioned, documented in `contract/` — the monorepo-native frontier no single-agent harness essay addresses. *@jsyqrt in Osmani note.*

## Engines

**farsight** (Rust): hybrid BM25+vector search; replaces `obsidian/scripts/hybrid_search.py`, then embeddings generation, then techref's search core (same engine, two frontends). Candidate stack tantivy + usearch + fastembed, pinned at implementation.

**gaiafield** (Rust): expose the graph that already exists — TheVoid has 88.7% link coverage, ~11.8 wikilinks/note. v1: deterministic extraction (wikilinks/frontmatter/tags → SQLite; no LLM edges, can't rot). v2: inferred edges above the calibrated 0.70 similarity threshold, confidence-labeled EXTRACTED/INFERRED/AMBIGUOUS + surprise scoring. v3: Leiden communities, causal edge types, OKF export, optional Graphify MCP bridge. Framework research verdict: build native (graphify.com = Graphify Labs, YC S26 — excellent blueprint, wrong dependency: Python CLI, no library API, cloud-tier incentive risk; Kuzu is Apple-archived — SQLite now, LadybugDB as upgrade path). Graph positioning: complements vector+grep for global/multi-hop questions; does not replace local retrieval.

## The example vault (`./vault`) — lands in R0

Five roles: (1) `vault init` template; (2) deterministic test corpus for farsight/gaiafield/contract (planted graph structure, schema edge cases, unknown-frontmatter-key tolerance); (3) executable contract — CI fails schema changes that don't update the example; (4) Graduation-Pattern eval substrate — public, reproducible, cheap; (5) the ratchet's public corpus — anonymized minimal repros of real TheVoid failures become regression cases with dated citations.

**Using your own vault:** `./vault` is the out-of-the-box default — clone the repo and everything works immediately against it. To point the toolkit at a real vault, set `TOOLKIT_VAULT=/path/to/your/vault` (resolution order: env var → `./vault` fallback; documented in `contract/PROFILE.md` and readable via `toolkit doctor`). `toolkit vault init /path/to/new` scaffolds a fresh personal vault from the same template. Tests and evals always run against `./vault` regardless of the env var, so a user's vault is never touched by CI or test runs. Design: ~100–150 notes (below the 200-note structural threshold from arscontexta's scale curve) at realistic ~10 links/note density; one clearly-fictional persona for profile demos; **content = the toolkit's own documentation written as vault notes** — the docs demo the system by being the system. Growth only via init needs, test cases, ratchet repros.

## Curation waves

- **Core wave:** obsidian → readwise → memory → research → farsight → techref → gaiafield → feinschliff
- **Second wave:** tech-radar (renders into docs/ as the public SOTA view), feinbild/feinklang/feinschnitt, imagine, elevenlabs, handoff, autoresearch (carries the eval/self-improvement loop — must survive curation)
- **Private repo:** whatsapp, music-coach, memory identity
- **Archive (frozen v1):** crowd, cli-recorder, social, proxmox, codescan, notebooklm, todoist, workflows, remotion — re-entry possible if they earn it against the admission bar

feinschmiede is absorbed: fein-* plugins keep their names (shipped brand, PyPI continuity); brand packs become data — a neutral default pack ships, and custom packs load externally via profiles; downstream consumers pin released versions.

## Delivery model

- **R0 — walking skeleton (one release):** new repo, `contract/` extracted from TheVoid CLAUDE.md, `toolkit vault init` + `doctor`, example vault, obsidian plugin on the platform, CI + gitleaks. Proof: a stranger clones, inits a vault, installs one plugin, it works.
- **R1…Rn:** one increment each — next plugin curated onto the platform or next engine milestone (farsight parity → gaiafield v1 → v2). Every merge: version bump, evals green, changelog entry (doubles as social material). The repo is never publicly mid-migration.
- **Flywheel as operating system:** research/readwise capture SOTA → distill to vault → tech-radar positions → features cite vault notes → changelog/social amplify. Goal 1 and Goal 5 are the same loop.

## Config discipline (from the 2026-07-26 config-restructure handoff)

The capture-folder handoff and its new notes add four binding rules:

- **Instruction budget is shared slots across all config tiers** (~100–150 after the system prompt), not lines per file (*Multi-Project-Claude-Code-Organization-2026*). The toolkit's repo CLAUDE.md is a **router** (like the global one now is), pointing into `contract/` and `docs/` — it answers nothing itself.
- **Delete-over-add for stronger models**: Anthropic cut >80% of Claude Code's system prompt with no eval loss; weaker-model constraints become conflicting instructions (*Context-Engineering-for-Claude-5-Unhobbling*). Every contract rule gets the ratchet citation AND a removal condition — the config node's standing rule, now with first-party evidence.
- **Skill references load only on invocation**: depth in `references/` is invisible when a workflow runs inline. Hard requirements must live in the file that is *always* loaded (contract / vault CLAUDE.md template), with skills carrying only depth. The `vault init` template inherits this split.
- **MCP-vs-filesystem stance is now documented** (*Obsidian-Agent-Access-MCP-vs-Filesystem-2026*, ~35× token overhead): the toolkit's filesystem+CLI approach is the stated architecture, cited in `contract/KNOWLEDGE_API.md`.

## Long run

- **TheVoid in git** — provenance layer, not sync (Obsidian Sync stays): gitignore `.smart-env` (227M), LFS/exclude binaries (~100 PDFs, 118 PNGs), NAS remote, scheduled auto-commit via existing maintenance. Payoff: git-blame receipts for the ratchet, diff-based distill review, temporal edges for gaiafield from commit history. Gated on snapshot tooling in the obsidian plugin.
- **OKF-compatible export** from gaiafield (vault note flags OKF as "the closest external standard to what this vault already is").
- **Quick wins from the vault's own list** (fold into early increments): `ENABLE_TOOL_SEARCH=true`, OTEL env vars, SkillsBench scoring of top-10 skills.

## R0 build log — how the walking skeleton was built

New repo scaffolded at `~/Developer/agentic-toolkit-v2` (local name only; at publish, GitHub `agentic-toolkit` v1 is renamed to the archive and this repo takes the name). I orchestrate; subagents own **disjoint directories** so they cannot collide (per `nodes/parallel-agents.md` discipline); all git commits are made by the orchestrator with explicit paths, never `git add -A`. Vault access is read-only for all agents (vault-guard hook respected; nothing in TheVoid is modified).

**Stage 0 (orchestrator, sequential):** scaffold repo skeleton — git init, uv + cargo workspace roots, directory tree, `.claude-plugin/marketplace.json`, router-style CLAUDE.md, `docs/PLAN.md` (this plan with full vault citations).

**Stage 1 (one agent, blocking):** `contract/` — extract VAULT_SCHEMA.md from TheVoid's CLAUDE.md (~145 lines, authoritative; schema documented as floor-not-ceiling), PROFILE.md, KNOWLEDGE_API.md, ROUTING.md, and the `vault init` CLAUDE.md template with the always-loaded/skill-depth split. Everything downstream depends on this.

**Stage 2 (parallel agents, disjoint dirs):**
- *core agent* — `core/`: toolkit_core (profile.py, vault.py with `TOOLKIT_VAULT` → `./vault` resolution, frontmatter IO tolerant of unknown keys), CLI `toolkit vault init` (scaffolds from the `./vault` template) + `toolkit doctor` (active vault, profile completeness, DLQ surfacing stub), pytest suite.
- *example-vault agent(s)* — `vault/`: ~100–150 fictional-persona notes that are the toolkit docs (PARA, distill workflow, harness concepts), realistic link density, planted graph structure + schema edge cases for engine tests; profile examples.
- *obsidian-plugin agent* — `plugins/obsidian/`: port from v1 (`~/Developer/agentic-toolkit/obsidian`), vendored env dropped (uv-managed), profile convention adopted, retrieval-verification skill added, skill files within DESIGN.md budgets.
- *CI agent* — `.github/workflows/`: path-filtered lint+test, gitleaks, release-binaries skeleton (no crates built in R0).

**Stage 3 (orchestrator + one review agent):** integration — evals run against the example vault (capability evals for obsidian plugin, schema-consistency check contract↔example), the R0 "stranger test" (fresh clone → `vault init` → plugin install → smoke test), then an adversarial review agent against the seven goals + Osmani scope test before anything is declared done.

Out of scope for R0 (subsequent releases): farsight, gaiafield, feinschmiede absorption, further plugins, TheVoid-in-git, publishing to GitHub.

## Verification

- Stranger test end-to-end on a clean clone: `toolkit vault init` produces a valid vault; `claude plugin marketplace add <local path>` + install obsidian plugin succeeds; one skill invocation works against the example vault.
- `pytest` green in `core/`; schema-consistency CI check fails when VAULT_SCHEMA.md and examples/vault diverge (verified by intentional break).
- gitleaks + manual scan: no personal data anywhere (the example vault's persona is fictional; profiles are examples only).
- Every vault citation in `docs/PLAN.md` resolves to a real note in TheVoid.
- Seven goals each traceable to at least one shipped R0 artifact or explicitly deferred with its release named.
