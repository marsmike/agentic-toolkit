# /compile quick start

## Adopt an existing .pptx

```
/compile --from-pptx /path/to/template.pptx --renderer pptx --id new-thing
```

The most common path. Pull a curated `.pptx`, canonicalise it (single-slide,
materialise layout placeholders, strip orphan parts), phash-verify against the
source, write the catalog entry.

## From a Claude Design HTML section

```
/compile --from-html <brand-root>/claude-design/<brand>-2026.html --renderer pptx --id title-orange
```

One HTML section → one template. Useful when a brand's design system ships in
HTML.

## From a screenshot

```
/compile --from-screenshot ~/Pictures/sketch.png --renderer pptx --id chapter-orange
```

Vision-model intent extraction → fresh slide → canonicalise → verify against
the screenshot itself.

## From a markdown brief

```
/compile --from-brief ./briefs/scorecard.md --renderer pptx --id scorecard
```

Best-effort verification: there is no rendered baseline, so the threshold is
relaxed (`--threshold 16`).

## Override the verification threshold

```
/compile --from-pptx <…> --renderer pptx --id <…> --threshold 4
```

Tighter threshold for high-fidelity adoption (e.g. matching kit templates
byte-for-byte). Default is 8 ("looks different to a human").

## Skip verification

```
/compile --from-pptx <…> --renderer pptx --id <…> --skip-verify
```

Use only when there's genuinely no baseline (brand-new layout). A human must
eyeball `<brand-root>/templates/pptx/<id>.pptx` and the `.port-verify/<id>/`
PNGs before committing.
