---
description: Pulls Readwise highlights into 01_Capture/ with origin-prefixed filenames — the second core-wave plugin, feeding the same distill pipeline the obsidian plugin owns.
status: active
created: 2026-02-08
kind: tool-landmark
topics:
  - capture
  - integrations
tags:
  - domain/toolkit-meta
---

# Readwise Plugin

Pulls new highlights from a Readwise account into `01_Capture/` as flat, origin-prefixed files
(`Readwise-<slug>.md`) — see [[Capture-Conventions]] for the naming rule this follows. Does not
distill anything itself; that's [[Obsidian-Plugin|the obsidian plugin's]] job, reached through the
same capture inbox rather than a direct call between the two, per
[[Versioned-Inter-Plugin-Contracts]].

## Why overlap-checking matters here specifically

Readwise captures and other capture sources (an X-bookmark export, a manual research note) overlap
more than expected — the same article or thread gets captured twice from two different origins.
[[Two-Phase-Distillation]]'s "check for prior distillation before writing" rule exists largely
because of collisions exactly like this one.

## Credentials

The Readwise API token is an environment variable, never a vault field — see the Secrets section
of `contract/PROFILE.md` and [[Fill-From-Obsidian-Profiles]] for the general rule this follows.

## Related

- [[Capture-Conventions]]
- [[Obsidian-Plugin]]
- [[Two-Phase-Distillation]]
- [[Fill-From-Obsidian-Profiles]]
- [[Versioned-Inter-Plugin-Contracts]]
