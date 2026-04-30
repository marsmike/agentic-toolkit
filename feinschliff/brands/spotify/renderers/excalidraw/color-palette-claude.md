# Color Palette — Feinschliff

Canonical Feinschliff palette for excalidraw diagrams. Sourced from
`brands/feinschliff/tokens.json`; mirrored by hand in
`apply_feinschliff_theme.py` (dicts `FILL_TO_FEINSCHLIFF`, `TEXT_TO_FEINSCHLIFF`,
`STROKE_TO_FEINSCHLIFF`).

## DSL color mapping

| DSL semantic | Fill      | Stroke   | Text    |
|--------------|-----------|----------|---------|
| `primary`    | white     | ink      | ink     |
| `secondary`  | paper     | ink      | ink     |
| `tertiary`   | fog       | graphite | ink     |
| `start`      | accent    | black    | black   |
| `end`        | black     | black    | white   |
| `warning`    | highlight | black    | black   |
| `decision`   | highlight | black    | black   |
| `ai`         | ink       | accent   | white   |
| `inactive`   | paper     | silver   | graphite|
| `error`      | accent    | black    | black   |
| `code`       | black     | accent   | white   |
| `data`       | black     | accent   | white   |

## Rules

- **Accent is scarce.** One hero element per diagram.
- **Text on accent is black.**
- **Canvas is white.**

## Usage

```bash
# 1. Write .dsl with `theme bsh` as the first line (auto-applies via expand_dsl.py import).
# 2. Or retrofit an existing .excalidraw. From within this plugin:
uv run python ${CLAUDE_PLUGIN_ROOT}/brands/feinschliff/renderers/excalidraw/apply_feinschliff_theme.py <file.excalidraw>
# From the sibling excalidraw plugin (cross-plugin):
uv run python ${CLAUDE_PLUGIN_ROOT}/../feinschliff/brands/feinschliff/renderers/excalidraw/apply_feinschliff_theme.py <file.excalidraw>
```

See `README.md` in this folder for the renderer contract.
