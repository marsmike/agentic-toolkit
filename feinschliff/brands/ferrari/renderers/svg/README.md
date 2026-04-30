# Feinschliff SVG renderer

Emits Feinschliff-branded SVG files at 1920×1080 (CSS px) for use in web
embeds, status pages, dashboards — any substrate where `.pptx` is the
wrong fit.

## Run

```
cd feinschliff/brands/feinschliff/renderers/svg
python build.py
```

Output: `out/<id>.svg`, one file per registered layout. Open any file in a
browser to view — the SVGs are self-contained (no external assets, no
third-party fonts beyond the Noto Sans stack already assumed by the rest
of the design system).

## Architecture

Mirrors the PPTX renderer's layer structure (see
`feinschliff/brands/feinschliff/renderers/pptx/`):

| File | Role |
|------|------|
| `theme.py`      | Projects `brands/feinschliff/tokens.json` into a dict of hex strings (`HEX`), a px-size scale (`SIZE_PX`), font family strings, and a weight dict. Import-time load, no runtime token hunting. |
| `geometry.py`   | 1920 × 1080 canvas constants + named anchors (logo, pgmeta, footer). No pt/EMU conversion — SVG uses CSS px natively. |
| `primitives.py` | Low-level builders: `svg_root`, `rect`, `line`, `text`, `group`. Thin wrappers over `xml.etree.ElementTree`. |
| `components.py` | Higher-level Feinschliff pieces: `rule`, `eyebrow`, `title`, `body`, `kpi_value_unit`, `kpi_key`, `kpi_delta`, `column_label_stack`, `canvas_background`. |
| `layouts/_shared.py` | Shared chrome (inline-SVG wordmark + pgmeta + footer + slide-num) and `content_header` rule/eyebrow/title stack. |
| `layouts/<id>.py`    | One module per layout — exposes `NAME`, `ID`, `build(root)`. |
| `layouts/__init__.py`| Registry: ordered list of layout modules. |
| `build.py`           | Orchestrator — renders every registered layout to `out/<ID>.svg`. |

## Contract

- **Reads:** `brands/feinschliff/tokens.json` (via `theme.py`). Layout metadata
  in `brands/feinschliff/catalog/layouts.json` is not imported today but is
  the source of truth for slot contracts — layout demo content mirrors
  what's in the catalog.
- **Writes:** one `.svg` per registered layout into `out/`. Files are
  committed to the repo so diff review catches visual regressions.
- **Deps:** stdlib only. No third-party runtime deps — SVG is XML and
  `xml.etree.ElementTree` handles it.
- **No imports from other renderers.**

## Conventions

1. `viewBox="0 0 1920 1080"` on every output; `width`/`height` set to the
   canvas extents so the SVG has a default displayed size but still scales
   cleanly in any container via CSS.
2. Coordinates are CSS px, identical to the HTML reference and the PPTX
   renderer — only the output substrate differs.
3. Font sizes are px (`SIZE_PX[...]`), not pt.
4. SVGs are **static renders** of a filled layout, not editable templates.
   Placeholder copy lives as literal `<text>` — there is no slot-injection
   pass on the consumer side today.
5. Chrome (wordmark + pgmeta + footer + slide-num) is drawn per-layout in
   `_shared.paint_chrome()`. Mirrors the PPTX pattern.

## Current coverage (proof-of-concept)

- `title_orange` — accent-bg title slide with big Noto Sans Light display.
- `kpi_grid` — 3-cell KPI row with value/unit runs, hairline grid, keys + deltas.
- `two_column_cards` — two paper cards, accent-numbered columns.

The remaining catalog layouts (`title-ink`, `title-picture`, `agenda`,
`chapter-orange`, `chapter-ink`, `three-column`, `four-column-cards`,
`text-picture`, `full-bleed-cover`, `bar-chart`, `components-showcase`,
`quote`, `end`) are deferred to a later PR — adding them is a mechanical
fill-out now that the foundation is in place.

## Deferred

- **Remaining layouts** (listed above). Each is ≈ 40–70 lines of Python
  plus one committed `out/<id>.svg` artifact. Foundation (`theme.py`,
  `primitives.py`, `components.py`, `_shared.paint_chrome`) already
  handles all of them — no new machinery needed.
- **`components.tsx`** — a React-components sibling of this folder so
  embeddings in web apps (status dashboards, docs sites) can import
  `KPICard`, `SlideFrame`, etc. as JSX rather than dropping in raw SVG.
  Deferring until a live web project drives the need.

See `feinschliff/README.md` → "Deferred work" for the plugin-wide roadmap.
