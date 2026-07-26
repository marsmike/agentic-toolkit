---
description: How to run a plugin's capability evals against this example vault, and what a passing regression suite actually certifies.
status: active
created: 2026-02-14
kind: guide
topics:
  - evals
tags:
  - domain/toolkit-meta
---

# Running Evals

Every plugin ships evals that follow [[The-Graduation-Pattern]]: a low-bar starting set that grows
as real failures surface, gating trunk merges once promoted into the regression suite. Evals run
against `./vault` — this example vault — never against a vault reached via `TOOLKIT_VAULT`, per
`contract/PROFILE.md`.

## Why this vault as the eval substrate

An eval needs a corpus with enough realistic structure to be meaningful but small enough to be
fast and deterministic — this vault's 78 active notes (see `Index.md`), dense linking, and three
recognizable clusters (see [[Test-Corpus-Map]]) are sized for exactly that. Concretely, an
obsidian-plugin distill eval can file one of the three example captures and check the proposed
placement lands in a sensible folder; a search eval can query for "storage shelf" and expect
[[Hardware-Inventory]] and [[Weekly-Review|the home-lab weekly review]] to rank above anything in
the birding cluster.

## Where the suites live

`uv run pytest core/tests` covers `core`'s own contract (vault resolution, doctor, profile); each
plugin ships its own `evals/run.py`, emitting JSON `{eval, pass, detail}` per check (`obsidian`:
seven evals including `search_parity` and `inferred_candidates`; `readwise`: four; `memory`:
three); `cargo test --workspace` covers the Rust engines directly against `./vault` (farsight's
`query_test.rs`, gaiafield's `graph_test.rs`). An eval whose subject binary isn't built yet passes
with a `"<engine> not present"` detail rather than failing — release binaries and the Rust crates
they come from aren't always available in every environment an eval runs in.

## Stub-driven evals have a real gap — cover it with a real-binary phase

R5's `inferred_candidates` eval was, for most of its life, driven entirely by a hand-written stub
standing in for a not-yet-released v2 binary — and the stub silently encoded the same missing-field
bug the real CLI spec had (see [[Surprise-Scoring]]'s coordination-bug note). Every stub-driven
assertion passed while the real behavior was wrong. The fix wasn't a better stub — it was adding a
fourth phase that runs against a **real** gaiafield binary (`TOOLKIT_GAIAFIELD_BIN`) when one is
available, so a stub can never again drift from the real CLI's shape undetected. See
[[The-Observer-Pattern]] for how this was caught in the first place.

## What green actually certifies

A green regression suite means every previously-observed failure mode stays fixed, not that the
plugin is bug-free in general — evals only cover what's been added to them, which is the entire
point of the graduation pattern: coverage grows from real incidents, not from an attempt at
exhaustiveness up front. A stub standing in for a missing binary is exactly the kind of coverage
gap that requires the real-binary check above to actually close.

## Related

- [[The-Graduation-Pattern]]
- [[Test-Corpus-Map]]
- [[Autoresearch-Eval-Loop]]
- [[The-Observer-Pattern]]
- [[Surprise-Scoring]]
- [[Toolkit-Maintenance]]
