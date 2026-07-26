---
description: Designing a system so identity, configuration, and knowledge live in a plain-file vault the agent can read and write directly, rather than in the application's own database.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-01-14
created: 2026-01-14
kind: concept
topics:
  - vault-architecture
  - agent-memory
tags:
  - domain/toolkit-meta
  - domain/agent-systems
---

# Vault-First Architecture

A system is vault-first when the plain-file vault is the source of truth and the application is a
thin reader/writer over it, rather than the reverse. Contrast with a database-first design where
the app owns a schema in its own store and periodically exports a human-readable view — the
export can always drift from what the app actually believes.

## Why it matters for agents specifically

An agent that reads and writes the same files a human edits in Obsidian gets three things for
free: the human can intervene with a plain text editor at any time, git or Obsidian Sync gives
free version history without the app building its own, and every other tool that also speaks
plain Markdown (a static site generator, a second agent, a linter) can participate without an API.
See [[Fill-From-Obsidian-Profiles]] for the specific instance of this used for plugin identity, and
[[Filesystem-vs-MCP-for-Agent-Tool-Access]] for why the access path itself stays filesystem-first
too.

## The corollary that's easy to miss

If the vault is the source of truth, nothing downstream is allowed to silently diverge from it —
generated views (an index, a graph database) must be regenerable from the vault, never edited
directly themselves. [[Knowledge-Graphs-from-Wikilinks]] and the toolkit's own `Index.md`
convention both follow from this. The public [[Docs-Site]] is the same corollary applied to
publishing: it renders the vault directly rather than maintaining a separate docs source that could
drift from what the vault actually says.

## Related

- [[Fill-From-Obsidian-Profiles]]
- [[Knowledge-Graphs-from-Wikilinks]]
- [[Filesystem-vs-MCP-for-Agent-Tool-Access]]
- [[PARA-Method]]
- [[Frontmatter-as-Floor-Not-Ceiling]]
- [[Docs-Site]]
- [[Alex-Vega]]
