---
name: compile
description: Compiling a Claude Design HTML file into the active brand's Baukasten (catalog + renderer code). Use when a brand pack's design changes — rare; audience is tech leads.
---

# compile — Feinschliff brand compiler

## Active brand

These skills operate on the active brand pack at `feinschliff/brands/<brand>/`, where `<brand>` is resolved as follows:

1. `--brand <name>` flag if passed (highest precedence)
2. `FEINSCHLIFF_BRAND` env-var if set
3. Default `feinschliff`

Brand-pack contract: see [`../../references/brand-pack-spec.md`](../../references/brand-pack-spec.md).

In this document, the placeholder `<brand-root>` stands for the resolved brand pack directory: `brands/feinschliff/` (default) or `brands/<your-brand>/`.

Parses `<brand-root>/claude-design/<brand>-2026.html` and regenerates `<brand-root>/catalog/layouts.json` + per-layout `.py` in `<brand-root>/renderers/pptx/layouts/`. Intended for when a brand authors a new Claude Design output.

## Quick Start

```
/compile --check    # drift check only, exits non-zero on drift
```

See [`references/quick-start.md`](references/quick-start.md) for all invocations.

## Pipeline (summary)

1. **Drift check** — HTML ↔ catalog label sync (standalone script, also the CI gate).
2. **Parse + validate** — assert six `data-*` attrs per section; fail loudly on missing.
3. **Emit catalog** — rewrite `<brand-root>/catalog/layouts.json`; preserve hand-tuned `placeholder_map`s.
4. **Regenerate pptx layout code** — create stubs for new layouts; preserve existing hand-tuned layout files.
5. **Build + verify** — render `<Brand>-Template.pptx`, LLM-eyeball against source HTML.

See [`references/pipeline.md`](references/pipeline.md) for step-by-step detail.

## References

- [`references/pipeline.md`](references/pipeline.md) — full step-by-step recipe.
- [`references/quick-start.md`](references/quick-start.md) — invocation forms.
- [`../../references/brand-pack-spec.md`](../../references/brand-pack-spec.md) — brand-pack contract.
- [`../../references/claude-design-prompt.md`](../../references/claude-design-prompt.md) — how to author the HTML.
- [`../../references/renderer-protocol.md`](../../references/renderer-protocol.md) — what a renderer must satisfy.
- `<brand-root>/catalog/layouts.json` — the authoritative catalog, rewritten by this skill.
