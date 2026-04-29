# Feinschliff PPTX renderer

Emits `out/Feinschliff-Template.pptx` — a real PowerPoint template with named
`SlideLayout`s, editable typed placeholders, and brand chrome. Users open it
in PowerPoint → `Insert → New Slide` shows each Feinschliff layout with
fillable prompts.

## Run

```
cd feinschliff/brands/feinschliff/renderers/pptx
uv sync
uv run python build.py
```

Output: `out/Feinschliff-Template.pptx`.

## Architecture

Four-layer package — mirrors the svg renderer's structure; same mental model for both substrates.

| File / folder | Role |
|---|---|
| `theme.py` | Projects `brands/feinschliff/tokens.json` into `HEX`, `SIZE_PX`, `FONT_DISPLAY`, `FONT_MONO`, `WEIGHT` (plus `RGBColor` module constants for direct python-pptx use). Import-time load. |
| `geometry.py` | CSS px ⇄ EMU ⇄ pt conversion. Critical ratio: 1 CSS px = 1/144 inch; pt = px × 0.5 (not the standard 0.75, which assumes 96 DPI and is wrong for the 1920 × 1080 / 13.333″ × 7.5″ canvas). |
| `master.py` | Slide size, theme/font injection, layout cloning, master/layout reset. Only module that touches raw OOXML. |
| `components/` | Pure-function primitives and composites: `primitives.py` (rect, text, line), `type.py`, `chrome.py` (logo, pgmeta, footer, slide-number field), `controls.py` (button, chip), `data.py` (KPI, bar row), `media.py` (image frame with diagonal stripe fill), `cards.py`, `placeholders.py`. One module per atom category — a new component ≈ adding a file here. |
| `layouts/` | One module per named SlideLayout. Each exposes `NAME` and `build(layout)`. `_shared.py` holds helpers used by 2+ layouts. `__init__.py` is the ordered registry. |
| `slides.py` | Demo deck — fills each layout with representative content via `add(prs, layout_name, _0="title", …)`. Preserves paragraph structure when substituting prompt text. |
| `build.py` | Orchestrator: `set_slide_size → apply_feinschliff_theme → ensure_n_layouts → reset_master_shapes → layouts.build_all → slides.build_demo_deck → save`. |
| `out/Feinschliff-Template.pptx` | Output artifact — diff review catches visual regressions. |

## Contract

- **Reads:** `brands/feinschliff/tokens.json` (via `theme.py`) and `assets/` (logo PNGs embedded in chrome).
- **Writes:** `out/Feinschliff-Template.pptx`. Reproducible — `uv run python build.py` regenerates it deterministically from source.
- **Deps:** `python-pptx` + `lxml` + `Pillow`. Locked in `uv.lock`.
- **No imports from other renderers.**

## Conventions

1. **Chrome on each layout, not the master.** So dark and light variants can differ cleanly. Slide-number is a live `<a:fld type="slidenum">` field.
2. **Text placeholders use explicit pPr reset** (`marL="0" indent="0"` + `<a:buNone/>`). Without this, placeholders inherit the master's default body-style bullet and indent.
3. **Uppercase labels use `<a:rPr cap="all"/>`**, not `.upper()` on `<a:t>`. The `cap` attribute applies at render time, so user-typed replacements stay uppercased without the user doing anything.
4. **Picture frames are fixed rects with `pattFill prst="wdDnDiag"`, not picture placeholders.** LibreOffice and some PowerPoint versions z-order picture placeholders above fixed shapes regardless of document order — chrome would disappear. Users replace the image via right-click → Format Shape → Fill → Picture. The striped rect reads as "image goes here" without relying on placeholder semantics.
5. **Multi-run text hierarchy** (e.g. KPI "62" + "k" at different sizes) uses a fixed text shape with manually-emitted runs rather than a placeholder. Placeholders only copy the first run's `rPr`; a fixed shape preserves the hierarchy visually at the cost of placeholder editability.

## Extending

Adding a new named layout:

1. Create `layouts/<id>.py` exposing `NAME` + `build(layout)`. Use `components/` primitives — don't hand-write OOXML.
2. Register the module in `layouts/__init__.py`.
3. Add a catalog entry in `brands/feinschliff/catalog/layouts.json` with `id`, `name`, `role`, `concepts`, `when_to_use`, `when_not_to_use`, slot schema, and renderer.pptx `{module, layout_name, placeholder_map}`.
4. Add a demo slide in `slides.py`.
5. Run `uv run python build.py` and open the output; verify the new layout appears under Insert → New Slide.

See `feinschliff/skills/extend/SKILL.md` for the "screenshot → new component" flow.
