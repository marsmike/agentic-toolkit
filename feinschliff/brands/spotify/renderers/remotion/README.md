# Remotion renderer — canonical

Canonical home for the Feinschliff Remotion theme recipe.

**Files:**
- `feinschliff-theme.md` — copy-paste recipe: palette + typography + `theme.ts` object, derived by hand from `brands/feinschliff/tokens.json`. Consumed by the Remotion skill when authoring a Feinschliff-branded video.

**Consumers:**
- `remotion/skills/remotion/references/design-system.md` — points a reader at `feinschliff-theme.md` when they need the Feinschliff theme instead of fetching a generic DESIGN.md from awesome-design-md.

**Contract:**
- Reads: `brands/feinschliff/tokens.json` (manually mirrored — update `feinschliff-theme.md` when tokens change).
- Writes: nothing. This is authoring documentation, not runnable code.
- No imports from other renderers.

## Deferred

- **`components.tsx`** — importable React components (`KPICard`, `SlideFrame`, `Chip`, `RuleDivider`) so Remotion projects consume Feinschliff primitives as code rather than copy-paste. Will land when a real composition drives the need; deferring today avoids dead code.
- **Programmatic tokens loading.** Today the `feinschliff-theme.md` recipe carries hex/px values that mirror `tokens.json` by hand. Once the TSX components above exist, the `theme.ts` recipe will become an importable module that reads `tokens.json` at build time — same pattern as the pptx/excalidraw/svg renderers do in Python.

See `feinschliff/README.md` → "Deferred work" for the plugin-wide roadmap.
