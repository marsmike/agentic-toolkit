# /compile Pipeline

Operates on the active brand pack at `<brand-root>/`. See `../SKILL.md` for how `<brand-root>` is resolved (defaults to `brands/feinschliff/`). All path placeholders below are relative to `feinschliff/`.

Parses `<brand-root>/claude-design/<brand>-2026.html` and regenerates `<brand-root>/catalog/layouts.json` + per-layout `.py` in `<brand-root>/renderers/pptx/layouts/`.

## Drift check

Before the full apply pipeline runs, verify HTML and catalog agree on which layouts exist:

```bash
cd <brand-root>/renderers/pptx && uv run python compile.py --check
```

Example resolution (default `FEINSCHLIFF_BRAND=feinschliff`):

```bash
cd brands/feinschliff/renderers/pptx && uv run python compile.py --check
```

This is a standalone script — runs without Claude — and is also the CI gate (`tests/test_compile_drift.py`). It classifies every HTML section as `layout` / `visual-ref` / `UNKNOWN` and every catalog entry as `html-backed` / `code-first`. Non-zero exit = drift.

Keep the label↔id map and visual-ref list in `<brand-root>/renderers/pptx/compile.py` in sync when adding a new layout or renaming one.

## Pre-requisite: HTML must meet the contract

The HTML MUST carry the full `data-*` annotation per `../../../references/claude-design-prompt.md`. If `<brand>-2026.html` only has `data-label` (no `data-role`, `data-concepts`, `data-when-to-use`, `data-when-not-to-use`, `data-slots`), **regenerate it via the prompt before running the apply pipeline**.

## Input contract

Every `<section class="slide">` MUST be annotated with six `data-*` attributes:
- `data-label`
- `data-role`
- `data-concepts`
- `data-when-to-use`
- `data-when-not-to-use`
- `data-slots` (JSON)

## Step 1 — Parse + validate

Read `<brand-root>/claude-design/<brand>-2026.html`. For each `<section class="slide">`:
- Assert all six `data-*` attrs present. On missing attr, emit a clear error:
  ```
  ERROR: slide #5 (data-label="Chapter Ink") is missing data-when-not-to-use.
  Add this attribute to the HTML before re-running.
  ```
- Parse `data-slots` as JSON — fail on invalid JSON.
- Parse `data-concepts` as comma-separated list.

## Step 2 — Emit catalog/layouts.json

For each slide, emit an entry in `<brand-root>/catalog/layouts.json`:
```json
{
  "id": "<slug of data-label>",
  "name": "<Brand> · <data-label>",
  "role": "<data-role>",
  "concepts": [<split of data-concepts>],
  "when_to_use": "<data-when-to-use>",
  "when_not_to_use": "<data-when-not-to-use>",
  "slots": <data-slots parsed>,
  "renderer": {
    "pptx": {
      "module": "feinschliff.<brand-module-prefix>.renderers.pptx.layouts.<id>",
      "layout_name": "<Brand> · <data-label>",
      "placeholder_map": {... inferred from slot names ...}
    }
  }
}
```

The `<brand-module-prefix>` is `brands.<slug>` for packs under `brands/` (e.g. `brands.feinschliff`). The `<Brand>` token in `name` and `layout_name` is the brand's display label (e.g. `Feinschliff`).

Preserve existing `renderer.pptx.placeholder_map` values if they already exist for this `id` (humans may have hand-tuned them). Auto-generate from slot names only when creating a new entry.

## Step 3 — Regenerate pptx layout code

For each slide:
- If `<brand-root>/renderers/pptx/layouts/<id>.py` DOES NOT exist: create it from a layout template that imports `from components import (...)`, sets background from `data-role`, registers placeholders from `data-slots`.
- If it already exists: PRESERVE the existing Python. The catalog update is the single source of truth for metadata; the Python contains hand-tuned positions + decoration. Do NOT overwrite.

## Step 4 — Build + verify

```bash
cd <brand-root>/renderers/pptx && uv run python build.py
```

Render `out/<Brand>-Template.pptx` to PNGs via `soffice + pdftoppm`.

Compare each generated slide to the corresponding `<section>` in the source HTML (rendered via Chrome headless). LLM eyeballs for divergences. Iterate up to 3× per `../../deck/references/iteration-loop.md` — same loop as `/deck` uses.

## Determinism

Running `/compile` twice on the same HTML produces byte-identical catalog output and (when catalog entries are new) identical initial layout stubs. Existing hand-tuned layouts are preserved.

## When something breaks

- **Missing attribute**: hard fail, clear diagnostic, no partial write.
- **Invalid JSON in data-slots**: hard fail, show the bad slot and a suggestion.
- **New slide in HTML but no matching layout file**: compiler creates a stub; operator fills in the rest.
- **Slide removed from HTML**: compiler leaves orphaned layout `.py` in place + emits warning; operator decides whether to delete.
