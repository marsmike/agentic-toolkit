# Example — Binance brand-pack template

Pre-rendered PDF for the Binance brand pack — Binance Yellow accent on a deep crypto-black canvas, IBM Plex Sans body, tabular numerics, trading-floor urgency.

## Use

Same as the Feinschliff preview: open `Binance-Template.pdf` in any browser or PDF reader to browse the layouts before authoring. To run `/deck` against the Binance brand:

```bash
FEINSCHLIFF_BRAND=binance /deck "your brief..."
```

## Source

- Tokens: [`feinschliff/brands/binance/tokens.json`](../../../feinschliff/brands/binance/tokens.json) — derived from [getdesign.md/binance/design-md](https://getdesign.md/binance/design-md).
- Renderer: [`feinschliff/brands/binance/renderers/pptx/`](../../../feinschliff/brands/binance/renderers/pptx/) — same shape as the Feinschliff renderer; only the brand-scoped chrome (wordmark, diamond glyph, pgmeta defaults) and tokens differ.
- No HTML reference deck. Binance was authored from the public DESIGN.md spec without a Binance-Design HTML showcase, so `/compile` is not wired up for this brand. `/deck` works against the python-pptx layouts directly.

## Regenerating

```bash
cd feinschliff/brands/binance/renderers/pptx
uv sync
uv run python build.py
# out/Binance-Template.pptx is the editable source.
soffice --headless --convert-to pdf --outdir ../../../../../examples/feinschliff/template-preview-binance out/Binance-Template.pptx
```
