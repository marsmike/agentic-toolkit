Bringing an existing folder of plain Markdown notes into this vault doesn't require adding
frontmatter to everything before the import counts. This guide itself has none — on purpose — to
prove the point it's making: a parser that chokes on a missing frontmatter block would already
have failed on the file you're reading right now.

## What actually happens on import

Nothing is auto-added. A note with no frontmatter at all stays exactly as it was, readable and
linkable, until someone (or an agent, during a later distill-style pass) deliberately decides it's
worth promoting to a fuller schema — description, status, tags, the works. Being under-specified
is not an error state; see the frontmatter-floor rule this vault documents in
04_Resources/Concepts/Frontmatter-as-Floor-Not-Ceiling.md, which this note is a plain, load-bearing
instance of rather than just a description of.

## Why not require frontmatter on import

Requiring it up front means either blocking the import on busywork, or the importing tool
inventing plausible-looking values for fields it has no actual information about — a `status` or
`created` date guessed by a script is worse than an honestly absent one, because it looks
authoritative without being true.

## When to add frontmatter later

Once a note earns real vault integration — links added, an enrichment pass touches it, someone
decides it belongs in the toolkit's documented taxonomy — that's the natural point to backfill
`description`, `status`, and `tags` rather than leaving it perpetually bare.

Related ideas: Frontmatter-as-Floor-Not-Ceiling, Two-Phase-Distillation, Capture-Conventions.
(Deliberately written as plain text rather than as linked notes in this paragraph — see
04_Resources/Guides/Test-Corpus-Map.md for why this note carries no frontmatter and is the
vault's parser-tolerance specimen.)
