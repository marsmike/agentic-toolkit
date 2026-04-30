"""Higher-level Feinschliff components composed from `primitives`.

This module is the SVG counterpart to the PPTX renderer's `components/`
package. Every helper here is used by at least one layout — no dead code.

Included:
  - `canvas_background` — paints the full-bleed background rect
  - `rule` — 80×4 accent/black/etc. keyline used above headers
  - `eyebrow` — mono uppercase label
  - `title` — display headline with line-height + tracking
  - `body` — paragraph text (graphite, 1.5 line-height)
  - `kpi_value_unit` — KPI value (big light) + small graphite unit as a
    single text element with two `<tspan>` runs
  - `kpi_key` / `kpi_delta` — the mono labels beneath a KPI value
"""
from __future__ import annotations

from xml.etree.ElementTree import Element, SubElement

import theme as T
from primitives import num, rect, text


def canvas_background(parent: Element, *, fill: str) -> Element:
    """Full-bleed 1920×1080 background rectangle."""
    from geometry import CANVAS_W, CANVAS_H
    return rect(parent, 0, 0, CANVAS_W, CANVAS_H, fill=fill)


def rule(parent: Element, x: float, y: float, *,
         width: float = 80, height: float = 4, color: str | None = None) -> Element:
    """Feinschliff signature 80×4 keyline. Defaults to black (light variant)."""
    return rect(parent, x, y, width, height, fill=color or T.HEX["black"])


def eyebrow(parent: Element, x: float, y: float, content: str, *,
            color: str | None = None) -> Element:
    """Mono uppercase label — 18px graphite-ish by default, 0.12em tracking."""
    return text(
        parent, x, y, content,
        size_px=T.SIZE_PX["eyebrow"],
        weight=T.WEIGHT["regular"],
        color=color or T.HEX["black"],
        font=T.FONT_MONO,
        tracking_em=0.12,
        uppercase=True,
    )


def title(parent: Element, x: float, y: float, content: str, *,
          size_px: int | None = None, weight: str = "bold",
          color: str | None = None, tracking_em: float = -0.015,
          line_height: float = 1.1) -> Element:
    """Display headline."""
    return text(
        parent, x, y, content,
        size_px=size_px if size_px is not None else T.SIZE_PX["slide_title"],
        weight=weight,
        color=color or T.HEX["black"],
        tracking_em=tracking_em,
        line_height=line_height,
    )


def body(parent: Element, x: float, y: float, content: str, *,
         size_px: int | None = None, color: str | None = None,
         line_height: float = 1.5) -> Element:
    """Paragraph copy (graphite, 22px default, 1.5 lh)."""
    return text(
        parent, x, y, content,
        size_px=size_px if size_px is not None else T.SIZE_PX["col_body"],
        weight=T.WEIGHT["regular"],
        color=color or T.HEX["graphite"],
        line_height=line_height,
    )


def kpi_value_unit(parent: Element, x: float, y: float, value: str, unit: str) -> Element:
    """KPI cell headline: big Noto Sans Light value + small graphite unit.

    Rendered as a single `<text>` with two `<tspan>` runs so the unit
    baseline aligns with the value baseline (same anchor y).
    """
    value_size = T.SIZE_PX["kpi_value"]
    unit_size = T.SIZE_PX["kpi_unit"]
    baseline_y = y + value_size * 0.82

    el = SubElement(parent, "text", {
        "x": num(x),
        "y": num(baseline_y),
        "font-family": T.FONT_DISPLAY,
        "text-anchor": "start",
    })

    val_tspan = SubElement(el, "tspan", {
        "fill": T.HEX["black"],
        "font-size": num(value_size),
        "font-weight": str(T.WEIGHT["light"]),
        "letter-spacing": "-0.03em",
    })
    val_tspan.text = value

    if unit:
        unit_tspan = SubElement(el, "tspan", {
            "fill": T.HEX["graphite"],
            "font-size": num(unit_size),
            "font-weight": str(T.WEIGHT["regular"]),
            # Preserve any leading space in unit (e.g. " bn") — XML strips
            # runs of whitespace between tspans otherwise.
            "{http://www.w3.org/XML/1998/namespace}space": "preserve",
        })
        unit_tspan.text = unit
    return el


def kpi_key(parent: Element, x: float, y: float, content: str) -> Element:
    return text(
        parent, x, y, content,
        size_px=T.SIZE_PX["kpi_key"],
        weight=T.WEIGHT["regular"],
        color=T.HEX["graphite"],
        font=T.FONT_MONO,
        tracking_em=0.1,
        uppercase=True,
    )


def kpi_delta(parent: Element, x: float, y: float, content: str) -> Element:
    return text(
        parent, x, y, content,
        size_px=T.SIZE_PX["kpi_delta"],
        weight=T.WEIGHT["regular"],
        color=T.HEX["accent_hover"],
        font=T.FONT_MONO,
    )


def column_label_stack(parent: Element, x: float, y: float, *,
                       number: str, title_text: str, body_text: str) -> None:
    """Column rhythm: orange mono number → medium title → graphite body.

    Used by multi-column card layouts. Callers that want wrapping must
    pre-break lines with `\\n` (SVG text isn't a bounded box).
    """
    text(
        parent, x, y, number,
        size_px=T.SIZE_PX["col_num"],
        weight=T.WEIGHT["regular"],
        color=T.HEX["accent"],
        font=T.FONT_MONO,
        tracking_em=0.12,
        uppercase=True,
    )
    title(
        parent, x, y + 44, title_text,
        size_px=T.SIZE_PX["col_title"],
        weight="medium",
        tracking_em=-0.012,
        line_height=1.15,
    )
    body(
        parent, x, y + 220, body_text,
        size_px=T.SIZE_PX["col_body"],
        line_height=1.5,
    )
