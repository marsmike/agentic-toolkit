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
fast and deterministic — this vault's ~90 notes, dense linking, and three recognizable clusters
(see [[Test-Corpus-Map]]) are sized for exactly that. Concretely, an obsidian-plugin distill eval
can file one of the three example captures and check the proposed placement lands in a sensible
folder; a search eval can query for "storage shelf" and expect
[[Hardware-Inventory]] and [[Weekly-Review|the home-lab weekly review]] to rank above anything in
the birding cluster.

## What green actually certifies

A green regression suite means every previously-observed failure mode stays fixed, not that the
plugin is bug-free in general — evals only cover what's been added to them, which is the entire
point of the graduation pattern: coverage grows from real incidents, not from an attempt at
exhaustiveness up front.

## Related

- [[The-Graduation-Pattern]]
- [[Test-Corpus-Map]]
- [[Autoresearch-Eval-Loop]]
- [[Toolkit-Maintenance]]
