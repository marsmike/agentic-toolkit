#!/usr/bin/env python3
# Canonical location. Imported by excalidraw/references/expand_dsl.py
# (via a sys.path insert) when a DSL file starts with `theme bsh`.
"""
Apply the Feinschliff theme to an .excalidraw JSON file produced by expand_dsl.py.

Recolors elements using the Feinschliff palette (see color-palette-feinschliff.md),
sets sharp corners on all shapes (Feinschliff is a hard-edge system),
and remaps text colors per the hierarchy rules.

Palette source: brands/feinschliff/tokens.json. This module reads it once at
import time; when tokens change the remaps here follow automatically.

Usage:
    uv run python apply_feinschliff_theme.py <file.excalidraw>

Output:
    <file>-bsh.excalidraw in the same directory.
"""

import json
import sys
from pathlib import Path


_TOKENS_PATH = Path(__file__).resolve().parents[2] / "tokens.json"


def _load_palette() -> dict[str, str]:
    """Semantic token name → uppercase hex including leading '#'.

    Mirrors the projection used by brands/feinschliff/renderers/pptx/theme.py.
    DTCG color group is flat under tokens["color"]; $type / $description
    scaffolding entries are skipped by the startswith("$") filter.
    """
    with _TOKENS_PATH.open() as f:
        tokens = json.load(f)
    return {
        name: token["$value"].upper()
        for name, token in tokens["color"].items()
        if not name.startswith("$")
    }


T = _load_palette()


# Map of source fill (from expand_dsl.py SHAPE_COLORS) → Feinschliff (fill, stroke, text-on-fill, dashed).
# Left-hand hexes are excalidraw-generic input; right-hand values are sourced from tokens.json.
FILL_TO_FEINSCHLIFF = {
    # old_fill (                  fill,             stroke,           text_color,       dashed)
    "#3b82f6":                   (T["white"],      T["ink"],         T["ink"],         False),  # primary
    "#60a5fa":                   (T["paper"],      T["ink"],         T["ink"],         False),  # secondary
    "#93c5fd":                   (T["fog"],        T["graphite"],    T["ink"],         False),  # tertiary
    "#fed7aa":                   (T["accent"],     T["black"],       T["black"],       False),  # start (accent hero)
    "#a7f3d0":                   (T["black"],      T["black"],       T["white"],       False),  # end (black)
    "#fee2e2":                   (T["highlight"],  T["black"],       T["black"],       False),  # warning
    "#fef3c7":                   (T["highlight"],  T["black"],       T["black"],       False),  # decision
    "#ddd6fe":                   (T["ink"],        T["accent"],      T["white"],       False),  # ai (ink + accent border)
    "#dbeafe":                   (T["paper"],      T["silver"],      T["graphite"],    True),   # inactive (dashed silver)
    "#fecaca":                   (T["accent"],     T["black"],       T["black"],       False),  # error
    "#1e293b":                   (T["black"],      T["accent"],      T["white"],       False),  # code/data
}


# Map of source text color (TEXT_COLORS from expand_dsl.py) → Feinschliff text color.
# Used for free-floating text (title / subtitle / body / detail).
TEXT_TO_FEINSCHLIFF = {
    "#1e40af": T["black"],     # title → black
    "#3b82f6": T["accent"],    # subtitle → accent (signature)
    "#64748b": T["graphite"],  # body/detail → graphite
    "#374151": T["ink"],       # on-light → ink
    "#ffffff": T["white"],     # on-dark → stays white
}


# Map for line/arrow/dot stroke remaps (keys normalized to lowercase).
STROKE_TO_FEINSCHLIFF = {
    # Shape strokes (already handled per-element, but arrow strokes are copied from source).
    "#1e3a5f": T["ink"],      # most shape strokes → ink
    "#c2410c": T["black"],    # start stroke → black
    "#047857": T["black"],    # end stroke → black
    "#dc2626": T["black"],    # warning stroke → black
    "#b45309": T["black"],    # decision stroke → black
    "#6d28d9": T["accent"],   # ai stroke → accent
    "#1e40af": T["black"],    # inactive stroke → treated as ink (black used for contrast)
    "#b91c1c": T["black"],    # error stroke → black
    "#334155": T["accent"],   # code stroke → accent
    # Line default stroke.
    "#64748b": T["ink"],      # line gray → ink
    "#86868b": T["ink"],      # line gray (dark theme) → ink
}


def norm(color: str) -> str:
    """Lowercase hex for comparison."""
    return color.lower() if isinstance(color, str) else color


def apply_feinschliff(data: dict) -> dict:
    """Transform the excalidraw JSON in-place. Returns the same dict."""
    # First pass — index text elements by their containerId so we can
    # rewrite their color when the container is recolored.
    elements = data.get("elements", [])
    text_by_container = {}
    for el in elements:
        if el.get("type") == "text" and el.get("containerId"):
            text_by_container[el["containerId"]] = el

    # Second pass — recolor each element.
    for el in elements:
        t = el.get("type")
        if t in ("rectangle", "ellipse", "diamond"):
            # Shape: remap via background fill
            bg = norm(el.get("backgroundColor"))
            if bg in FILL_TO_FEINSCHLIFF:
                new_fill, new_stroke, new_text, dashed = FILL_TO_FEINSCHLIFF[bg]
                el["backgroundColor"] = new_fill
                el["strokeColor"] = new_stroke
                if dashed:
                    el["strokeStyle"] = "dashed"
                # Retarget bound text
                bound_text = text_by_container.get(el.get("id"))
                if bound_text is not None:
                    bound_text["strokeColor"] = new_text
                    # Feinschliff body text inside containers: mono @ 16px is already correct
            # Sharp corners for all shapes (Feinschliff hard-edge aesthetic)
            if "roundness" in el:
                el["roundness"] = None
            # Thin 1px borders (Feinschliff design-system default)
            # Dots (small ellipses originally strokeWidth 1) stay thin
            if el.get("strokeWidth", 2) >= 2:
                el["strokeWidth"] = 1
        elif t == "text":
            # Only free-floating text (no container) gets the TEXT_TO_FEINSCHLIFF remap —
            # container-bound text is handled above when the container is recolored.
            if not el.get("containerId"):
                stroke = norm(el.get("strokeColor"))
                if stroke in TEXT_TO_FEINSCHLIFF:
                    el["strokeColor"] = TEXT_TO_FEINSCHLIFF[stroke]
        elif t == "line":
            stroke = norm(el.get("strokeColor"))
            if stroke in STROKE_TO_FEINSCHLIFF:
                el["strokeColor"] = STROKE_TO_FEINSCHLIFF[stroke]
        elif t == "arrow":
            stroke = norm(el.get("strokeColor"))
            if stroke in STROKE_TO_FEINSCHLIFF:
                el["strokeColor"] = STROKE_TO_FEINSCHLIFF[stroke]
        elif t == "ellipse":
            # Already handled above for shape path, but dots are just small ellipses.
            # Dots have stroke == fill from expand_dsl.py. Remap stroke via FILL_TO_FEINSCHLIFF.
            pass

    # Canvas background stays white (already default).
    if "appState" in data:
        data["appState"]["viewBackgroundColor"] = "#FFFFFF"

    return data


def main() -> int:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <file.excalidraw>", file=sys.stderr)
        return 2

    src = Path(sys.argv[1])
    if not src.exists():
        print(f"error: {src} not found", file=sys.stderr)
        return 1

    with src.open() as f:
        data = json.load(f)

    apply_feinschliff(data)

    dst = src.with_name(src.stem + "-bsh" + src.suffix)
    with dst.open("w") as f:
        json.dump(data, f, indent=2)

    print(str(dst))
    return 0


if __name__ == "__main__":
    sys.exit(main())
