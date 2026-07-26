---
description: The vault's search engine — stateless BM25, Rust, CLI-in/JSON-out, one per-query scan over active-content notes with no persisted index to go stale.
status: active
created: 2026-02-04
kind: tool-landmark
topics:
  - retrieval
  - engines
tags:
  - domain/toolkit-meta
---

# Farsight

The toolkit's first native engine (R1, `crates/farsight/`, currently **0.1.1**): a **stateless
BM25** search binary over a vault's active-content notes, CLI-in/JSON-out per
[[CLI-in-JSON-out-Contracts]]. `farsight query "<terms>" --vault ./vault --k 10 --json` re-scans
`02_Projects`/`03_Areas`/`04_Resources` plus any root note with its own `status: active` (this
vault's one case: [[Alex-Vega]]) on every call — the same active-content filter
`contract/VAULT_SCHEMA.md` defines. It replaces the BM25 half of
`plugins/obsidian/scripts/search.py`, which now prefers a `farsight` binary when one is on
`PATH`/`TOOLKIT_FARSIGHT_BIN` and falls back to its own Python BM25 otherwise.

## What shipped, and what didn't

Docs written before R1 described this as "hybrid BM25+vector search." That's the long-run name for
the engine in `docs/PLAN.md`, not R1's scope: **there is no vector half, and no PDF-chunk support,
yet.** `crates/farsight`'s dependencies stop at `clap` + `serde`/`serde_yaml` — no embedding stack
at all. See [[Hybrid-Retrieval]] for the fusion idea this engine is aimed at, and why it isn't
there yet.

## Why no persisted index

Every `query` re-scans from scratch: `k1=1.5`, `b=0.75` over each note's title + doubled
`description` + the first 2000 characters of body — the same formula `search.py` already used, so
this is a drop-in, not a divergent reimplementation. At vault scale (~100–1500 notes) a full scan
is fast enough that a stateless design is a deliberate trade: it eliminates rebuild-timing,
partial-write, and cache-invalidation bugs by never having a cache to invalidate. See
[[BM25-Dilution]] for a failure mode this formula doesn't fully absorb on its own (a long
`description` field still dilutes keyword weight).

## What it deliberately doesn't do

Farsight answers "what matches this query," not "what connects to this note" — that's
[[Gaiafield]]'s job. The two are complementary, queried separately, composed by whoever's calling
them.

## 0.1.1 — the cross-engine scope fix

R1 shipped scoped only to `02_Projects`/`03_Areas`/`04_Resources`; farsight 0.1.1 (R4) added the
root-note `status: active` clause, ending a disagreement with gaiafield where the graph could
traverse to [[Alex-Vega]] but search couldn't find it at all.

## Where this vault exercises it

[[Toolkit-Maintenance]] spot-checks Farsight against real queries over
[[Field-Guide-Project|field-guide]] and [[Home-Lab-Migration|home-lab-migration]] content, and
[[Test-Corpus-Map]] documents the planted specimens
([[Retrieval-Verification-Loop-Long-Description-Specimen]] and its sibling) the `search_parity`
eval scores against.

## Related

- [[Hybrid-Retrieval]]
- [[Gaiafield]]
- [[CLI-in-JSON-out-Contracts]]
- [[BM25-Dilution]]
- [[Toolkit-Maintenance]]
- [[Test-Corpus-Map]]
- [[Capability-Probing]]
