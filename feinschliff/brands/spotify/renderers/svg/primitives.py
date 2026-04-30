"""Low-level SVG element builders — thin wrappers over xml.etree.ElementTree.

Each builder returns the created `Element`, already appended to `parent`.
Coordinates are CSS px inside a 1920×1080 viewBox. Colours are "#RRGGBB"
strings from `theme.HEX`. Typography options (size, weight, tracking,
line-height, uppercase) are applied in-line as SVG attributes or styles.

These primitives stay small and composable; higher-level components live
in `components.py` and assemble multiple primitives.
"""
from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement

import theme as T

SVG_NS = "http://www.w3.org/2000/svg"


def svg_root(*, width: int, height: int, viewBox: str) -> Element:
    """Create a standalone SVG root element with the Feinschliff canvas viewBox."""
    root = Element(
        "svg",
        {
            "xmlns": SVG_NS,
            "viewBox": viewBox,
            "width": str(width),
            "height": str(height),
            "preserveAspectRatio": "xMidYMid meet",
        },
    )
    return root


def group(parent: Element, *, id_: str | None = None, transform: str | None = None) -> Element:
    attrs: dict[str, str] = {}
    if id_:
        attrs["id"] = id_
    if transform:
        attrs["transform"] = transform
    return SubElement(parent, "g", attrs)


def rect(
    parent: Element,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str | None = None,
    stroke: str | None = None,
    stroke_width: float | None = None,
) -> Element:
    attrs: dict[str, str] = {
        "x": num(x),
        "y": num(y),
        "width": num(w),
        "height": num(h),
    }
    attrs["fill"] = fill if fill is not None else "none"
    if stroke is not None:
        attrs["stroke"] = stroke
        attrs["stroke-width"] = num(stroke_width if stroke_width is not None else 1)
    return SubElement(parent, "rect", attrs)


def line(
    parent: Element,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str,
) -> Element:
    """Feinschliff rules/dividers are filled rects (matches PPTX renderer convention)."""
    return rect(parent, x, y, w, h, fill=fill)


def text(
    parent: Element,
    x: float,
    y: float,
    content: str,
    *,
    size_px: float,
    weight: int | str = 400,
    color: str = "#000000",
    font: str | None = None,
    anchor: str = "start",        # "start" | "middle" | "end"
    tracking_em: float = 0,
    line_height: float = 1.0,
    uppercase: bool = False,
) -> Element:
    """Emit a `<text>` element.

    SVG baseline math: `<text y>` is the text baseline, not the top. The
    caller passes y as the visual top (matching the PPTX renderer's coord
    convention) and we shift baseline-down by ~0.82 * size so ascenders
    sit inside the y position. Multi-line content becomes one parent
    `<text>` with `<tspan>` children using dy for line spacing.
    """
    family = font or T.FONT_DISPLAY
    baseline_y = y + size_px * 0.82

    weight_attr = str(weight) if isinstance(weight, int) else _weight_name_to_num(weight)

    attrs: dict[str, str] = {
        "x": num(x),
        "y": num(baseline_y),
        "fill": color,
        "font-family": family,
        "font-size": num(size_px),
        "font-weight": weight_attr,
        "text-anchor": anchor,
    }
    if tracking_em:
        attrs["letter-spacing"] = f"{tracking_em}em"

    el = SubElement(parent, "text", attrs)

    lines = content.split("\n")
    for i, ln in enumerate(lines):
        line_text = ln.upper() if uppercase else ln
        tspan = SubElement(el, "tspan", {"x": num(x)})
        if i > 0:
            tspan.set("dy", f"{line_height}em")
        tspan.text = line_text
    return el


def num(n: float) -> str:
    """Render a number with minimal noise (no trailing .0 for integers).

    Public because `components.py` and `layouts/_shared.py` both need
    to emit SVG attribute numbers in the same canonical form.
    """
    if isinstance(n, int):
        return str(n)
    if float(n).is_integer():
        return str(int(n))
    return f"{n:.3f}".rstrip("0").rstrip(".")


# ─── internal ──────────────────────────────────────────────────────────────

_WEIGHT_NAME_TO_NUM = {
    "light": 300,
    "regular": 400,
    "normal": 400,
    "medium": 500,
    "bold": 700,
}


def _weight_name_to_num(name: str) -> str:
    return str(_WEIGHT_NAME_TO_NUM.get(name, 400))
