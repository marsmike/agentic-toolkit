"""DSL → .excalidraw → Feinschliff-themed → PNG pipeline for /deck.

Given a DSL string and a slug, produces four sibling files under
<out_dir>/diagrams/:

  <slug>.dsl              — raw DSL (with any `theme bsh` pragma stripped)
  <slug>.excalidraw       — generic-palette expansion (editable in Excalidraw)
  <slug>-bsh.excalidraw   — same, post `apply_feinschliff` (editable, themed)
  <slug>-bsh.png          — rendered PNG of the themed version (embedded in pptx)

Returns the PNG path so the caller can add_picture() it into the slide.
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

# Bootstrap imports from the excalidraw plugin + feinschliff theme.
# Path layout: agentic-toolkit/feinschliff/brands/feinschliff/renderers/pptx/diagram_pipeline.py
# parents[0]=pptx, [1]=renderers, [2]=feinschliff, [3]=brands, [4]=feinschliff(plugin), [5]=agentic-toolkit
_HERE = Path(__file__).resolve().parent
_EXC_REFS = _HERE.parents[4] / "excalidraw" / "references"
_FEINSCHLIFF_EXC = _HERE.parent / "excalidraw"  # feinschliff/brands/feinschliff/renderers/excalidraw

for _p in (_EXC_REFS, _FEINSCHLIFF_EXC):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _strip_theme_bsh(dsl: str) -> str:
    """Strip a leading `theme bsh` line (case-insensitive) from DSL text.

    The first non-empty, non-comment line is inspected. If it is a `theme bsh`
    declaration, it is removed; otherwise the input is returned verbatim.
    We always apply the feinschliff theme ourselves via apply_claude_theme,
    so the pragma would cause double-theming.
    """
    lines = dsl.splitlines()
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # First non-empty non-comment line — check if it's `theme bsh`.
        parts = stripped.split(None, 1)
        if (
            len(parts) == 2
            and parts[0].lower() == "theme"
            and parts[1].strip().lower() == "bsh"
        ):
            # Drop this line.
            return "\n".join(lines[:i] + lines[i + 1 :])
        # First significant line isn't `theme bsh` — nothing to strip.
        return dsl
    return dsl


def render_diagram(dsl: str, slug: str, out_dir: Path) -> tuple[Path, list[str]]:
    """Run the full pipeline.

    dsl: source DSL text. Any leading `theme bsh` line is stripped — we
         always feinschliff-theme the output via apply_claude_theme here.
    slug: basename without extension, e.g. "03-architecture-overview".
    out_dir: deck output directory, e.g. Path("out/my-deck"). The function
             creates <out_dir>/diagrams/ if absent.

    Returns: (png_path, validator_issues).
      - png_path: Path to <out_dir>/diagrams/<slug>-bsh.png.
      - validator_issues: list of structural defects detected by
        diagram_validator.check() on the themed JSON. Empty = clean.
        Caller decides whether to iterate, surface, or proceed.
    """
    import expand_dsl  # from excalidraw/references
    import apply_claude_theme  # from feinschliff/brands/feinschliff/renderers/excalidraw
    import render_excalidraw  # from excalidraw/references
    import diagram_validator  # from feinschliff/brands/feinschliff/renderers/pptx (same dir)

    out_dir = Path(out_dir)
    diagrams_dir = out_dir / "diagrams"
    diagrams_dir.mkdir(parents=True, exist_ok=True)

    # 1. Normalize DSL.
    normalized = _strip_theme_bsh(dsl)

    # 2. Write normalized DSL.
    dsl_path = diagrams_dir / f"{slug}.dsl"
    dsl_path.write_text(normalized)

    # 3. Expand DSL → generic excalidraw JSON.
    generic_doc = expand_dsl.parse_dsl(normalized)
    generic_path = diagrams_dir / f"{slug}.excalidraw"
    generic_path.write_text(json.dumps(generic_doc, indent=2))

    # 4. Apply Feinschliff theme to a deep copy so generic file stays pristine.
    themed_doc = apply_claude_theme.apply_claude(copy.deepcopy(generic_doc))
    themed_path = diagrams_dir / f"{slug}-bsh.excalidraw"
    themed_path.write_text(json.dumps(themed_doc, indent=2))

    # 5. Validate structural layout BEFORE rendering — validator runs on the
    # themed JSON (same geometry, just recolored). Issues are surfaced to the
    # caller as a return value; we still render so the caller can see the
    # output and decide next steps.
    issues = diagram_validator.check(themed_doc)

    # 6. Render themed version to PNG.
    png_path = diagrams_dir / f"{slug}-bsh.png"
    render_excalidraw.render(
        themed_path,
        output_path=png_path,
        scale=2,
        max_width=1920,
    )

    return png_path, issues


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="DSL → Feinschliff-themed Excalidraw PNG")
    ap.add_argument("dsl_file", type=Path)
    ap.add_argument("--slug", default=None, help="default: dsl file stem")
    ap.add_argument("--out-dir", type=Path, default=Path("."))
    args = ap.parse_args()
    slug = args.slug or args.dsl_file.stem
    png, issues = render_diagram(args.dsl_file.read_text(), slug, args.out_dir)
    if issues:
        for line in issues:
            print(f"[validator] {line}", file=sys.stderr)
    print(png)
