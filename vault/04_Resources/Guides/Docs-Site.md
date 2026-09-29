---
description: How the public docs site is built from this vault — pinned Quartz 4, the vault rendered directly with no separate docs source, and what's excluded from the publish.
status: active
created: 2026-07-26
kind: guide
topics:
  - docs-site
  - vault-architecture
tags:
  - domain/toolkit-meta
---

# Docs Site

The docs site isn't a separate documentation project — it's this vault, rendered. `.github/
workflows/docs.yml` builds `./vault` with [Quartz 4](https://quartz.jzhao.xyz/), pinned to release
tag `v4.5.2` (a specific tag, not a tracking branch, so an upstream Quartz change can't silently
break the build on its own schedule). `docs-site/quartz.config.ts` and `docs-site/quartz.layout.ts`
are copied over Quartz's own config files at build time; they're the only toolkit-authored files in
the pipeline; everything a visitor reads is a vault note.

## What gets published, and what doesn't

The workflow `rsync`s `vault/` into Quartz's `content/` directory, excluding five things:

- `00_Daily/` — the generated daily notes (`daily_build.py`) and the owner's own text in them; not a public docs surface.
- `00_Memory/` — agent self-memory; not a public docs surface.
- `01_Capture/` — the raw inbox; not-yet-distilled, not public docs surface.
- `05_Archive/` — frozen (`contract/VAULT_SCHEMA.md`: "never link here from new notes"); excluded
  explicitly, not just left unlinked — Quartz's Explorer and search list every page it builds
  regardless of whether anything links to it, so an unexcluded `05_Archive/` would still surface
  on the site.
- `.gaiafield/` — the local graph-engine's SQLite cache, a binary artifact, not a doc.

This matches the vault's own active-content filter (see `contract/VAULT_SCHEMA.md`): the filter
excludes `00_Memory`/`01_Capture`/`05_Archive` from search, enrichment and generated indexes, and
the publish step excludes the same three from the site, plus the engine-cache directory that isn't
part of the schema's folder table at all.

`Templates/` takes a different route: the rsync does **not** exclude it (so it does land in
`quartz/content/`), but `docs-site/quartz.config.ts`'s `ignorePatterns` tells Quartz not to build a
page for it — deliberately, since `Templates/` isn't itself vault content either. A wikilink to a
template is therefore never resolvable on the site; write one as plain text instead, the way the
two project `Weekly-Review.md` notes now reference `Templates/Weekly-Review`.

`Config/` is deliberately **included**, even though it looks like plumbing: active vault notes
wikilink into it directly (`[[Config/toolkit/obsidian.md]]` from
[[Profiles-and-Config]]), and excluding it would turn those into broken links on the live site.

## Wikilinks, backlinks, and the graph view

Quartz's `ObsidianFlavoredMarkdown` and `CrawlLinks` (configured with `markdownLinkResolution:
"shortest"`, mirroring how Obsidian itself resolves a double-bracket wikilink by basename rather
than full path) render this vault's wikilinks as real site links with no rewriting needed.
Backlinks and both a per-page local graph and an expandable global graph are on by default in
`quartz.layout.ts` — deliberately not trimmed for minimalism, since a knowledge-graph toolkit
documented as a knowledge graph is the point, not an incidental feature.

## Previewing locally

There's no separate local-preview script; mirror `docs.yml`'s own steps by hand: clone a pinned
Quartz 4 checkout, copy the two `docs-site/*.ts` files over its config, `rsync` `vault/` into its
`content/` with the same three excludes, then `npx quartz build --serve` from inside that checkout.

## Related

- [[Vault-First-Architecture]]
- [[The-Cold-Boot-Ritual]]
- [[Profiles-and-Config]]
- [[Test-Corpus-Map]]
