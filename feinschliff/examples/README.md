# Examples — Feinschliff

Real-world examples for the `feinschliff` plugin. Each subdirectory
pairs an **input** (a brief, a DESIGN.md, a screenshot) with the
**output** the plugin produced (a `.pdf`, a rendered PNG, a generated
layout). Use these as starting points for your own work.

## Teaser

[`teaser.mp4`](teaser.mp4) — 60-second video showing one brief rendered
across all five elevated brand packs (Feinschliff · BMW · Spotify ·
Ferrari · Binance). 1920×1080 @ 30fps, no music, type-led — auto-plays
silently in social feeds. Made with Claude Code + Remotion.

## Brand-pack previews

Pre-rendered PDFs for every brand pack the plugin ships. PDFs render
inline on GitHub — click into a folder, then click the `.pdf` to view.

| Brand | Identity | Folder |
|---|---|---|
| **Feinschliff** | Eponymous pack — gold + navy, Bauhaus restraint | [`feinschliff/`](feinschliff/) |
| **Claude** | Coral + cream, editorial serif (Anthropic's Claude surface) | [`claude/`](claude/) |
| **Spotify** | Spotify-green accent on near-black, pill-and-circle geometry | [`spotify/`](spotify/) |
| **Binance** | Binance-yellow on crypto-black, IBM Plex tabular | [`binance/`](binance/) |
| **BMW** | Corporate blue on pure white, two-weight ladder, hairline rules | [`bmw/`](bmw/) |
| **Ferrari** | Rosso Corsa + Modena yellow on cinematic black, classical serif | [`ferrari/`](ferrari/) |

Each brand folder ships:

- `{Brand}-Template.pdf` — pre-rendered preview (≈1 MB, 34 slides).
- `README.md` — palette, typography, glyph abstraction, regenerate recipe.

Four reference packs (**BMW**, **Spotify**, **Ferrari**, **Binance**)
ship full brand-policy blocks alongside DTCG tokens — see their
READMEs for the policy schema and the design decisions that go beyond
colors and fonts. Each demonstrates the architecture in a different
register: BMW (light canvas + sharp rectangles + 700/300 ladder),
Spotify (dark + pills + heavy shadows + 700/400 binary), Ferrari
(cinematic dark + 0px corners + sans 500 display), Binance
(crypto-black + 6/12px radius + 600/700 display + markets-ticker
chrome).

## Plugin-command examples

| Example | What's inside | Plugin command |
|---|---|---|
| [`brief-to-deck/`](brief-to-deck/) | One-paragraph brief → 8-slide branded deck | `/deck "..."` |
| [`design-md-to-tokens/`](design-md-to-tokens/) | A DESIGN.md + the brand pack it expanded into (v0.2 preview) | `/compile` |

## Contributing examples

Examples are PR-friendly — open one with:

1. A new subdirectory in this folder.
2. A short `README.md` explaining what's demonstrated.
3. The input (brief / DESIGN.md / screenshot) committed.
4. The output the plugin produced (`.pdf`, PNG, etc.) committed if useful for visual reference.

Match the existing format. Keep examples small, self-contained, and shippable as MIT (no real customer logos or trademarked brands beyond what NOTICE already covers).
