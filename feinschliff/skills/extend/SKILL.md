---
name: extend
description: Adding a new component and layout to the active brand's Baukasten from a screenshot. Use when an existing deck has a pattern the Baukasten doesn't cover — timelines, org charts, custom frames.
---

# extend — Feinschliff Baukasten extension

## Active brand

These skills operate on the active brand pack at `feinschliff/brands/<brand>/`, where `<brand>` is resolved as follows:

1. `--brand <name>` flag if passed (highest precedence)
2. `FEINSCHLIFF_BRAND` env-var if set
3. Default `feinschliff`

Brand-pack contract: see [`../../references/brand-pack-spec.md`](../../references/brand-pack-spec.md).

In this document, `<brand-root>` stands for the resolved brand pack directory (`brands/feinschliff/` by default, or `brands/<your-brand>/`).

Adds a new component + layout to the active brand's Baukasten, regenerating the catalog. Screenshot-driven additive workflow — no existing code modified.

## Quick Start

```
/extend screenshot.png "timeline: 5 milestones, accent on active"
```

See [`references/quick-start.md`](references/quick-start.md) for argument details.

## Pipeline (summary)

1. **Analyse** — LLM inspects screenshot + description; emits a proposed plan for confirmation.
2. **Generate component** — pure `add_<name>` function in `<brand-root>/renderers/pptx/components/<name>.py`.
3. **Generate layout** — `NAME` + `build(layout)` in `<brand-root>/renderers/pptx/layouts/<name>.py`.
4. **Add catalog entry** — append to `<brand-root>/catalog/layouts.json` with slots + placeholder map.
5. **Append demo slide** — to `build_demo_deck()` in `<brand-root>/renderers/pptx/slides.py`.
6. **Update tests** — bump hard-coded layout count in 3 locations.
7. **Build + verify** — `uv run python build.py` + `pytest tests/`.
8. **Visual verify** — LLM-eyeball the rendered PNG against the source screenshot.

See [`references/pipeline.md`](references/pipeline.md) for step-by-step detail.

## Design principle

Additive, not intrusive. Never modifies existing `components/*.py` or `layouts/*.py`. If the new component looks near-identical to an existing one, tune the existing one instead (outside this skill's scope).

## References

- [`references/pipeline.md`](references/pipeline.md) — full step-by-step recipe.
- [`references/quick-start.md`](references/quick-start.md) — argument details.
- [`../../references/brand-pack-spec.md`](../../references/brand-pack-spec.md) — brand-pack contract.
- [`../../references/renderer-protocol.md`](../../references/renderer-protocol.md) — renderer-level contract.
- [`../deck/references/iteration-loop.md`](../deck/references/iteration-loop.md) — the verify-and-iterate loop.
- `<brand-root>/renderers/pptx/layouts/kpi_grid.py` — reference layout pattern (every default brand pack ships one).
