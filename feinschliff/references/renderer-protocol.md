# Renderer Protocol

Contract every Feinschliff renderer must satisfy. Used by `/compile` when regenerating renderer code from Claude Design HTML.

In this document, `<brand-root>` stands for the resolved brand pack directory — `feinschliff/brands/<brand>/` (e.g. `brands/feinschliff/`). The active brand is resolved via `FEINSCHLIFF_BRAND` / `--brand` (default `feinschliff`).

## Responsibilities

A renderer in `<brand-root>/renderers/<name>/`:

1. **Reads** `<brand-root>/tokens.json` (DTCG 1.0) for all colour/typography/sizing tokens.
2. **Reads** `<brand-root>/catalog/layouts.json` + `<brand-root>/catalog/components.json` (if present) for the list of layouts + components to render.
3. **Optionally reads** `<brand-root>/logo/` for raster/vector assets.
4. **Writes** format-specific artefacts to `<brand-root>/renderers/<name>/out/`.
5. **Does NOT import** from other renderers. Renderers are siblings.
6. **Exposes a build entrypoint** (e.g. `build.py`, `build.ts`) runnable from the renderer's folder.

## File layout

```
<brand-root>/renderers/<name>/
├── <language manifest>       e.g. pyproject.toml, package.json
├── build.<ext>               entrypoint
├── components/               (optional) format-specific primitives
├── layouts/                  (optional) format-specific layouts
├── assets/                   (optional) format-specific assets (cached logos, etc.)
└── out/                      build artefact — gitignored per brand-pack-spec
```

## Minimum viable renderer

A placeholder renderer with only a `README.md` satisfies the protocol (as a TODO). It promises a real implementation in a future PR but does not block the rest of the system.

## When `/compile` regenerates a renderer

`/compile <name>` for a renderer with only a README:
- Reports "renderer `<name>` is a placeholder; skipping code regeneration" but still updates `<brand-root>/catalog/layouts.json` based on the HTML.

`/compile <name>` for a populated renderer:
- Regenerates the renderer's layout code from the Claude Design HTML attributes.
- Runs the renderer's build entrypoint.
- Verifies output against the HTML via the iteration loop.

## Adding a new renderer

1. Create `<brand-root>/renderers/<name>/` with a README explaining the planned format.
2. When ready: add the language manifest + `build.<ext>` + whatever module structure is idiomatic for the language.
3. Add the renderer's entry under each layout's `renderer` map in `catalog/layouts.json`.
4. Run `/compile <name>` to emit layout code + build.
5. Verify output via the iteration loop.

## Versioning

Tokens: semver via `$description` in `tokens.json` → major-bump on breaking changes to token names/types.
Catalog: `schema_version` field in `layouts.json` → bump on breaking shape changes.
Renderers: independent; a renderer can lag behind catalog bumps if it stays on an older schema version (indicated in the renderer's README).
