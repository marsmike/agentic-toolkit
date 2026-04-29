---
name: deck
description: Build or polish a brand-compliant PowerPoint deck using the active brand's Baukasten. Use when the user asks to create a deck, make a presentation, or polish a rough .pptx.
---

# deck — Feinschliff PPTX deck creator

## Active brand

These skills operate on the active brand pack at `feinschliff/brands/<brand>/`, where `<brand>` is resolved as follows:

1. `--brand <name>` flag if passed (highest precedence)
2. `FEINSCHLIFF_BRAND` env-var if set
3. Default `feinschliff`

Brand-pack contract: see [`../../references/brand-pack-spec.md`](../../references/brand-pack-spec.md).

In this document, `<brand-root>` stands for the resolved brand pack directory (`brands/feinschliff/` by default, or `brands/<your-brand>/`).

Creates or polishes presentations using the active brand's Baukasten. Theory-aware: infers audience + narrative frame, applies anti-patterns, critiques design defects.

## Quick Start

```
/deck "Q1 2026 update: 62k employees, +5.1% revenue, 40 factories"
```

See [`references/quick-start.md`](references/quick-start.md) for more examples.

## Modes

- **create** — `/deck "brief"` → new deck from scratch.
- **polish** — `/deck polish rough.pptx` → reflow an existing deck into brand layouts.
- **critique** — `/deck critique existing.pptx` → read-only defect analysis.

See [`references/modes.md`](references/modes.md) for full mode semantics and the step-1b approval-gate format.

## Pipeline (summary)

1. **Ask** — perfection bar (3 or 6 iter).
2. **Ingest** — brief / outline / `.pptx` → `content_plan.json` + `design_brief.json`.
3. **Present** — step 1b approval gate (enter / edit / redo).
4. **Plan** — layouts chosen per design brief → `deck_plan.json`.
5. **Build** — render via the active brand's Baukasten → `out/<name>.pptx`.
6. **Verify** — **MANDATORY, NEVER SKIPPED.** Render to PNG; LLM-eyeball against all 11 defect classes AND the active brand's `claude-design/<brand>-2026.html` reference. Emit `out/verify_report.md` — human-readable, and the completion gate.
7. **Revise** — loop back to build if defects; hard stop at the step-0 budget (3 default / 6 perfectionist).

**Completion rule.** Never declare the deck done without `out/verify_report.md` on disk from at least one verify pass. If you find yourself about to say "done" and the file doesn't exist, you skipped step 6 — go back and run it.

See [`references/pipeline.md`](references/pipeline.md) for step-by-step detail.

## References

**Recipe:** [`references/pipeline.md`](references/pipeline.md) · [`references/modes.md`](references/modes.md) · [`references/quick-start.md`](references/quick-start.md) · [`references/iteration-loop.md`](references/iteration-loop.md) (11-class verify).

**Brand + layouts:** [`references/visual-vocabulary.md`](references/visual-vocabulary.md) (concept → layout) · [`references/content-best-practices.md`](references/content-best-practices.md) (voice, slot caps).

**Theory:** [`references/narrative-frames.md`](references/narrative-frames.md) (SCQA / PSSR / Sparkline / Man-in-Hole) · [`references/audience-calibration.md`](references/audience-calibration.md) (exec / manager / dev / peer) · [`references/slide-claim-test.md`](references/slide-claim-test.md) · [`references/anti-patterns.md`](references/anti-patterns.md) · [`references/design-brief-schema.md`](references/design-brief-schema.md).
