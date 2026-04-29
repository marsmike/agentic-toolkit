# Example — Feinschliff brand-pack template

Pre-built `.pptx` containing all 36 layouts of the Feinschliff brand pack. Open it in PowerPoint / Keynote / LibreOffice to browse the available slide styles before you author.

## What's inside

`Feinschliff-Template.pptx` (≈150 KB) — built from `feinschliff/brands/feinschliff/renderers/pptx/build.py`. Each layout appears once as a demo slide with placeholder content:

- title-orange / title-ink / title-picture · cover variants
- chapter-orange / chapter-ink · section openers
- executive-summary · KPI grid + insights + next-steps
- action-title · McKinsey-style headline + supporting body
- table · five-row product-line scorecard
- bar-chart / line-chart / stacked-bar / waterfall / matrix-2x2 / venn / pyramid / funnel / scorecard / process-flow / gantt · data layouts
- horizontal-bullets / vertical-bullets / two-column-cards / three-column / four-column-cards · text layouts
- quote · big-statement
- key-takeaways · 4-card recap
- end · closing
- (...and 9 more)

## Use

This is a **read-only reference**. To produce your own deck, run `/deck "<brief>"` in Claude Code — the plugin picks layouts, fills slots, and emits `out/<deckname>.pptx`. The template here is what the renderer produces when called with no content (each layout's `prompt_text` defaults).

## Regenerating

```bash
cd feinschliff/brands/feinschliff/renderers/pptx
uv sync
uv run python build.py
# out/Feinschliff-Template.pptx — copy here when the design system changes.
```

CI also rebuilds this template on every push and uploads it as a workflow artifact (see `.github/workflows/ci.yml` → "feinschliff brand pack build"). The committed copy here is a stable point-in-time reference; the CI artifact is the always-fresh build.
