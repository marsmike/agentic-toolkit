---
description: Direct filesystem and CLI access to vault content beats routing every read and write through an MCP server, by a wide token-overhead margin.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-13
created: 2026-02-13
kind: concept
topics:
  - architecture
  - tool-access
tags:
  - domain/toolkit-meta
  - domain/agent-systems
---

# Filesystem vs. MCP for Agent Tool Access

An MCP server sitting between an agent and a vault adds a protocol round-trip and a serialization
layer to every read and write that a direct `Read`/`Write`/`Edit`/`Grep` call over the filesystem
doesn't pay at all. Measured against real vault operations, the overhead comes out to roughly 35×
more tokens for the MCP path on comparable operations — large enough to be an architectural
decision, not a rounding error.

## Why this toolkit takes the filesystem-first stance

`contract/KNOWLEDGE_API.md` states plainly: no MCP server sits between a plugin and the vault. The
v0 surface is filesystem operations plus CLI commands that take flags in and return JSON out (see
[[CLI-in-JSON-out-Contracts]]); the v1+ engines ([[Farsight]], [[Gaiafield]]) extend that same
CLI-in/JSON-out shape rather than introducing a new access pattern.

## When MCP still makes sense

This isn't an argument that MCP is wrong everywhere — it's specifically about the high-frequency,
low-latency path of an agent reading and writing its own working vault. A one-off integration with
an external service that already speaks MCP is a different trade-off entirely.

## Related

- [[CLI-in-JSON-out-Contracts]]
- [[Vault-First-Architecture]]
- [[Farsight]]
- [[Gaiafield]]
