---
description: Vault health checks — metadata normalization, orphaned notes, stale pages, and broken wikilinks — and what a lint pass should and shouldn't auto-fix.
status: active
created: 2026-02-18
kind: guide
topics:
  - vault-maintenance
tags:
  - domain/toolkit-meta
---

# Vault Maintenance and Linting

A lint pass over an active vault checks for a handful of specific things, each with a different
correct response:

- **Sourceless or statusless distilled notes** — flag for triage, don't guess a value.
- **Orphaned notes** — zero inbound links from active content. Expected for a fresh note that
  hasn't been enriched into yet; worth a look if it's been that way a long time.
- **Stale pages** — content that references something since renamed or removed elsewhere in the
  vault. Repair the reference if the target moved; flag if the target is genuinely gone.
- **Broken wikilinks** — a link whose target doesn't exist anywhere in the vault. Unlike a
  stale-but-repairable reference, this needs a human decision: was the target ever going to be
  written, or was this a typo?

## A broken link, on purpose, right here

This paragraph links to [[Nonexistent-Note-For-Linting-Demo]], which does not exist anywhere in
this vault. That's deliberate — see [[Test-Corpus-Map]] — so a linter's broken-link detector has
something real to catch in this example vault rather than only in a synthetic test fixture built
just for the linter's own test suite.

## What a lint pass should never do

Auto-delete a broken link, auto-invent the missing note, or silently strip a frontmatter field it
doesn't recognize — see [[Frontmatter-as-Floor-Not-Ceiling]]. Linting surfaces problems for a
human or a higher-judgment agent step; it doesn't resolve judgment calls itself, per
[[Judgment-Calls-vs-Deterministic-Failures]].

## Related

- [[Test-Corpus-Map]]
- [[Frontmatter-as-Floor-Not-Ceiling]]
- [[Judgment-Calls-vs-Deterministic-Failures]]
- [[Toolkit-Maintenance]]
