---
description: Naming, flatness, and provenance rules for 01_Capture/ — why a directory listing alone should show where every capture came from.
status: active
created: 2026-02-05
kind: guide
topics:
  - capture
tags:
  - domain/toolkit-meta
---

# Capture Conventions

`01_Capture/` is flat — no subfolders, ever — and every filename is hyphenated and prefixed by
origin: `Readwise-`, `Research-`, `X-Bookmark-`, or another source-specific prefix a plugin
introduces for itself. The three example captures in this vault
(`Readwise-Hybrid-Search-Landscape.md`, `Research-Leiden-Community-Detection.md`,
`X-Bookmark-Retrieval-Debate.md`) show the pattern.

## Why flat and prefixed, not foldered by source

A folder-per-source structure hides the one thing that actually matters at a glance: how much is
sitting untriaged, and from where. `ls 01_Capture/` answering that immediately is worth more than
the organizational tidiness a folder structure would add — see [[Atomic-Notes]] for the general
preference this vault has for small, flat, legible structure over deep hierarchy wherever legible
is achievable.

## What a capture is allowed to look like

Raw and untrusted — minimal or no frontmatter, informal prose, unresolved TODOs. See
[[Migrating-Notes-From-Plain-Markdown]] for a related case: this toolkit's tooling has to tolerate
notes with no frontmatter at all, not just captures with minimal frontmatter.

## The one-way link rule

Active content never links *to* a capture — a distilled note's `source` field points at the
original external source, never at the capture file that first held it. Removing a capture happens
through the vault's safe-delete surface after distilling it, never an irreversible raw delete.

## Related

- [[The-Distill-Workflow]]
- [[Two-Phase-Distillation]]
- [[Migrating-Notes-From-Plain-Markdown]]
- [[Readwise-Plugin]]
- [[Atomic-Notes]]
