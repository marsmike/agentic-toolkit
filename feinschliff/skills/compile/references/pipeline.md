# /compile pipeline

Step-by-step detail for the four design-source paths. The skill is per-template
in v2 — one source → one Slide Concept → one template artefact + one catalog
entry. The bulk-regeneration model used in v1 is gone (`port_brand.py` is the
v2 equivalent for one-shot bulk porting; see `feinschliff/scripts/`).

## Common preconditions

- `<brand-root>` resolves to one of `feinschliff/brands/{feinschliff,bmw,ferrari,spotify,claude,binance}/`
  (see [`../SKILL.md`](../SKILL.md#active-brand) for resolution order). All
  path placeholders below are relative to `feinschliff/`.
- The catalog at `<brand-root>/catalog.json` exists and validates against
  `lib/schemas/catalog-v2.schema.json`.
- For `--renderer pptx`, the dev environment has LibreOffice (`soffice`) and
  `pdftoppm` available — both are required by the visual-verification step.
  See `scripts/verify_v2_template.py` for the install path on macOS / Linux.

## --from-pptx (adoption mode)

Used when a brand ships an existing `.pptx` (e.g. a curated kit template or a
hand-authored slide).

1. Resolve the source. If a local path, copy to a tmp dir. If a URL, fetch via
   the resolver's auth-aware HTTP path (see `lib/fetcher.py`).
2. Run `scripts/extract_v2_template.py
   --input <fetched.pptx> --layout-name "<layout>" --out
   <brand-root>/templates/pptx/<id>.pptx`. The script:
   - asserts single-slide
   - copies layout-only placeholders onto the slide so `fill_slot` can address
     every placeholder the layout declares
   - drops orphan slide parts via `part.drop_rel(rId)` so the saved file is
     small and free of duplicate-name artefacts
3. Run `scripts/verify_v2_template.py` against the original `.pptx` (the v1
   baseline equivalent). Skip this step only if there is no design-source
   render to compare against (e.g. a brand-new template with no prior
   version); in that case render the emitted template alone for visual
   inspection and require a human eyeball before committing the catalog.
4. Compute sha256 of the saved `.pptx`.
5. Update `<brand-root>/catalog.json`:
   - If an entry with `id == <id>` exists: replace its
     `renderer.pptx.{source,sha256,placeholder_map}`. Keep narrative fields
     (`slots`, `when_to_use`, `when_not_to_use`, `tags`) unless the design
     source changes them.
   - Otherwise: insert a new entry. Slots and narrative come from the
     intent-extraction step.

## --from-html (Claude Design HTML)

Used when a brand designer has authored or updated a Claude Design HTML spec
at `<brand-root>/claude-design/<brand>-2026.html`. One section in the HTML →
one Slide Concept → one template.

1. Parse the HTML, find the section matching `--id`. Validate the six required
   `data-*` attributes (label, role, concepts, when-to-use, when-not-to-use,
   slots). Hard-fail on missing or malformed attrs.
2. Build a fresh slide via python-pptx using the brand's master/theme and the
   target slide layout. Populate placeholders to match the slot schema parsed
   from the HTML.
3. Save as a single-slide `.pptx`, then run `extract_v2_template.py` against
   it to canonicalise (materialise layout placeholders + drop orphan parts).
   The result lands at `<brand-root>/templates/pptx/<id>.pptx`.
4. Render both the HTML section (via Playwright headless) and the emitted
   template to PNG; compare via phash. On pass, commit catalog entry.

## --from-screenshot (PNG/JPG)

Used when there is no machine-readable design source — a designer's PNG export
or a photograph of a paper sketch.

1. Vision model reads the screenshot and produces a Slide Concept.
2. Build a fresh slide as in `--from-html` step 2, but with slot values
   inferred from the screenshot rather than parsed from HTML.
3. Same canonicalisation + verification as `--from-html`, except the baseline
   render IS the screenshot.

## --from-brief (markdown)

Used when a designer hands over a markdown spec instead of a finished visual.

1. Parse the brief to extract the Slide Concept.
2. Build a fresh slide. Visual verification is best-effort: there is no
   rendered baseline, so compare against a model-rendered "design intent"
   image, with a relaxed phash threshold (≤ 16 instead of ≤ 8).

## Common postconditions

- `<brand-root>/templates/<kind>/<id>.<ext>` exists and parses without error.
- The catalog entry's `sha256` matches the file's actual content sha256.
- Visual-verification PNGs sit at `<brand-root>/.port-verify/<id>/` (gitignored)
  for at least one /compile run, then are overwritten on the next.
- `feinschliff brand inspect <brand>` shows the new entry under v2 layouts.

## Failure modes

- **Verification fails (phash distance > threshold).** Catalog is NOT updated;
  the emitted `.pptx` stays at `templates/pptx/<id>.pptx` for manual
  inspection. Either:
  - Fix the extraction (likely a placeholder-instantiation issue), re-run
    `/compile`.
  - Lower the threshold via `--threshold N` if the difference is acceptable
    (e.g. font-rendering noise on a brand with custom fonts).
  - Hand-edit the template and run `/compile --from-pptx <hand-edited.pptx>`
    to commit the manual fix.
- **Schema validation fails.** The Slide Concept produced an entry shape that
  does not match the v2 catalog schema. Inspect the catalog after /compile's
  draft, fix by hand, commit.
- **No demo source / new template.** When a layout is brand-new (no prior v1
  baseline), there is nothing to phash-diff against. Render the emitted
  template alone and require a human approval before committing the catalog.

## Determinism

Re-running `/compile` against the same `--from-pptx` source produces a
byte-identical template artefact and identical sha256. Re-running against
`--from-html` is byte-stable when python-pptx + the brand master have not
changed. Re-running against `--from-screenshot` or `--from-brief` is NOT
deterministic because intent extraction goes through the model — re-runs may
produce semantically equivalent but byte-different artefacts.
