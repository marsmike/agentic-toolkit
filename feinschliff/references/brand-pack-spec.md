# Brand-Pack Spec

A Feinschliff brand pack is a directory under `feinschliff/brands/` that conforms to this contract. The skills (`compile`, `deck`, `extend`) read from the active brand pack at runtime; the active pack is resolved via the `FEINSCHLIFF_BRAND` env-var (default: `feinschliff`) or the `--brand <name>` flag.

## Directory layout

```
feinschliff/brands/<brand-name>/
├── tokens.json                  (required)
├── catalog/
│   └── layouts.json             (required)
├── claude-design/
│   ├── <brand>-2026.html        (required — Claude Design HTML reference)
│   └── assets/                  (images, SVGs referenced by HTML)
├── renderers/
│   ├── pptx/                    (required for /deck and /compile)
│   │   ├── build.py             (entry point)
│   │   ├── theme.py             (token projection)
│   │   ├── master.py
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── pyproject.toml
│   │   └── .gitignore           (must include "out/")
│   ├── excalidraw/              (optional)
│   ├── svg/                     (optional)
│   └── remotion/                (optional)
├── logo/                        (optional)
├── NOTICE.md                    (required if pack uses third-party material)
└── README.md                    (recommended)
```

## File responsibilities

| File | Purpose |
|---|---|
| `tokens.json` | Single source of truth for color, typography, spacing. Conforms to W3C Design Tokens Format Module draft-2. |
| `catalog/layouts.json` | Layout catalog — list of available slide layouts with slot definitions, `placeholder_map`s, and the top-level `"brand"` field set to the brand pack's slug. |
| `claude-design/<brand>-2026.html` | The Claude Design HTML reference deck. Source of truth for what the brand "looks like" in 1920×1080 canvas. |
| `claude-design/assets/` | SVG wordmark assets and any other reference images the HTML loads. Wordmark assets are conventionally named `<brand>-wordmark-black.svg` and `<brand>-wordmark-white.svg`. |
| `renderers/pptx/build.py` | Entry point — produces a template `.pptx` in `out/<Brand>-Template.pptx`. |
| `renderers/pptx/theme.py` | Loads `../../tokens.json` and exposes constants (`T.ACCENT`, `T.HEX["accent"]`, `T.FONT_DISPLAY`, etc.) for renderer code. Token names are neutral semantic (`accent`, `accent-hover`, `highlight`, `ink`, `graphite`, `paper`, etc.) so the same renderer code works for any brand. |
| `renderers/pptx/master.py` | `apply_<brand>_theme()` function — installs the brand's color scheme and font scheme into the pptx master. |
| `renderers/{excalidraw,svg,remotion}/` | Optional renderer overrides. Each ships its own `apply_<brand>()` (Excalidraw) or `<brand>Theme` (Remotion) export consuming the same `tokens.json`. |
| `logo/` | Optional. Default brand packs render the wordmark from text via `chrome.add_logo()` rather than loading a logo asset. If present, files are referenced by name from renderers. |
| `NOTICE.md` | Required if the pack uses third-party material (fonts under SIL OFL, design tokens under another permissive license, etc.). One section per upstream with name, license, copyright, link. |
| `README.md` | Brand description, license, attribution summary, quick links. Recommended; not strictly required. |

## Design-token contract

`tokens.json` follows the W3C Design Tokens Format Module draft-2 schema. Required keys:

- `color` — must define at minimum: `accent`, `accent-hover`, `highlight`, `ink`, `graphite`, `paper`, `white`. Brand packs may add more.
- `font-family` — `display`, `body`, `mono`. Each value is an array of font names (the first is the brand's primary, the rest are fallbacks).
- `font-weight` — `light`, `regular`, `medium`, `bold` mapped to numeric weights.
- `font-size` — full token list mirroring the feinschliff baseline (used by the Baukasten layout code).
- `slide` — canvas dimensions, padding.

The reason token names are neutral semantic (`accent` not `orange`): a renderer written for one brand pack should run unchanged against any other brand pack. Brand packs ARE the place to put brand-specific values; renderer code should be brand-agnostic.

## Renderer contract

A `pptx/build.py` must:

- Build a template `.pptx` at `out/<Brand>-Template.pptx`.
- Read all colors and fonts from `../../tokens.json` via `theme.py` — never hardcode.
- Honor the catalog at `../../catalog/layouts.json`.
- Have its `out/` directory gitignored — build artifacts are not source.

The `master.py` exposes `apply_<brand>_theme(prs)` which installs colors + fonts into a python-pptx Presentation. Sibling renderers (Excalidraw, SVG, Remotion) follow the same pattern — `apply_<brand>()` or `apply_<brand>_theme()` exported by name. The `_theme` suffix is optional in the function name but conventional in the module name.

## Naming conventions

Observed patterns in the feinschliff brand pack (apply the same shape to your own pack):

| Convention | Pattern | Example |
|---|---|---|
| Brand slug | lowercase, single word | `feinschliff` |
| Catalog brand field | matches slug | `"brand": "feinschliff"` |
| Module path | `feinschliff.brands.<slug>.renderers...` | `feinschliff.brands.feinschliff.renderers.pptx.layouts.matrix_2x2` |
| Wordmark text | Capitalized brand name | `"Feinschliff"` |
| Wordmark assets | `<slug>-wordmark-{black,white}.svg` | `feinschliff-wordmark-black.svg` |
| Output filename | `<Brand>-Template.pptx` | `Feinschliff-Template.pptx` |
| Excalidraw export function | `apply_<slug>` (no `_theme` suffix) | `apply_feinschliff` |
| PPTX theme function | `apply_<slug>_theme` | `apply_feinschliff_theme` |
| Remotion theme constant | `<slug>Theme` (camelCase) | `feinschliffTheme` |
| Test file | `test_<slug>_brand_pack.py` | `tests/test_feinschliff_brand_pack.py` |

## Authoring a new brand pack

The fastest path to a new brand pack is to copy an existing OSS pack:

```bash
cp -R feinschliff/brands/feinschliff feinschliff/brands/myco
cd feinschliff/brands/myco
```

Then:

1. **Rewrite `tokens.json`** with your color palette and font families. Keep neutral semantic token names (`accent`, `accent-hover`, `highlight`, etc.) — only the values change.
2. **Rebrand text strings**: literal `Feinschliff` / `feinschliff` / `FEINSCHLIFF` becomes `Myco` / `myco` / `MYCO`. Run a comprehensive grep to catch all references:

   ```bash
   grep -rni "feinschliff" feinschliff/brands/myco \
     --include="*.py" --include="*.html" --include="*.json" \
     --include="*.md" --include="*.svg" --include="*.css" \
     --include="*.toml" --include="*.js"
   ```

   Should return zero hits when the rebrand is complete.
3. **Rename the wordmark SVG assets** (`<slug>-wordmark-{black,white}.svg`) and update the SVG content.
4. **Update `claude-design/<slug>-2026.html`** — at minimum the `:root` CSS variables and the Google Fonts import line. Inline `font-family` declarations in the deeper preview body can be left as-is if the file is documentation-only and the renderer doesn't consume it.
5. **Update `catalog/layouts.json`** — `"brand": "<slug>"` and any `module:` paths that reference the old brand.
6. **Rename the renderer functions** following the naming conventions table above.
7. **Smoke-test the build**:

   ```bash
   cd renderers/pptx && uv run python build.py
   ```

   Expected: exits 0, produces `out/<Brand>-Template.pptx`.
8. **Add a smoke test** at `feinschliff/tests/test_<slug>_brand_pack.py` mirroring the feinschliff template (4 tests: tokens valid, required color roles present, build succeeds, catalog brand field correct).
9. **Author `NOTICE.md`** if you used third-party fonts or design tokens.
10. **Open a PR**.

## License & attribution

Each brand pack `README.md` (or `NOTICE.md` if used) MUST declare:

- The license under which the pack itself is distributed (default MIT — match the repo).
- Any upstream design system or font licenses that apply (e.g., Noto Sans is SIL OFL).
- Any trademarked elements that are NOT included.

## Future: DESIGN.md ingestion (v0.2)

Feinschliff v0.2 will accept a `DESIGN.md` file from [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md) as direct brand-pack input. A DESIGN.md will be auto-converted to a `tokens.json` + a starter `claude-design/<slug>-2026.html`, with the renderer code inherited from the closest brand pack. The brand-pack contract above will remain stable — DESIGN.md is added as an alternative authoring path, not a replacement.
