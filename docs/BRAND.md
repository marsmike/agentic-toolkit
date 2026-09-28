# Brand

**The idea, in one line:** a GenAI unisphere for your notes.

The naming already carries the theme — `unisphere` (the CLI, the one front door), `gaiafield`
(the knowledge graph engine), `farsight` (the search engine), and the vault itself: the Void.
This document makes that theme deliberate instead of accidental: how it should read, what the
words mean, what the images look like, and where the line is.

Names are a nod to Peter F. Hamilton's Commonwealth novels; this project is not affiliated with
him or his publishers.

## Voice

- **Confident, understated, a little far-future.** State what a thing does; let the scale imply
  itself. Not "revolutionary AI-powered knowledge management" — more like `unisphere status`'s
  own tone: plain, declarative, slightly wry.
- **Lore words only where they are real names** — `unisphere`, `gaiafield`, `farsight`,
  u-shadows, the Pilgrimage, dreams, longtalk, the Void. Everywhere else, plain words: search,
  graph, pipeline, notifications, cloud routine. A lore word never substitutes for the plain word
  that explains what a thing does — it sits *next to* it, in parentheses or a clause, the first
  time it appears in any document.
- **Scoped to where it can't be mistaken for the truth.** The structural words below (space,
  worlds, wormholes, star systems, core worlds, uncharted worlds) belong in visuals, taglines and
  friendly CLI flavor text — never in data output or command names. `unisphere graph stats`
  prints "1,485 nodes," not "1,485 worlds"; a doctor check reports "3 orphaned notes," not "3
  uncharted worlds." An agent or a script has to be able to trust every number and name that
  comes back from a command; the lore never gets to be load-bearing.
- **No quotes from the books, ever.** No cover art, no character names or likenesses, nothing
  that implies affiliation or endorsement. One plain attribution line, stated once per document
  that uses the lore, is the whole of the relationship: "Names are a nod to Peter F. Hamilton's
  Commonwealth novels; this project is not affiliated with him or his publishers."
- **A fan recognizes it; nobody else is confused.** If a sentence needs the reader to have read
  the books to parse it, it has gone too far. Every reader gets the plain meaning from the prose
  alone; a reader of the novels gets a second, quieter layer of recognition on top.

## Glossary

**Names** — in the Commonwealth → here, honestly:

| Commonwealth | Here |
|---|---|
| the unisphere | `unisphere` — the CLI and the network every plugin, engine and companion CLI goes through |
| the gaiafield | `gaiafield` — the knowledge graph engine: wikilinks as deterministic edges (SQLite), plus a report-only inferred layer (offline embeddings) |
| farsight (the Void's psychic long-range sight) | `farsight` — the BM25 search engine: stateless, no index to go stale |
| u-shadows | the cloud routines that keep the unisphere current while you're away: the pipeline, the Signal Radar and the watchdog (`cloud/routines.json`) |
| the Pilgrimage | a capture's journey from `01_Capture/` into the vault proper — distilled, linked, filed (the pipeline) |
| dreams | the Signal Radar's view of what's taking off across your feeds and the vault right now |
| longtalk | the watchdog's notifications — the message that reaches you when something needs attention |
| the Void | the vault: the one place everything flows into |

**Structure** — the shape of the graph itself, for visuals and flavor text only (see "Voice"
above — a command's own output never uses this column):

| In the graph | As space |
|---|---|
| the graph | space |
| a note | a world (a planet) |
| a link | a wormhole |
| a cluster of related notes (a detected community — see `Community-Detection-and-Bridge-Notes`) | a star system |
| a hub note (one many others link to — a high-degree node) | a core world |
| an orphan (a note with no links in or out — what `vault lint`/`doctor` flag) | an uncharted world |
| the vault | the Void |

Each mapping is checked against what the code actually does (`cloud/routines.json`,
`plugins/radar/README.md`, `plugins/obsidian/README.md`, `plugins/obsidian/scripts/vault_lint.py`
and the graph's own community detection) — if the code's behavior changes, these tables change
with it, not the other way around.

## Palette

Kept from the existing design language (`video/src/Explainer.tsx`'s `C`/`GROUP`, reused
verbatim in `docs/cheatsheet/build.py`): the deep-space dark background, the ink/dim neutrals,
the gold "accent" used for the one lit/focused element, and the five group colors
(Concepts/Guides/Tools/field-guide/home-lab-migration/03_Areas). That palette already *was* the
gaiafield-glow-plus-wormhole-ring idea — it just had no brand names on it, no light mode, and the
group colors were only ever used for tiny cheat-sheet dots. New in this pass: the violet→magenta
`wormhole` gradient (now every link/lane and the ring itself), the group colors promoted to full
planet fills with their own light-mode set, and the light ("starlight") column throughout — the
video and cheat sheet only ever needed dark mode.

| Token | Dark | Light | Use |
|---|---|---|---|
| `bg` | `#0a0e1c` | `#f5f6fb` | page / card background |
| `bg2` | `#141a33` | `#e9ebf7` | raised surface |
| `ink` | `#eef1ff` | `#141833` | primary text |
| `dim` | `#8d94b8` | `#4b5178` | secondary text, captions |
| `line` | `#3c4270` | `#c7cbea` | structural lines, a hub world's thin ring |
| `wormhole1` → `wormhole2` | `#9b87ff` → `#ff7ab6` | `#6b46c1` → `#a81f57` | the portal ring, and every wormhole (link/lane) |
| `accent` | `#ffcf5c` | `#d9820a` | the one focus/"you are here" world only — never body text |

Group colors (a world's fill — real `group` values from `video/src/graph.json`, the same field
`gaiafield` writes):

| Group | Dark | Light |
|---|---|---|
| Concepts | `#9b87ff` | `#6b46c1` |
| Guides | `#2fd4c0` | `#0c8a7d` |
| Tools | `#ffb547` | `#b3690a` |
| field-guide / home-lab-migration | `#ff7ab6` | `#a81f57` |
| 03_Areas | `#5fb0ff` | `#2f6fb3` |

Text-contrast check (WCAG relative-luminance formula) against `bg`: dark `ink` 17.1:1, dark `dim`
6.5:1, light `ink` 16.1:1, light `dim` 7.1:1 — every text pairing clears AA (4.5:1) with headroom.
`accent` and the group colors are decorative fills (a world, a ring, a glow), never text, so they
are chosen for clarity against each mode's background rather than the AA text ratio — the light
`accent` (`#d9820a`) was picked specifically to read as a clear, saturated amber rather than the
muddy brown an earlier pass used.

## Typography

No web fonts in shipped SVGs (GitHub strips `<link>`/`@font-face`/`@import` from images served
via `<img src>`) — system stacks only, matching `Explainer.tsx`:

- **Display / wordmark** — `-apple-system, "SF Pro Display", "Helvetica Neue", Helvetica, Arial,
  sans-serif`, bold, slight positive letter-spacing.
- **Readout / labels / taglines** — `ui-monospace, "SF Mono", Menlo, monospace` — the same family
  the CLI's own terminal output uses, so the tagline reads like a status line.
- The cheat sheet's condensed display face (`DIN Condensed` / `Oswald`) is `core/**`/`docs/`
  territory this round and untouched here.

## Visual language

Space is the graph, drawn straight: `assets/build_banner.py` takes `video/src/graph.json`'s own
highlighted focus node (36, Knowledge-Graphs-from-Wikilinks) and expands it deterministically —
its one-hop neighbors in full, then two-hop neighbors in ascending node-id order, capped at 38 —
so the picture is dense enough to read as a graph, not five dots, while staying the exact real
data the explainer video and cheat sheet already use.

- **Worlds.** Every note is a small planet: a radial gradient (a bright highlight, the group's
  real hue, a darkened terminator at the rim) instead of a flat dot, sized by degree. Color comes
  from the note's real `group` field — Concepts violet, Guides teal, Tools amber, the two
  field-guide/home-lab-migration demo folders pink, `03_Areas` blue.
- **Core worlds.** The focus node and the top two or three hubs by degree get a soft atmosphere
  glow behind them. At most one planet — the single highest-degree node in the picture (ties
  broken toward a Tools/engine node, so it lands on Gaiafield) — gets a thin tilted ring, drawn
  behind the planet so the planet itself occludes its middle.
- **Wormholes.** Every link is a lane: a slightly curved path (a small, deterministic,
  per-edge-seeded offset, never a straight ruler line), brighter near the two worlds it joins and
  fading through the middle. The focus node's own lanes get an extra soft glow underneath, and
  three of them carry a small bright transit dot gliding slowly along the path (CSS
  `offset-path`/`offset-distance`, gated by `prefers-reduced-motion` below).
- **Star systems.** A group with three or more worlds in the picture gets a very faint nebula
  haze behind it, centered on its members — a real cluster (the note's own `group`), not a
  decorative blob.
- **The frame.** A starfield (faint, deterministic, never distracting) sits behind everything,
  and one wormhole ring — tilted, double (a crisp line plus a soft blurred haze), violet fading
  to magenta — frames the whole scene as the portal it's viewed through. The graph is laid out
  with one uniform scale centered on the ring's own center, filling roughly two-thirds of the
  ring's inner diameter, with a few deterministic separation passes so no two worlds (or a world
  and the label margin) overlap.

Layering, back to front: starfield, the ring, the nebula haze, the lanes (glow, then the lanes
themselves, then transit dots), the core worlds' atmosphere glow, the ringed hub's own ring,
every planet, the wordmark.

Animation is CSS `@keyframes` only — a slow ring rotation (the outer and inner ring
counter-rotating), a gentle glow pulse on the hubs, and the transit dots' motion path — gated by
`@media (prefers-reduced-motion: reduce)` inside the SVG's own `<style>` block. Every frame is
still a complete, legible still: nothing depends on motion to read correctly, and no planet
textures or sci-fi clip art — the shapes stay restrained enough to read as a knowledge graph
first, a space scene second.

## Do / don't

**Do**
- Use `unisphere`, `gaiafield`, `farsight`, u-shadows, the Pilgrimage, dreams, longtalk and the
  Void as real names, and the structural words (space, world, wormhole, star system, core world,
  uncharted world) in visuals and flavor text, each explained in plain words the first time it
  appears in a document.
- Keep the one attribution line, once per document that uses the lore.
- Keep the palette's dark/light tokens paired — never ship a color from one mode's table against
  the other mode's background.
- Mention "TheVoid" (the real repo/vault name) only where a real path or example needs it, e.g.
  `cloud/routines.json` or a clone URL — the concept, everywhere else, is "the Void."

**Don't**
- No cover art, no quoted passages, no character names or likenesses, no claim or implication of
  affiliation with Peter F. Hamilton or his publishers.
- No lore word, structural or otherwise, standing in for a plain one in a command's data output —
  `graph stats`, `doctor`, exit codes and error text stay in plain, literal English always (see
  "Voice" above).
- No new dated "[earned: …]" incident invented for flavor — that convention marks real history
  elsewhere in this repo; this document doesn't borrow it for atmosphere.
