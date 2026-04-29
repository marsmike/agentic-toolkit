# Claude Design Prompt — How to request Feinschliff-ready HTML

This is the **generic, brand-agnostic contract** — what `data-*` attributes `/compile` expects on every slide, and what it does with them. For a ready-to-paste prompt with a brand's full layout inventory, voice rules, and brand tokens, see the active brand pack's `feinschliff/<brand-root>/claude-design-prompt.md` (e.g. `feinschliff/brands/feinschliff/claude-design-prompt.md`).

Hand this prompt to Claude Design when generating or updating a brand's design-system HTML. It asks Claude Design to emit the six `data-*` attributes per slide that Feinschliff's `/compile` parses.

## The prompt

```
Generate a design-system HTML deck for the <BRAND_NAME> corporate brand.

Canvas: 1920×1080 CSS px, one <section class="slide"> per design variant. Include all layout variants the brand supports: title slides, chapter openers, agenda, KPI grid, multi-column content, text+picture, full-bleed cover, bar chart, components showcase, quote, end.

For EVERY <section class="slide">, include the following data-* attributes:

1. data-label (required): short human-readable layout name, e.g. "Title Orange", "KPI Grid".

2. data-role (required): one of
   [title-primary, title-with-visual, chapter-opener, agenda, data-quantity,
    data-comparison, data-timeline, content-columns, content-with-visual,
    quote, reference, closer]

3. data-concepts (required): comma-separated list of abstract concept types
   the layout serves. Examples:
   "cover, headline, full-slide-statement"
   "quantity, metrics, summary-figures"
   "comparison, pair, before-after"

4. data-when-to-use (required): 1-2 sentences describing when to pick this layout.

5. data-when-not-to-use (required): 1-2 sentences describing when to avoid this layout and which alternative to use instead. This field is critical — negative guidance significantly improves layout-selection quality downstream.

6. data-slots (required): JSON string mapping slot names to JSON Schema definitions. Each slot has:
   - type: "string" | "array"
   - description: what the slot's content represents
   - maxLength: soft cap guiding content generation
   - optional: true if the slot is not required
   - format: "path" for image slots
   - For array slots: items + minItems + maxItems

Example:

<section class="slide"
  data-label="KPI Grid"
  data-role="data-quantity"
  data-concepts="quantity, metrics, summary-figures"
  data-when-to-use="2-4 high-level quantitative figures with units + labels + deltas. Most scannable format for executive updates."
  data-when-not-to-use="More than 4 figures — use a table. Figures without clear units — use a title slide with the number callout."
  data-slots='{
    "eyebrow": {"type": "string", "maxLength": 60, "optional": true},
    "title":   {"type": "string", "maxLength": 80},
    "kpis": {
      "type": "array", "minItems": 2, "maxItems": 4,
      "items": {
        "type": "object",
        "properties": {
          "value": {"type": "string"},
          "unit":  {"type": "string"},
          "key":   {"type": "string", "maxLength": 40},
          "delta": {"type": "string", "maxLength": 20}
        },
        "required": ["value", "key"]
      }
    }
  }'>
  ...existing visual HTML...
</section>

Design tokens (colour, typography, spacing) stay in <style> as today — no format change requested. Just add the six attributes per slide.

End every deck with a "<BRAND_NAME> · End"-style closer slide. Include a "Components Showcase" slide documenting the UI kit.
```

## Why we ask Claude Design for this

Closing the loop with Claude Design means the brand's design system CARRIES its own semantic metadata. Our `/compile` becomes a dumb pipe — change Claude Design's template, and the catalog regenerates for free. No custom parsers, no per-brand rules.

## What `/compile` does with the output

1. Parses every `<section class="slide">`.
2. Reads the six `data-*` attrs.
3. Validates: all six must be present (hard fail on missing).
4. Emits `<brand-root>/catalog/layouts.json` + per-layout `.py` stub in `<brand-root>/renderers/pptx/layouts/` (active brand resolved via `FEINSCHLIFF_BRAND` / `--brand`; default `feinschliff`).
5. For each renderer with existing code, preserves human-written refinements via a 3-way merge strategy (catalog metadata auto-updates; component/layout Python keeps manual tweaks unless the slot shape changed).
