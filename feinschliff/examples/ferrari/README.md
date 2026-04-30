# Example — Ferrari brand-pack template

Pre-rendered PDF for the Ferrari brand pack, derived from the canonical
[getdesign.md/ferrari](https://getdesign.md/ferrari/design-md) DESIGN.md.
Third reference brand pack in the toolkit (after BMW and Spotify)
demonstrating the **policy-driven** brand-pack architecture — Ferrari
ships its cinematic register, sharp-corner precision, and the Rosso Corsa
livery band by setting tokens + policy blocks, not by editing renderer
code.

## What makes the Ferrari pack visibly Ferrari

- **Cinematic near-black canvas.** `surface-dark = #181818` — slightly warm,
  *never* pure black. The dark canvas IS the page chrome; full-bleed
  cinematic photography is the brand's primary depth treatment.
- **Rosso Corsa is functional-only.** `accent = #DA291C` is reserved for
  primary CTAs, the Cavallino mark, and F1 race-position highlights — used
  scarcely, never decorative. The single-cell race-position highlight in
  the KPI grid is the canonical "one cell out of four in red" pattern.
- **Sharp 0px corners are non-negotiable.** `radius.btn = radius.card = 0` —
  every CTA, card, and band reads as luxury-automotive precision. Same code
  path that renders BMW's sharp rectangles renders Ferrari's; opposite of
  Spotify's pills. Pill geometry (`radius.chip = 9999`) is reserved for the
  badge-pill — the ONE place pill is allowed.
- **Display weight is 500, never bold.** `headline-rule.weight-display =
  medium` — DESIGN.md is explicit: *"Don't bold display copy. The
  cinematic photography does the visual heavy-lifting."* Component titles
  + button labels run 700; everything display runs 500.
- **Negative tracking on display IS a Ferrari signature.** Display sizes
  carry `tracking-em = -0.02` (-1.6px @ 80px display-mega) — the brand's
  editorial signature. BMW says no negative tracking; Ferrari says yes.
- **Single sans family across every text role.** FerrariSans (or Inter at
  weight 500 as the documented open-source substitute). No display/body
  family split, no serif pairing.
- **Livery band as section marker.** A full-width Rosso Corsa accent band
  is the chapter divider — replaces BMW's M-stripe role and Spotify's
  equalizer-marker role. Ships as `add_livery_band` in `chrome.py`.
- **Spec-cell + race-position KPI pattern.** 4-up grid: three cells in
  white, one cell in Rosso Corsa carrying the racing-identity
  highlight. Hairline brightness-step between cells (1px #303030 — same
  hex as canvas-elevated; reads as a tone-step). Zero shadows — depth
  comes from hairlines + brightness-step ONLY (DESIGN.md elevation table).
- **UPPERCASE 1.4px-tracked button labels, no chevron terminator.**
  `chip-rule.tracking-em = 0.1` applied across every CTA. Buttons end at
  the last letter — DESIGN.md is explicit, no `›` or `→` terminator.

## Use

Open `Ferrari-Template.pdf` in any browser or PDF reader to browse the
layouts before authoring. To run `/deck` against the Ferrari brand:

```bash
FEINSCHLIFF_BRAND=ferrari /deck "your brief..."
```

## Source

- **Brand spec:** [getdesign.md/ferrari](https://getdesign.md/ferrari/design-md) — vendored verbatim via the npm `getdesign` package.
- **Tokens + policy:** [`feinschliff/brands/ferrari/tokens.json`](../../brands/ferrari/tokens.json) — DTCG colors, type, radius, plus seven Ferrari-specific policy blocks (`layout`, `cover`, `section-marker`, `photography`, `headline-rule`, `chip-rule`, `shadow`).
- **Renderer:** [`feinschliff/brands/ferrari/renderers/pptx/`](../../brands/ferrari/renderers/pptx/) — same engine as BMW/Spotify, with Ferrari-bespoke `chrome.py` (livery band, UPPERCASE link, hairline divider, heraldic-shield glyph), sharp-corner `controls.py`, and rebuilt cover/chapter/KPI/quote/end layouts.
- **Glyph:** the chrome glyph is a generic heraldic-shield silhouette in Modena yellow with a Rosso Corsa hairline border — an abstract stand-in. The licensed Cavallino Rampante (prancing horse) is intentionally not reproduced. Wordmark is "FERRARI" UPPERCASE per the brand's classical lockup register.
- **No HTML reference deck.** Ferrari was authored from the public DESIGN.md spec without a Ferrari-Design HTML showcase, so `/compile` is not wired up for this brand. `/deck` works against the python-pptx layouts directly.

## Regenerating

```bash
cd feinschliff/brands/ferrari/renderers/pptx
uv sync
uv run python build.py
soffice --headless --convert-to pdf --outdir ../../../../examples/ferrari out/Ferrari-Template.pptx
```
