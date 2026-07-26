---
description: When plugins compose through vault notes instead of direct calls, the note shape one plugin writes and another reads needs its own versioned, documented contract.
status: distilled
source: "(none — originated from toolkit design work)"
processed_date: 2026-02-16
created: 2026-02-16
kind: concept
topics:
  - architecture
  - inter-plugin-contracts
tags:
  - domain/toolkit-meta
---

# Versioned Inter-Plugin Contracts

Plugins in this toolkit never import from a sibling plugin — composition happens through the
vault: one plugin writes a note, another plugin reads it later. That avoids the tight coupling of
direct calls, but it introduces a different coupling that's easy to overlook: the *shape* of the
note itself (which frontmatter fields, what the body structure looks like) becomes a contract
between the two plugins, just an indirect one.

## Why it needs the same discipline as a versioned API

An undocumented, unversioned note shape can drift silently — plugin A changes what it writes,
plugin B keeps expecting the old shape, and the failure only surfaces at read time, far from
where the change was made. Documenting the shape in `contract/` and versioning it the way
[[CLI-in-JSON-out-Contracts|a CLI's JSON output]] is versioned closes that gap: a breaking change
to the shape is a visible, deliberate decision, not an accident.

## The frontmatter-floor tension this sits next to

[[Frontmatter-as-Floor-Not-Ceiling]] says tooling must tolerate fields it doesn't recognize.
This concept says the fields two *specific* plugins agree to exchange still need a documented,
versioned shape between those two — tolerance of the unknown and a contract for the known aren't
in conflict; they apply to different fields.

## Related

- [[CLI-in-JSON-out-Contracts]]
- [[Frontmatter-as-Floor-Not-Ceiling]]
- [[Filesystem-vs-MCP-for-Agent-Tool-Access]]
