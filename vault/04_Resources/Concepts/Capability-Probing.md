---
description: Detecting what a binary can actually do at runtime via a side-effect-free check, rather than parsing a version number or letting a real call fail and crash.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-07-26
created: 2026-07-26
kind: concept
topics:
  - reliability
  - engines
tags:
  - domain/toolkit-meta
---

# Capability Probing

Once an engine binary ships multiple versions (gaiafield v1 with no inference, v2 with it), a
caller needs to know which capability the specific binary in front of it actually has — without
parsing a version string (which requires trusting a naming convention forever) and without just
making the real call and hoping it fails cleanly if unsupported (which can crash, hang, or write a
DLQ note for a state that isn't actually an error).

## The pattern

Probe for the capability itself, side-effect-free, before relying on it:

- `plugins/obsidian/scripts/graph.py`'s `_supports_inference()` calls the binary with `--help` and
  checks for the `infer` subcommand as a **whole word** — not a substring match. The first version
  of this check matched any `--help` output that *mentioned* "inference" anywhere in its prose,
  which false-positived on a v1 binary whose help text happened to describe something adjacent —
  turning a normal "this binary predates inference" state into a spurious DLQ entry. Exit-0 plus
  whole-word subcommand matching fixed it.
- `toolkit doctor`'s graph section (`core/toolkit_core/knowledge.py`) reads the *shape* of
  `gaiafield stats --json`'s output to distinguish three states: no `model` key at all means a v1
  binary that predates inference entirely; the key present but empty means a v2 binary that hasn't
  run `gaiafield infer` yet; populated means the normal reporting case. No version number is parsed
  anywhere in this logic.
- `search.py`/`graph.py`'s binary-preference chains (`TOOLKIT_FARSIGHT_BIN`/`TOOLKIT_GAIAFIELD_BIN`
  env var, else PATH, else absent) distinguish a binary that's simply **absent** (normal, silent
  degrade) from one that's **present but fails on a real call** (abnormal — writes a DLQ note). The
  absent case is never treated as an error; the present-but-broken case always is.

## Why this over the alternatives

Parsing a version string requires every caller to know the exact version a capability shipped in,
forever, and breaks the moment a version scheme changes. Letting a real call fail requires the
capability's absence to always fail in a safe, recognizable way — a stronger assumption than a
cheap side-effect-free probe needs. Capability probing sits between the two: cheap, forward-
compatible (a future v3 binary still answers the same `--help` probe correctly), and it never
mistakes "this feature doesn't exist yet" for "this call failed."

## Related

- [[Dead-Letter-Queues-for-Automation]]
- [[CLI-in-JSON-out-Contracts]]
- [[Inference-Write-Policy|Report-Only Inference]]
- [[Gaiafield]]
- [[Farsight]]
- [[Toolkit-CLI]]
