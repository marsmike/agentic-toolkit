---
description: Titles, intros and sections of the generated domain maps (read by map_build.py)
---

# Maps config

One `## <domain>` block per `domain/*` tag that deserves more than the defaults. Optional
`title:` line, intro prose, then `- Section: kind, kind` bullets in the order the map shows them;
`- Start here: [[Note]], [[Note]]` pins notes ahead of the most-linked ones. Kinds no section
names are grouped by kind after the sections. Domains without a block get a map anyway.

## toolkit-meta
title: Toolkit
How the agentic toolkit itself works: the retrieval, graph and pipeline ideas behind it, the tools
it wraps, and the guides for running and maintaining it.

- Concepts: concept
- Guides: guide
- Tools: tool-landmark

## birding
title: Birding
The field-guide project and the birding area it feeds: species accounts, sourcing, sightings.

## homelab
title: Home lab
The home-lab migration and the network it runs on.
