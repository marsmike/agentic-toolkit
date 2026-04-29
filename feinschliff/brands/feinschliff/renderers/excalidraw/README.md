# Excalidraw renderer — canonical

Canonical home for the Feinschliff excalidraw theme.

**Files:**
- `apply_feinschliff_theme.py` — post-expansion filter that recolours an `.excalidraw` doc to the Feinschliff palette. Imported by the excalidraw plugin's `expand_dsl.py` when a DSL file starts with `theme bsh`.
- `color-palette-feinschliff.md` — semantic-name → hex mapping, authored against `brands/feinschliff/tokens.json`.

**Consumers:**
- `excalidraw/references/expand_dsl.py` — inserts this folder on `sys.path` when the DSL requests `theme bsh`, then imports `apply_feinschliff` from here.

**Contract:**
- **Palette source.** `apply_feinschliff_theme.py` loads `brands/feinschliff/tokens.json` at import time into `T` (semantic name → uppercase hex). `FILL_TO_FEINSCHLIFF`, `TEXT_TO_FEINSCHLIFF`, and `STROKE_TO_FEINSCHLIFF` all resolve through `T`, so a tokens edit propagates automatically. Left-hand map keys (excalidraw-generic source hexes like `#3b82f6`) are still literals — they come from `expand_dsl.py`'s `SHAPE_COLORS` and aren't brand-owned.
- **Library mode:** `apply_feinschliff(doc: dict) -> None` mutates the excalidraw document in place. This is what `expand_dsl.py` uses when a DSL begins with `theme bsh`.
- **CLI mode:** `python apply_feinschliff_theme.py <file.excalidraw>` reads the file, applies the theme, and writes `<file>-bsh.excalidraw` next to the source. Used to retrofit an existing excalidraw that wasn't generated via the DSL.
- No imports from other renderers.
