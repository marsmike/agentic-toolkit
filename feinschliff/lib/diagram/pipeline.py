"""DSL → generic Excalidraw → brand-themed Excalidraw → PNG pipeline.

Brand-agnostic. The caller passes the brand pack root and the name of the
theme module to apply (a Python module under
``<brand-root>/renderers/excalidraw/`` exposing an ``apply_<brand>(doc)``
callable). The pipeline produces four sibling files under
``<out_dir>/diagrams/``:

  <slug>.dsl                 — raw DSL (with any ``theme <pragma>`` line stripped)
  <slug>.excalidraw          — generic-palette expansion (editable)
  <slug>-<brand>.excalidraw  — themed (editable)
  <slug>-<brand>.png         — rendered PNG of the themed version
"""
from __future__ import annotations

import copy
import importlib
import json
import sys
from pathlib import Path
from typing import Callable


def _excalidraw_refs_dir() -> Path:
    """The shared excalidraw plugin's references/ dir, sibling of feinschliff/."""
    return Path(__file__).resolve().parents[3] / "excalidraw" / "references"


def strip_theme_pragma(dsl: str) -> str:
    """Strip a leading ``theme <name>`` line (case-insensitive) from DSL text.

    Pragmas like ``theme bsh`` collide with the brand-explicit theme application
    we do here; if the first non-empty non-comment line is a pragma, drop it.
    """
    lines = dsl.splitlines()
    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        parts = stripped.split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "theme":
            return "\n".join(lines[:i] + lines[i + 1:])
        return dsl
    return dsl


def render_diagram(
    dsl: str,
    slug: str,
    out_dir: Path,
    *,
    brand_root: Path,
    theme_module: str,
    theme_apply_attr: str,
) -> tuple[Path, list[str]]:
    """Run the full pipeline.

    Args:
        dsl: source DSL text.
        slug: basename without extension, e.g. ``"03-architecture-overview"``.
        out_dir: deck output directory. ``<out_dir>/diagrams/`` is created.
        brand_root: the brand pack directory (e.g. ``feinschliff/brands/feinschliff/``).
            Used to locate ``renderers/excalidraw/`` for the theme module.
        theme_module: name of the python file under ``<brand_root>/renderers/excalidraw/``,
            without the ``.py``, e.g. ``"apply_feinschliff_theme"``.
        theme_apply_attr: the attribute on that module to call, e.g.
            ``"apply_feinschliff"``. The callable must take a generic Excalidraw
            doc and return a themed copy.

    Returns:
        (png_path, validator_issues). ``png_path`` points at
        ``<out_dir>/diagrams/<slug>-<brand>.png``. ``validator_issues`` is a
        list of structural defects detected on the themed JSON.
    """
    out_dir = Path(out_dir)
    diagrams_dir = out_dir / "diagrams"
    diagrams_dir.mkdir(parents=True, exist_ok=True)

    # Bootstrap the shared excalidraw + per-brand theme module onto sys.path.
    excalidraw_refs = _excalidraw_refs_dir()
    brand_excalidraw = brand_root / "renderers" / "excalidraw"
    for p in (excalidraw_refs, brand_excalidraw):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))

    expand_dsl = importlib.import_module("expand_dsl")
    render_excalidraw = importlib.import_module("render_excalidraw")
    theme_mod = importlib.import_module(theme_module)
    apply_theme: Callable[[dict], dict] = getattr(theme_mod, theme_apply_attr)

    # Late import: validator is colocated in this package.
    from . import validator

    normalized = strip_theme_pragma(dsl)

    dsl_path = diagrams_dir / f"{slug}.dsl"
    dsl_path.write_text(normalized)

    generic_doc = expand_dsl.parse_dsl(normalized)
    generic_path = diagrams_dir / f"{slug}.excalidraw"
    generic_path.write_text(json.dumps(generic_doc, indent=2))

    themed_doc = apply_theme(copy.deepcopy(generic_doc))
    brand_slug = brand_root.name
    themed_path = diagrams_dir / f"{slug}-{brand_slug}.excalidraw"
    themed_path.write_text(json.dumps(themed_doc, indent=2))

    issues = validator.check(themed_doc)

    png_path = diagrams_dir / f"{slug}-{brand_slug}.png"
    render_excalidraw.render(
        themed_path,
        output_path=png_path,
        scale=2,
        max_width=1920,
    )
    return png_path, issues


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="DSL → brand-themed Excalidraw PNG")
    ap.add_argument("dsl_file", type=Path)
    ap.add_argument("--brand-root", type=Path, required=True)
    ap.add_argument("--theme-module", default="apply_feinschliff_theme")
    ap.add_argument("--theme-apply-attr", default="apply_feinschliff")
    ap.add_argument("--slug", default=None, help="default: dsl file stem")
    ap.add_argument("--out-dir", type=Path, default=Path("."))
    args = ap.parse_args()
    slug = args.slug or args.dsl_file.stem
    png, issues = render_diagram(
        args.dsl_file.read_text(),
        slug,
        args.out_dir,
        brand_root=args.brand_root,
        theme_module=args.theme_module,
        theme_apply_attr=args.theme_apply_attr,
    )
    if issues:
        for line in issues:
            print(f"[validator] {line}", file=sys.stderr)
    print(png)
