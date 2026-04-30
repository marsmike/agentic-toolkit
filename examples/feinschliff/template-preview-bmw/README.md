# Example — BMW brand-pack template

Pre-rendered PDF for the BMW brand pack, derived from the canonical
[BMW DESIGN.md](https://getdesign.md/bmw/design-md). This is the first
brand pack in the toolkit that goes beyond a token swap — it ships
explicit **policy blocks** (`cover`, `section-marker`, `photography`,
`headline-rule`, `chip-rule`) alongside the DTCG tokens, so layouts
can switch on brand idioms instead of just colors.

## What makes the BMW pack visibly BMW

- **Light canvas + dark navy hero band rhythm.** White (`paper` `#FFFFFF`)
  is the dominant page surface; surface-dark navy (`#1A2129`) appears as
  a treatment, never as the base. Page rhythm relies on light → dark →
  light alternation.
- **700 / 300 weight ladder.** Display headlines run BMW Type Next 700;
  body runs Light 300. Weight 500 is intentionally absent — the
  high-contrast pairing is the editorial signature.
- **Tracking 0 on all display.** No Apple-style negative letter-spacing
  — BMW Type Next reads on a wide body, tightening it would read
  off-brand. Eyebrows + chevron links use 1.5px / 0.115em tracking
  UPPERCASE (`label-uppercase` voice).
- **Rectangular IS the brand.** Every CTA, card, and input renders at
  `radius: 0px`. Pill / circular only for icon buttons.
- **BMW Blue is action-only.** `#1C69D4` carries every primary CTA;
  it never paints a hero fill or decorative band. Hero contrast comes
  from light/dark pairing, not from accent fills.
- **M-stripe (4px tricolor).** `m-blue-light → m-blue-dark → m-red`
  marks chapter dividers and the dark-band cover edge. Reserved for
  major editorial breaks — not decoration.
- **Spec-cell KPIs.** The KPI grid follows BMW DESIGN.md `spec-cell`:
  large 88px / 700 value, tracked-uppercase label below, BMW Blue
  delta. Hairline dividers separate cells; no shadows ever (depth
  comes from color-block contrast).
- **`LEARN MORE ›` chevron links.** UPPERCASE 13px / 700 / 1.5px tracked
  inline CTAs terminated with a `›` chevron — the iconic BMW corporate
  inline-CTA voice.

## Use

Open `BMW-Template.pdf` in any browser or PDF reader to browse the
layouts before authoring. To run `/deck` against the BMW brand:

```bash
FEINSCHLIFF_BRAND=bmw /deck "your brief..."
```

## Source

- **Brand spec:** [getdesign.md/bmw/design-md](https://getdesign.md/bmw/design-md) — canonical DESIGN.md (also vendored as the npm package `getdesign`).
- **Tokens + policy:** [`feinschliff/brands/bmw/tokens.json`](../../../feinschliff/brands/bmw/tokens.json) — DTCG colors, type, and the BMW-specific policy blocks (`layout`, `cover`, `section-marker`, `photography`, `headline-rule`, `chip-rule`).
- **Renderer:** [`feinschliff/brands/bmw/renderers/pptx/`](../../../feinschliff/brands/bmw/renderers/pptx/) — same rendering engine as Claude/Feinschliff, with BMW-bespoke `chrome.py` (M-stripe, chevron link, hairline, quartered-disc glyph), `type.py` (700 display + 300 body, tracking 0, label-uppercase eyebrows), and rebuilt cover + chapter + KPI layouts.
- **Glyph:** the chrome glyph is generic 4-quadrant pie geometry — an abstract stand-in for the BMW roundel, not the licensed brand asset. Wordmark is the literal three-letter "BMW" in display sans 700.
- **No HTML reference deck.** BMW was authored from the public DESIGN.md spec without a BMW-Design HTML showcase, so `/compile` is not wired up for this brand. `/deck` works against the python-pptx layouts directly.

## Regenerating

```bash
cd feinschliff/brands/bmw/renderers/pptx
uv sync
uv run python build.py
# out/BMW-Template.pptx is the editable source.
soffice --headless --convert-to pdf --outdir ../../../../../examples/feinschliff/template-preview-bmw out/BMW-Template.pptx
```
