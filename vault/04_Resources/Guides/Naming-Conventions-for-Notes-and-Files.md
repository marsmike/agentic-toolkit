---
description: Filename conventions across captures, distilled notes, and projects — origin prefixes, author/year disambiguation, and when a plain title is fine.
status: active
created: 2026-02-17
kind: guide
topics:
  - note-taking
  - onboarding
tags:
  - domain/toolkit-meta
---

# Naming Conventions for Notes and Files

Different folders earn different naming rules, matched to what each folder needs a filename to
communicate:

- **`01_Capture/`** — origin-prefixed and hyphenated (`Readwise-`, `Research-`, …), so a directory
  listing shows provenance without opening anything. See [[Capture-Conventions]].
- **Distilled resource notes** — a plain descriptive title is usually enough
  (`Hybrid-Retrieval.md`); when a note is drawn from one external, attributable source, embedding
  author and year disambiguates it from an unrelated note on the same topic.
- **Project and area notes** — plain titles scoped by their folder. Two projects can legitimately
  share a filename (`Weekly-Review.md` exists under both [[Field-Guide-Project|field-guide]] and
  [[Home-Lab-Migration|home-lab-migration]]) because the folder itself is the disambiguator; no
  suffix is needed inside a project that only has one of each note type.

## Why filenames aren't forced to be globally unique

Requiring every filename to be unique vault-wide would push toward long, defensive names
("Field-Guide-Weekly-Review-2026-W29") even where the folder already disambiguates perfectly well.
A wikilink can always be qualified with a path (`[[home-lab-migration/Weekly-Review]]`) on the rare
occasion it's actually ambiguous from context — see [[Test-Corpus-Map]] for this vault's own
planted instance of the same-title case.

## Related

- [[Capture-Conventions]]
- [[Test-Corpus-Map]]
- [[Field-Guide-Project]]
- [[Home-Lab-Migration]]
