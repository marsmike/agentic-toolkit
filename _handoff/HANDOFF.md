<!-- latest handoff pointer — see HANDOFF-toolkit-rebuild-01.md -->

---
stream: toolkit-rebuild
seq: 1
prev:
title: "R0-R6 shipped public: vault-first toolkit, engines, docs site, observer pattern"
date: 2026-07-26T21:37:40
repo: "agentic-toolkit"
branch: "main"
tool: claude-code
---

# Handoff — R0-R6 shipped public: vault-first toolkit, engines, docs site, observer pattern
_stream `toolkit-rebuild` · seq 1_

## Goal

Ship marsmike/agentic-toolkit as the public, vault-first Claude Code toolkit — curated
plugins over an Obsidian-style vault, Rust engines, continuous delivery with the observer
pattern, docs = the vault published to GitHub Pages. Seven goals in docs/PLAN.md are the
acceptance criteria.

## Status

R0–R6 shipped in one session (2026-07-26). Repo is PUBLIC, site live at
https://marsmike.github.io/agentic-toolkit. Marketplace 2.6.0 with 3 plugins (obsidian
2.5.0, readwise, memory). Engines released: farsight-v0.1.1, gaiafield-v0.2.0 (all 4
platforms; ring/musl verified live). All suites green: cargo 19, pytest 16, evals 7/7 +
4/4 + 3/3, docscheck 3/3. Docs adversarially verified against the running system; all 10
findings fixed (PR #5). README redesigned as tiered first contact (PR #4). Local repo
~/Developer/agentic-toolkit on main, clean; legacy at ~/Developer/agentic-toolkit-legacy
(private archive, also NAS-mirrored as agentic-toolkit-legacy.git).

## Tried & Ruled Out

- Multi-repo split (gaiafield/knowledge-skills repos, meta marketplace) → rejected for
  KISS; scaffolds were built and deleted. Don't re-propose.
- Graphify/Graphiti/LightRAG/Cognee as the knowledge layer → build-native won (vault is
  already a graph; Kuzu is Apple-archived; SQLite now, LadybugDB as upgrade path).
- Pooled calibration statistics → cluster-size artifact (70% of pairs flagged); replaced
  by tight-cluster leave-one-out (gates 0.72/0.67).
- Stub-only eval coverage of engine boundaries → masked a real contract break; evals now
  must carry a real-binary phase.
- fastembed/ONNX for embeddings → musl cross-compile risk; model2vec-rs (potion-base-8M)
  chosen, zero C++ in the embedding stack.
- Hardcoded corpus counts in tests → broke on vault growth; counts derive from Index.md.

## Key Decisions

- Vault ships identity, repo ships behavior; profiles resolve env → Config/toolkit/*.md
  → defaults. Secrets never in vault or repo.
- contract/KNOWLEDGE_API.md v2 rule 1: inferred edges are REPORT-ONLY forever.
- Observer pattern is standing process: every builder gets an adversarial verifier
  before commit; findings become [earned:] citations (the ratchet).
- Governance: Mike AND Claude merge green-CI PRs via admin bypass (`gh pr merge
  --admin`); outsiders face full ruleset. Ruleset/visibility changes are Mike-only
  (deny rules in .claude/settings.local.json).
- Curation: research/techref/feinschliff (feinschmiede absorption) deferred; crowd,
  notebooklm etc. stay archived unless they clear the admission bar.

## Evidence & Data

- Calibration (current corpus): intra 0.807 / cross 0.630 / separation 0.177; 218
  INFERRED + 279 AMBIGUOUS; numbers drift with corpus growth — `gaiafield calibrate`.
- Example vault: 79 active notes, ~829 wikilinks, planted invariants (ONE dangling link,
  0 boundary violations) enforced by cargo test — a stray `[[...]]` in prose breaks CI.
- Headless: `--allowedTools` is ONE comma-separated arg; `Bash(env:*)` required.
- Mike's env has a stale ANTHROPIC_API_KEY that breaks `claude -p` (strip with env -u).
- Rituals: scripts/coldboot.sh (--live for isolated claude -p stage), scripts/docscheck.sh.

## Next Step

No task is mid-flight — next increment is Mike's call. Ranked options from the roadmap:
1. Port the research plugin (next core-wave item) from agentic-toolkit-legacy/research,
   following the readwise-port pattern (curation brief + observer).
2. feinschmiede absorption (fein-* plugins in, brand packs as data) — biggest chunk.
3. Graph frontier: surprise candidates in a weekly-review skill, Leiden communities,
   OKF export (gaiafield v3 targets in crates/gaiafield/README.md).
4. Social flywheel: CHANGELOG → announcement content (goal 5, untouched so far).

## How to Verify

`cd ~/Developer/agentic-toolkit && cargo test --workspace && uv run pytest core/tests &&
uv run python plugins/obsidian/evals/run.py --json && scripts/docscheck.sh` — all green.
Site: curl -s -o /dev/null -w "%{http_code}" https://marsmike.github.io/agentic-toolkit/ → 200.

## Quick Start

Run `/handoff:handoff-resume` in ~/Developer/agentic-toolkit, then ask Mike which of the
four Next Step options to take. Memory file gaiafield-repo.md has the full state.

## Repo State (auto-captured)

- **Branch:** `main`
- **Recent commits:**
  - `457e6e1 docs: close all 10 docs-vs-reality findings; add docscheck ritual (#5)`
  - `d5ac958 docs: README as tiered first contact — banner, badges, diagrams, verified doc links (#4)`
  - `43b1829 R6: the vault becomes the published documentation`

```
# git status --short
?? _handoff/
```
