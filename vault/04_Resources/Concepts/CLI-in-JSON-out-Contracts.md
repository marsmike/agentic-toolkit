---
description: Every engine and plugin surface is a CLI that takes flags in and returns JSON out — a stable, language-agnostic seam between components that never share process memory.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-04
created: 2026-02-04
kind: concept
topics:
  - architecture
  - inter-plugin-contracts
tags:
  - domain/toolkit-meta
---

# CLI-in / JSON-out Contracts

Rust engines and Python plugins in this toolkit never share memory or call into each other's
internals — they communicate exactly the way two independent programs on the same machine should:
one runs a CLI, the other's stdout is JSON, parsed by whoever called it. No PyO3 bindings, no
shared library loaded into a host process.

## Why the boring seam is the right one

A process-boundary CLI can be replaced, rewritten in a different language, or run on a different
machine entirely without the caller changing anything except which binary it invokes. A shared
in-process binding couples the two components' build systems, versions, and crash domains
together — a panic in the engine takes down the caller too. [[Versioned-Inter-Plugin-Contracts]]
extends this same idea to the JSON shape itself: the output format is versioned and documented,
not just "whatever the current code happens to emit."

## Where it shows up in this toolkit

[[Farsight]] and [[Gaiafield]] are both CLI-in/JSON-out; `toolkit doctor` and `toolkit vault init`
follow the same contract from the Python side. No plugin reads an engine's internal index files or
database directly — only its documented CLI output.

## Related

- [[Versioned-Inter-Plugin-Contracts]]
- [[Farsight]]
- [[Gaiafield]]
- [[Toolkit-CLI]]
- [[Filesystem-vs-MCP-for-Agent-Tool-Access]]
