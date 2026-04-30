# Example — Spotify brand-pack template

Pre-rendered PDF for the Spotify brand pack, derived from the canonical
[getdesign.md/spotify](https://getdesign.md/spotify/design-md) DESIGN.md.
Second reference brand pack in the toolkit (after BMW) demonstrating
the **policy-driven** brand-pack architecture — Spotify ships pill
geometry, heavy shadows, and album-art card patterns by setting tokens,
not by editing renderer code.

## What makes the Spotify pack visibly Spotify

- **Pill-and-circle geometry.** `radius.btn = radius.chip = 9999` — every
  button and chip is a fully-rounded pill. `radius.card = 8` — album-art
  rounded corner. The same `add_rounded_rect` primitive that renders BMW's
  sharp 0px corners renders Spotify's pills, just by reading a different
  token slot.
- **Spotify Green is functional-only.** Reserved for play CTAs, active
  states, and chapter markers. Never a decorative fill (the spec is
  explicit: *"Don't use Spotify Green decoratively or on backgrounds"*).
- **Heavy shadows on elevated surfaces.** Cards carry the canonical
  `rgba(0,0,0,0.3) 0px 8px 8px` elevation shadow per DESIGN.md §6 —
  required on the dark canvas because subtle shadows are invisible.
  Implemented via the new `shadow="elevated"` parameter on `add_rounded_rect`.
- **Equalizer-bar section marker.** Three-to-four green pill bars of
  varying height — the Spotify analog of BMW's M-stripe, marking chapter
  dividers and major editorial breaks.
- **Bold/regular weight binary.** 700 for emphasis, 400 for body.
  Weight 500 used sparingly. The 700/400 contrast IS the typographic
  hierarchy.
- **UPPERCASE 1.4px-tracked button labels.** `chip-rule.tracking-em = 0.1`
  applied across every pill button and chip — Spotify's iconic
  systematic-label voice.
- **Album-art shelf cover.** The hero cover layout is a 5×2 rounded
  album-art tile shelf with gradient fade into the canvas, lowercase
  hero headline, and a Spotify Green pill PLAY CTA at lower-left —
  the Spotify app's home screen translated to deck.
- **Near-black canvas.** `surface-dark = #121212` (Base / Level 0)
  carries the entire deck. Cards step up to `paper = #181818`
  (Surface / Level 1). Mid Card `paper-2 = #252525` for emphasized
  surfaces.

## Use

Open `Spotify-Template.pdf` in any browser or PDF reader to browse the
layouts before authoring. To run `/deck` against the Spotify brand:

```bash
FEINSCHLIFF_BRAND=spotify /deck "your brief..."
```

## Source

- **Brand spec:** [getdesign.md/spotify](https://getdesign.md/spotify/design-md) — vendored verbatim via the npm `getdesign` package.
- **Tokens + policy:** [`feinschliff/brands/spotify/tokens.json`](../../brands/spotify/tokens.json) — DTCG colors, type, radius, plus six Spotify-specific policy blocks (`layout`, `cover`, `section-marker`, `photography`, `headline-rule`, `chip-rule`, `shadow`).
- **Renderer:** [`feinschliff/brands/spotify/renderers/pptx/`](../../brands/spotify/renderers/pptx/) — same engine as BMW/Claude, with Spotify-bespoke `chrome.py` (equalizer marker, pill chevron-link, lowercase wordmark), pill `controls.py`, rounded `cards.py`, and rebuilt cover/chapter/KPI/quote/end layouts.
- **Glyph:** chrome glyph is generic three-bar equalizer geometry — an abstract stand-in for the Spotify sound-wave mark, not the licensed logo. Wordmark is "spotify" lowercase per Spotify's wordmark register.
- **No HTML reference deck.** Spotify was authored from the public DESIGN.md spec without a Spotify-Design HTML showcase, so `/compile` is not wired up for this brand. `/deck` works against the python-pptx layouts directly.

## Regenerating

```bash
cd feinschliff/brands/spotify/renderers/pptx
uv sync
uv run python build.py
soffice --headless --convert-to pdf --outdir ../../../../examples/spotify out/Spotify-Template.pptx
```
