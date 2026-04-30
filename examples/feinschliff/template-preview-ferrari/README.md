# Example — Ferrari brand-pack template

Pre-rendered PDF for the Ferrari brand pack — Rosso Corsa accent, Modena yellow shield highlight, cinematic black canvas, classical serif/sans editorial pairing.

## Use

Same as the Feinschliff preview: open `Ferrari-Template.pdf` in any browser or PDF reader to browse the layouts before authoring. To run `/deck` against the Ferrari brand:

```bash
FEINSCHLIFF_BRAND=ferrari /deck "your brief..."
```

## Source

- Tokens: [`feinschliff/brands/ferrari/tokens.json`](../../../feinschliff/brands/ferrari/tokens.json) — derived from [getdesign.md/ferrari/design-md](https://getdesign.md/ferrari/design-md).
- Renderer: [`feinschliff/brands/ferrari/renderers/pptx/`](../../../feinschliff/brands/ferrari/renderers/pptx/) — same shape as the Feinschliff renderer; only the brand-scoped chrome (heraldic-shield glyph, FERRARI wordmark, pgmeta defaults) and tokens differ.
- No HTML reference deck. Ferrari was authored from the public DESIGN.md spec without a Ferrari-Design HTML showcase, so `/compile` is not wired up for this brand. `/deck` works against the python-pptx layouts directly.
- The shield glyph is a generic heraldic abstraction (rounded-top rectangle tapering to a V) — the licensed Cavallino Rampante (prancing horse) is intentionally not reproduced.

## Regenerating

```bash
cd feinschliff/brands/ferrari/renderers/pptx
uv sync
uv run python build.py
# out/Ferrari-Template.pptx is the editable source.
soffice --headless --convert-to pdf --outdir ../../../../../examples/feinschliff/template-preview-ferrari out/Ferrari-Template.pptx
```
