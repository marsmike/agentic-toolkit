# Example — Spotify brand-pack template

Pre-rendered PDF for the Spotify brand pack — vibrant green accent, deep-black canvas, bold geometric sans, album-art-driven dark immersive surface.

## Use

Same as the Feinschliff preview: open `Spotify-Template.pdf` in any browser or PDF reader to browse the layouts before authoring. To run `/deck` against the Spotify brand:

```bash
FEINSCHLIFF_BRAND=spotify /deck "your brief..."
```

## Source

- Tokens: [`feinschliff/brands/spotify/tokens.json`](../../../feinschliff/brands/spotify/tokens.json) — derived from [getdesign.md/spotify/design-md](https://getdesign.md/spotify/design-md). Not an official Spotify design system.
- Renderer: [`feinschliff/brands/spotify/renderers/pptx/`](../../../feinschliff/brands/spotify/renderers/pptx/) — same shape as the Feinschliff renderer; only the brand-scoped chrome (wordmark, equalizer glyph, pgmeta defaults) and tokens differ.
- No HTML reference deck. Spotify was authored from the public DESIGN.md spec without a Spotify-Design HTML showcase, so `/compile` is not wired up for this brand. `/deck` works against the python-pptx layouts directly.

## Regenerating

```bash
cd feinschliff/brands/spotify/renderers/pptx
uv sync
uv run python build.py
# out/Spotify-Template.pptx is the editable source.
soffice --headless --convert-to pdf --outdir ../../../../../examples/feinschliff/template-preview-spotify out/Spotify-Template.pptx
```
