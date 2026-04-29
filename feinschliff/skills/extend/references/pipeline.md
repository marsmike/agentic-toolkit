# /extend Pipeline

Operates on the active brand pack at `<brand-root>/` (see `../SKILL.md` for how `<brand-root>` resolves; defaults to `brands/feinschliff/`).

Adds a new component + layout to the active brand's Baukasten, regenerating the catalog. Screenshot-driven additive workflow — no existing code modified.

## Step 1 — Analyse

LLM inspects the screenshot + description. Identifies:
- **Name**: e.g. `timeline`.
- **Visual atoms**: dots, lines, labels, dates.
- **Content shape (props)**: `{items: [{date, label, active: bool}]}` for a timeline.
- **Position hints**: where the component sits in the 1920×1080 canvas (centred? full-width? left half?).

Emits a proposed plan (text summary) for user confirmation. If user rejects, iterate on the plan.

## Step 2 — Generate component

Create `<brand-root>/renderers/pptx/components/<name>.py` with a pure `add_<name>(target, x, y, w, h, **props)` function. Component-authoring reference (paths relative to the active brand pack):

- `<brand-root>/renderers/pptx/theme.py` — brand tokens (`T.ACCENT`, `T.GRAPHITE`, `T.FONT_DISPLAY`, `T.FONT_MONO`, `T.SIZE_PX`, `T.HEX`). Token names are neutral semantic — value differs per brand pack.
- `<brand-root>/renderers/pptx/geometry.py` — `px()`, `pt_from_px()`. All positions are expressed in 1920×1080 pixels.
- `<brand-root>/renderers/pptx/components/primitives.py` — `add_rect`, `add_line`, `_shapes(target)` (wraps Slide/Layout/Master so one component works on all three).
- `<brand-root>/renderers/pptx/components/type.py` — `add_text`, typography helpers.
- `<brand-root>/renderers/pptx/components/placeholders.py` — `add_text_placeholder`, `add_picture_placeholder`.

Protocol:
- `target` accepts Slide, SlideLayout, or SlideMaster. Use `_shapes(target)` for shape insertion.
- Use only `theme` + `geometry` + lower-level `components/*` modules — no reaching into other layouts.
- Pure; no side effects outside the passed target.
- Sharp-cornered, brand-typography-compliant (the active brand's tokens drive the typography).

Add re-export to `<brand-root>/renderers/pptx/components/__init__.py`.

## Step 3 — Generate layout

Create `<brand-root>/renderers/pptx/layouts/<name>.py` with `NAME` + `build(layout)`. Use the active pack's `<brand-root>/renderers/pptx/layouts/kpi_grid.py` as the canonical pattern:
- Calls `set_layout_name`, `set_layout_background`, `paint_chrome`.
- Calls `content_header(layout, eyebrow=..., title=...)` from `layouts/_shared.py` if the layout has a header.
- Calls `add_<name>(...)` for the main content area.
- Emits `add_text_placeholder` calls for every editable field. Reserved placeholder indices:
  - `0` — title
  - `10` — eyebrow
  - `11`, `12` — body slots
  - `20`+ — layout-specific (KPIs, columns, chapters, etc.). Pick a free range; don't collide with existing layouts that reuse idx numbers.

Register in `<brand-root>/renderers/pptx/layouts/__init__.py::LAYOUTS` (append only).

## Step 4 — Add catalog entry

Append to `<brand-root>/catalog/layouts.json`:
```json
{
  "id": "<name>",
  "name": "<Brand> · <Pretty Name>",
  "role": "<best-match role from existing catalog>",
  "concepts": [<inferred from description>],
  "when_to_use": "<from LLM analysis>",
  "when_not_to_use": "<from LLM analysis>",
  "slots": <schema inferred from component props>,
  "renderer": {
    "pptx": {
      "module": "feinschliff.<brand-module-prefix>.renderers.pptx.layouts.<name>",
      "layout_name": "<Brand> · <Pretty Name>",
      "placeholder_map": {...}
    }
  }
}
```

The `<brand-module-prefix>` is `brands.<slug>` for packs under `brands/` (e.g. `brands.feinschliff`). The `<Brand>` token is the brand's display label (e.g. `Feinschliff`).

`placeholder_map` must cover every `slots` field the user can fill. If a slot isn't wired to a placeholder, either add the placeholder in step 3 or drop the slot.

## Step 5 — Append demo slide

Append a new `add(prs, ...)` call to `build_demo_deck()` in `<brand-root>/renderers/pptx/slides.py`. Use `_<idx>=...` kwargs to fill each placeholder. Model after existing entries (e.g. the `<Brand> · KPI Grid` demo). Order-sensitive: append at the end so existing slide numbering stays stable.

## Step 6 — Update tests

Adding a layout breaks three hard-coded assertions. Bump all three:

- `tests/test_catalog_schema.py::test_has_16_layouts` → **17** (or whatever the new count is).
- `tests/test_baukasten_builds.py::EXPECTED_NAMES` — append the new `NAME` string.
- `tests/test_baukasten_builds.py::test_template_demo_slides` — expected slide count (currently `16`) → new count.

(Test counts are pack-specific; check the active pack's tests for the current values.)

## Step 7 — Build + verify

```bash
cd <brand-root>/renderers/pptx && uv run python build.py
cd ../../.. && uv run --project <brand-root>/renderers/pptx pytest tests/
```

Both must pass before visual verification.

## Step 8 — Visual verification

Render the new layout slide to PNG and compare with the screenshot:

```bash
# Needs LibreOffice installed. Emits one PNG per slide to /tmp/.
soffice --headless --convert-to png --outdir /tmp <brand-root>/renderers/pptx/out/<Brand>-Template.pptx
```

LLM eyeballs the relevant PNG against the reference screenshot. Iterate up to 3× per `../deck/references/iteration-loop.md`.

If the match is acceptable, commit component + layout + catalog entry + demo slide + test updates.

## Design principle: additive, not intrusive

This skill NEVER modifies existing `components/*.py` or `layouts/*.py`. New file, new catalog entry, new demo slide, test count bumps — that's all. Appends to `components/__init__.py`, `layouts/__init__.py::LAYOUTS`, `layouts.json`, `slides.py::build_demo_deck` must all be append-only; never reorder or mutate existing entries. If the new component looks near-identical to an existing one, prefer tuning the existing one instead (outside this skill's scope).
