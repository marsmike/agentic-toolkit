---
description: Separating the agent that builds a release from the agent that adversarially reviews it before commit — an independent pass incentivized to find what's wrong, not to confirm the build works.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-07-26
created: 2026-07-26
kind: concept
topics:
  - reliability
  - agent-systems
tags:
  - domain/toolkit-meta
---

# The Observer Pattern

A builder agent that reviews its own work is checking whether the code does what the builder
*intended* — which is a much weaker test than whether it does what the contract actually requires.
The observer pattern splits the two roles: one agent builds a release deliverable, a second,
independent agent reviews it afterward with no stake in the build having succeeded, checking it
against the contract and the stated goals rather than against the builder's own assumptions.

`docs/PLAN.md`'s R3 stage already separated "integration" from "adversarial review agent," but R4
made this the standing practice: "this is the first release cycle run fully on the observer
pattern — every builder deliverable was adversarially verified by an independent agent before
commit" (`CHANGELOG.md`).

## What it actually caught

Every one of these was a real bug that a self-review would have had no reason to look for, because
the builder's own mental model didn't include the failure mode:

- **Incremental-deletion corruption (gaiafield 0.1.1).** The original incremental-indexer left
  other notes' edges *into* a deleted note as resolved rows — `neighbors` crashed, `path` routed
  silently through nodes that no longer existed. The builder's own tests passed; they tested
  deletion, not what deletion left behind in *other* notes' edges.
- **Cross-engine root-note scope disagreement (farsight 0.1.1).** Gaiafield's graph could reach
  [[Alex-Vega]]; farsight's search couldn't find it at all. Neither engine was wrong on its own
  terms — the inconsistency only shows up when you check them against each other.
- **The calibration bias (gaiafield 0.2.0).** The first `calibrate` implementation ran, produced
  plausible-looking numbers, and passed its own tests. It took a second pass actually comparing a
  cross-cluster score against the pooled "same-topic" one to notice the numbers were backwards.
  See [[Calibration-Bias]].
- **The missing `label`/`model` fields on `surprise` rows.** Two builders independently implemented
  their half of one CLI spec faithfully — and the spec itself silently contradicted
  [[Inference-Write-Policy|Report-Only Inference]]'s own rule, written an hour earlier. A stub-driven eval couldn't catch
  it because the stub encoded the same gap the spec did; only a real-binary integration pass
  exposed it. See [[Surprise-Scoring]].

## Why a builder can't be its own observer

None of these bugs were carelessness — in each case the code did exactly what its author intended.
The gap was between "does this do what I meant" and "does this hold up against the contract, the
other engine, and a real invocation" — three questions a second party is structurally better
positioned to ask, because it isn't the one holding the original assumptions.

## Related

- [[The-Ratchet]]
- [[Judgment-Calls-vs-Deterministic-Failures]]
- [[Dead-Letter-Queues-for-Automation]]
- [[Anonymized-Failure-Repros]]
- [[Calibration-Bias]]
- [[Inference-Write-Policy|Report-Only Inference]]
- [[Surprise-Scoring]]
