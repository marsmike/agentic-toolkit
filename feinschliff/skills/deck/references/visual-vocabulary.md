# Visual Vocabulary

How to pick the right visual for a concept. This reference is generic (brand-agnostic). Brand-specific layout names come from the active brand's `<brand-root>/catalog.json` (see `../SKILL.md` for how the active brand resolves).

## The Process

For each slide you plan to generate:
1. Identify the **concept type** (from the list below).
2. Look up **candidate visual types**.
3. Cross-reference `catalog.json` for the brand's specific layouts that match.
4. Prefer layouts whose `when_to_use` aligns with your content; avoid layouts whose `when_not_to_use` applies.

## Concept → Visual-type Mapping

Based on Financial Times Visual Vocabulary (Comparison / Composition / Distribution / Relationship / Change-over-time / Quantity) extended for slides.

### Cover / opener
**Concepts:** deck cover, chapter opener, single-statement slide
**Visual types:** title-primary, title-with-visual, chapter-opener
**Catalog layouts (feinschliff):** title-orange, title-ink, title-picture, chapter-orange, chapter-ink, full-bleed-cover. Cross-reference each pack's `catalog.json` for the actual ids.

### Agenda
**Concepts:** table-of-contents, section-list
**Visual types:** agenda
**Catalog layouts:** agenda

### Quantity / metrics
**Concepts:** 2-4 high-level numbers with units and change indicators
**Visual types:** data-quantity
**Catalog layouts:** kpi-grid

### Comparison
**Concepts:** before/after, pros/cons, product-A-vs-B, two-track plan
**Visual types:** content-columns (2)
**Catalog layouts:** two-column-cards
**Fallback:** bar-chart if the comparison is numeric with 2-6 items.

### Composition / parts of a whole
**Concepts:** three pillars, strategy triad, phased plan
**Visual types:** content-columns (3 or 4)
**Catalog layouts:** three-column, four-column-cards

### Content with supporting visual
**Concepts:** product-detail, story-beat with hero image
**Visual types:** content-with-visual
**Catalog layouts:** text-picture

### Voice moment
**Concepts:** quote, customer testimonial, leadership principle
**Visual types:** quote
**Catalog layouts:** quote

### Data comparison (ordinal or ranked)
**Concepts:** revenue by region, survey results
**Visual types:** data-comparison
**Catalog layouts:** bar-chart

### Diagram — architectural / conceptual / freeform
**Concepts:** diagram, flowchart, architecture overview, architectural overview, system overview, system architecture, layered system, layer diagram, concept map, mind map, block diagram, multi-element flow with callouts
**Trigger words:** if the user's brief says *"diagram"*, *"flowchart"*, *"architecture"*, *"architectural overview"*, *"system overview"*, *"layers"*, *"concept map"*, *"mind map"*, or *"show how X connects to Y"* — pick `diagram`. One rich, hand-authored Excalidraw DSL per slide, rendered + brand-themed (using the active brand pack's tokens) at build time via `slides.add_diagram()`.
**Visual types:** diagram
**Catalog layouts:** diagram
**Fallback:** if the content fits a parameterized template, prefer that instead — process-flow for pipelines, pyramid for hierarchy, venn for overlap, 2x2-matrix for quadrants, funnel for conversion, gantt for time-phased plans.

### Closer
**Concepts:** thank-you, deck close
**Visual types:** closer
**Catalog layouts:** end

## What to do when nothing fits

If no layout in the brand catalog fits, prefer the closest generic match with `when_not_to_use` that doesn't apply. If multiple layouts could fit, the tie-breaker is `role` + `when_to_use` phrasing — pick the one whose description most closely matches your content intent.

Never force content into a mismatched layout. If the user's content is genuinely unusual, run `/extend` to propose a new component.
