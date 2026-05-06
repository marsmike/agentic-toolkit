---
name: compile
description: Compile a single design source (Claude Design HTML, screenshot, markdown brief, or existing .pptx) into a v2 template artifact and a catalog entry for the active brand. Use when adding a new layout to a brand pack or regenerating one that drifted from its design source.
---

# compile — produce a v2 template artifact

`/compile` is per-template, not bulk-regenerate. It takes ONE design source
and produces:

1. A template file at `<brand-root>/templates/<renderer>/<id>.<ext>`.
2. A catalog entry update in `<brand-root>/catalog.json` carrying
   `source` + `sha256` + `placeholder_map` for that renderer.

Visual verification runs before commit so quality is locked in at compile time
rather than discovered by the next `/deck` user.

## Active brand

Resolved from (highest precedence first):

1. `--brand <name>` flag.
2. `FEINSCHLIFF_BRAND` env-var.
3. Default `feinschliff`.

`<brand-root>` is the resolved brand pack directory.

## Inputs

- A design source — pick one:
  - `--from-pptx <path>` — adopt an existing `.pptx`. Local path or fetched
    URL; the file is canonicalised to single-slide and its layout
    placeholders are materialised onto the slide.
  - `--from-html <path>` — Claude Design HTML.
  - `--from-screenshot <path>` — PNG/JPG; the model extracts intent.
  - `--from-brief <path>` — markdown describing the layout.
- `--renderer <kind>` — one of `pptx` (only kind supported in PR-2), `svg`,
  `excalidraw`, `remotion`. Brands choose which renderers they support per
  template.
- `--id <slug>` — catalog id of the entry to create or update.

## Pipeline

1. **Extract intent.** Read the design source and produce a Slide Concept:
   layout name, slot schema, asset hints.
2. **Emit template.** For `--renderer pptx`:
   - `--from-pptx`: invoke `feinschliff/scripts/extract_v2_template.py`
     against the source file. The script asserts single-slide,
     materialises layout-only placeholders, and drops orphan slide parts.
   - Otherwise: build a fresh slide via python-pptx using the brand's
     master and the target slide layout, populate placeholders to match
     the slot schema, then run the same extraction step to canonicalise.
3. **Visual verification.** Run `feinschliff/scripts/verify_v2_template.py`:
   render the emitted template AND the design source to PNG via headless
   soffice, compare via `imagehash.phash`. Threshold: distance ≤ 8 (a
   typical "looks different to a human" cutoff). On fail, leave the
   rendered PNGs in `<brand-root>/.port-verify/<id>/` for inspection and
   **do not** update the catalog.
4. **Commit catalog entry.** On verification pass, write `source`,
   `sha256`, `placeholder_map`, plus narrative `slots`, `when_to_use`,
   and `when_not_to_use` text to `<brand-root>/catalog.json`.

## Quick start

```
/compile --from-pptx /path/to/template.pptx --renderer pptx --id new-thing
/compile --from-html <brand-root>/claude-design/<brand>-2026.html --renderer pptx --id title-orange
```

See [`references/pipeline.md`](references/pipeline.md) for step-by-step detail
and [`references/quick-start.md`](references/quick-start.md) for invocation
forms across the four design-source types.

## References

- [`../../scripts/extract_v2_template.py`](../../scripts/extract_v2_template.py) — extraction helper
- [`../../scripts/verify_v2_template.py`](../../scripts/verify_v2_template.py) — phash visual verifier
- [`../../scripts/port_brand.py`](../../scripts/port_brand.py) — bulk-port reference used in PR-2
- [`../../references/brand-pack-spec.md`](../../references/brand-pack-spec.md) — brand-pack contract
- `<brand-root>/catalog.json` — the catalog file `/compile` updates
