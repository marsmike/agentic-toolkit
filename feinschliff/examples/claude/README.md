# Example — Claude brand-pack template

Pre-rendered PDF for the Claude brand pack — coral primary, warm cream canvas, dark navy product surfaces, serif/sans editorial pairing.

## Use

Same as the Feinschliff preview: open `Claude-Template.pdf` in any browser or PDF reader to browse the layouts before authoring. To run `/deck` against the Claude brand:

```bash
FEINSCHLIFF_BRAND=claude /deck "your brief..."
```

## Source

- Tokens: [`feinschliff/brands/claude/tokens.json`](../../brands/claude/tokens.json) — derived from [getdesign.md/claude/design-md](https://getdesign.md/claude/design-md).
- Renderer: [`feinschliff/brands/claude/renderers/pptx/`](../../brands/claude/renderers/pptx/) — same shape as the Feinschliff renderer; only the brand-scoped chrome (wordmark, spike-mark glyph, pgmeta defaults) and tokens differ.
- No HTML reference deck. Claude was authored from the public DESIGN.md spec without a Claude-Design HTML showcase, so `/compile` is not wired up for this brand. `/deck` works against the python-pptx layouts directly.

## Regenerating

```bash
cd feinschliff/brands/claude/renderers/pptx
uv sync
uv run python build.py
# out/Claude-Template.pptx is the editable source.
soffice --headless --convert-to pdf --outdir ../../../../examples/claude out/Claude-Template.pptx
```
