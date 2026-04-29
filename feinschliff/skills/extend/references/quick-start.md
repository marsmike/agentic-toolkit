# /extend Quick Start

```
/extend path/to/screenshot.png "timeline: 5 milestones, mono dates, accent on the active one"
```

Required arguments:
1. Path to a screenshot of the pattern.
2. A description including the component name, content shape, and visual hints.

The new component + layout land in the active brand pack (resolved via `FEINSCHLIFF_BRAND` / `--brand`; default `feinschliff`). The skill emits a proposed plan (name, visual atoms, content shape, position hints) for you to confirm before generation begins.
