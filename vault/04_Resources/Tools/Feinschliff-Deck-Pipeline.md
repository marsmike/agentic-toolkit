---
description: The fein-* brand-pack pipeline for decks, diagrams, and data viz — feinschmiede's media plugins absorbed into the platform with brand packs as data, not code.
status: active
created: 2026-02-10
kind: tool-landmark
topics:
  - media
  - brand-packs
tags:
  - domain/toolkit-meta
---

# Feinschliff Deck Pipeline

Part of feinschmiede's absorption into the platform: the fein-* plugins (deck-building,
diagramming, data-viz authoring) keep their shipped names for continuity, but a brand pack — the
visual identity a deck compiles against — becomes data the pipeline reads, not code baked into the
plugin. A neutral default pack ships with this toolkit; anything organization-specific stays
external, the same secrets-stay-out-of-the-repo instinct as [[Fill-From-Obsidian-Profiles]] applied
to visual identity instead of credentials.

## Why this is a media plugin, not a knowledge plugin

Unlike [[Obsidian-Plugin]] or [[Readwise-Plugin]], this pipeline doesn't read or write vault
knowledge directly — it consumes a brand pack and a content spec and produces a rendered artifact.
It integrates cleanly with the rest of the platform specifically *because* it's decoupled this
way: swapping it out wouldn't touch anything else curated here.

## Related

- [[Fill-From-Obsidian-Profiles]]
- [[Versioned-Inter-Plugin-Contracts]]
- [[Scope-Discipline-for-Curated-Systems]]
