"""Venn component — 3-circle strategic overlap diagram.

A Venn visualises the sweet-spot where 2–3 capabilities / audiences /
domains intersect. Each circle is a set; overlap regions call out the
pairwise and centre-of-three intersections by name.

Design notes
------------
- Circles are `MSO_SHAPE.OVAL` filled with semi-transparent Feinschliff palette
  colours (orange, ink, graphite). Alpha is injected directly into the
  `<a:solidFill><a:srgbClr>` tree because python-pptx does not expose
  `Fill.transparency` as a writable property. Two overlapping 50%-alpha
  circles mix visibly on a white background.
- Outlines are sharp (2 px, T.INK) — mandatory in Feinschliff.
- The component draws the circles and (optional) outer set labels +
  centre sweet-spot marker. Pairwise + centre **text labels** are left
  to the layout, which wraps them in editable placeholders.

Geometry
--------
Mirrors the HTML reference (`brands/feinschliff/claude-design/feinschliff-2026.html`,
§31 MCK · Venn) which uses a 900×540 SVG viewBox with circles at
(320,220), (560,220), (440,400) with r=170. The caller passes a
bounding box; we map the viewBox to it proportionally so callers
can resize without recomputing geometry.
"""
from __future__ import annotations

from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.oxml.ns import qn
from pptx.util import Pt

import theme as T
from geometry import px
from components.primitives import _shapes, add_text


# ─── Reference geometry (SVG viewBox 900 × 540) ────────────────────────────
# Mirrors the HTML reference so Feinschliff visual language stays consistent across
# renderers. Callers pass their own bounding box; we rescale.
_VB_W = 900.0
_VB_H = 540.0

# Set → (cx, cy) in viewBox coordinates. Classic 3-circle Venn geometry:
# two circles up top, one below-centre.
_SET_CENTERS = {
    "A": (320.0, 220.0),  # top-left
    "B": (560.0, 220.0),  # top-right
    "C": (440.0, 400.0),  # bottom-centre
}
_SET_RADIUS = 170.0  # ~35% overlap with the other circles at this spacing

# Pairwise + centre intersection anchor points in viewBox coords.
_INTERSECTION_CENTERS = {
    ("A", "B"):      (440.0, 215.0),   # between top pair
    ("A", "C"):      (320.0, 320.0),   # between orange + gray
    ("B", "C"):      (560.0, 320.0),   # between ink    + gray
    ("A", "B", "C"): (440.0, 285.0),   # centre "sweet spot"
}

# Outer set-label anchor points (outside each circle, on its far side).
_OUTER_LABEL_CENTERS = {
    "A": (180.0, 120.0),   # top-left · outside orange
    "B": (700.0, 120.0),   # top-right · outside ink
    "C": (440.0, 505.0),   # bottom · outside graphite
}

# Centre-of-three highlight marker (a small paper-fill circle with an
# ink hairline, so the "sweet spot" reads as a distinct landmark).
_CENTER_MARKER_R = 52.0

# Defaults — Feinschliff palette. Orange / ink / graphite mix pleasantly at 50%.
_DEFAULT_COLORS = (T.ACCENT, T.INK, T.GRAPHITE)
_DEFAULT_ALPHA = 50_000       # OOXML alpha: 0..100_000 (100000 = opaque)
_STROKE_WIDTH_PX = 2           # sharp Feinschliff outline
_OUTER_LABEL_W_PX = 240
_OUTER_LABEL_H_PX = 24


# ─── Public API ────────────────────────────────────────────────────────────
def add_venn(
    target,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    *,
    sets: list[dict] | None = None,
    intersections: list[dict] | None = None,
    colors: tuple[RGBColor, RGBColor, RGBColor] = _DEFAULT_COLORS,
    stroke_color: RGBColor = T.INK,
    alpha: int = _DEFAULT_ALPHA,
    draw_outer_labels: bool = True,
    draw_center_marker: bool = True,
):
    """Draw a 3-circle Venn into the bounding box `(x_px, y_px, w_px, h_px)`.

    Args:
        target: Slide / SlideLayout / SlideMaster shape host.
        x_px, y_px, w_px, h_px: bounding box in CSS px. The reference
            viewBox (900×540) is mapped proportionally onto this box.
        sets: optional list of up to 3 set dicts. Keys used here:
              `name` (drawn as outer label if `draw_outer_labels`),
              `subtitle` (mono caption below the name).
              Extra fields (e.g. alignment to A/B/C) are ignored — the
              layout chooses which dict maps to which circle by order.
        intersections: kept for API symmetry; this component does NOT
              render intersection text (the layout places editable
              text placeholders on top of the shape stack). Reserved
              for future use (e.g. highlight an intersection region).
        colors: 3 RGBColors (circle A, B, C). Defaults to Feinschliff palette.
        stroke_color: outline colour (sharp-edged, 2 px).
        alpha: per-circle alpha 0..100_000 (OOXML units).
              50_000 (=50 %) lets overlaps mix visibly on white.
        draw_outer_labels: if True and `sets` supplied, draw mono
              uppercase labels + optional mono subtitles outside each
              circle on its far side.
        draw_center_marker: if True, draw the small centre highlight
              circle (paper fill, ink hairline) for the sweet spot.

    Returns:
        dict with the absolute CSS-px positions the layout needs:
            {
              "circles": {"A": {"cx", "cy", "r"}, "B": ..., "C": ...},
              "intersections": {
                  ("A","B"): (cx, cy),
                  ("A","C"): (cx, cy),
                  ("B","C"): (cx, cy),
                  ("A","B","C"): (cx, cy),
              },
              "outer_labels": {"A": (cx, cy), ...},
            }
    """
    sx = w_px / _VB_W   # x scale factor
    sy = h_px / _VB_H   # y scale factor

    def _map(cx_vb: float, cy_vb: float) -> tuple[float, float]:
        return x_px + cx_vb * sx, y_px + cy_vb * sy

    # Circles — draw in set order A, B, C so z-order is predictable.
    circle_geom: dict[str, dict] = {}
    for key, color in zip(("A", "B", "C"), colors):
        cx_vb, cy_vb = _SET_CENTERS[key]
        cx, cy = _map(cx_vb, cy_vb)
        # Non-uniform scaling would distort circles into ovals. We use the
        # smaller of sx/sy to keep them round, and centre the result on the
        # mapped centre point.
        r = _SET_RADIUS * min(sx, sy)
        _draw_circle(
            target,
            cx_px=cx, cy_px=cy, r_px=r,
            fill_color=color, alpha=alpha,
            stroke_color=stroke_color, stroke_w_px=_STROKE_WIDTH_PX,
        )
        circle_geom[key] = {"cx": cx, "cy": cy, "r": r}

    # Centre sweet-spot marker — drawn AFTER the circles so it paints on top.
    if draw_center_marker:
        cx_vb, cy_vb = _INTERSECTION_CENTERS[("A", "B", "C")]
        cx, cy = _map(cx_vb, cy_vb)
        r = _CENTER_MARKER_R * min(sx, sy)
        _draw_circle(
            target,
            cx_px=cx, cy_px=cy, r_px=r,
            fill_color=T.PAPER, alpha=100_000,
            stroke_color=T.INK, stroke_w_px=_STROKE_WIDTH_PX,
        )

    # Outer labels — mono uppercase + optional subtitle, centred at the
    # anchor point for each set.
    if draw_outer_labels and sets:
        for key, spec in zip(("A", "B", "C"), sets):
            if spec is None:
                continue
            name = spec.get("name", "")
            if not name:
                continue
            cx_vb, cy_vb = _OUTER_LABEL_CENTERS[key]
            cx, cy = _map(cx_vb, cy_vb)
            # Centre the text box horizontally on the anchor.
            lx = cx - _OUTER_LABEL_W_PX / 2
            add_text(
                target, lx, cy - _OUTER_LABEL_H_PX / 2,
                _OUTER_LABEL_W_PX, _OUTER_LABEL_H_PX,
                name,
                size_px=T.SIZE_PX["eyebrow"], weight="bold", font=T.FONT_DISPLAY,
                color=T.BLACK, uppercase=True, tracking_em=0.1,
                align=_center_align(),
            )
            subtitle = spec.get("subtitle")
            if subtitle:
                add_text(
                    target, lx, cy + _OUTER_LABEL_H_PX / 2 + 2,
                    _OUTER_LABEL_W_PX, _OUTER_LABEL_H_PX,
                    subtitle,
                    size_px=14, weight="bold", font=T.FONT_DISPLAY,
                    color=T.GRAPHITE, uppercase=False, tracking_em=0.08,
                    align=_center_align(),
                )

    # Compute mapped intersection points so the caller can place editable
    # text placeholders on top.
    intersections_px: dict[tuple, tuple[float, float]] = {}
    for key, (cx_vb, cy_vb) in _INTERSECTION_CENTERS.items():
        intersections_px[key] = _map(cx_vb, cy_vb)

    outer_labels_px: dict[str, tuple[float, float]] = {
        key: _map(*pos) for key, pos in _OUTER_LABEL_CENTERS.items()
    }

    return {
        "circles": circle_geom,
        "intersections": intersections_px,
        "outer_labels": outer_labels_px,
    }


# ─── Internals ─────────────────────────────────────────────────────────────
def _draw_circle(
    target,
    *,
    cx_px: float,
    cy_px: float,
    r_px: float,
    fill_color: RGBColor,
    alpha: int,
    stroke_color: RGBColor,
    stroke_w_px: float,
):
    """Emit an MSO_SHAPE.OVAL with semi-transparent solid fill."""
    d = r_px * 2
    shape = _shapes(target).add_shape(
        MSO_SHAPE.OVAL,
        px(cx_px - r_px), px(cy_px - r_px),
        px(d), px(d),
    )

    # Solid fill with alpha injection (python-pptx can't set alpha).
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    if 0 < alpha < 100_000:
        _apply_fill_alpha(shape, alpha)

    # Sharp Feinschliff outline.
    shape.line.color.rgb = stroke_color
    shape.line.width = px(stroke_w_px)

    shape.shadow.inherit = False
    return shape


def _apply_fill_alpha(shape, alpha: int):
    """Inject `<a:alpha val="..."/>` into the shape's solidFill/srgbClr.

    python-pptx exposes `shape.fill.solid()` and `fill.fore_color.rgb = ...`
    but not the alpha child element. We walk the spPr XML directly.
    """
    spPr = shape.fill._xPr  # <p:spPr> or <p:grpSpPr>
    solidFill = spPr.find(qn("a:solidFill"))
    if solidFill is None:
        return
    srgb = solidFill.find(qn("a:srgbClr"))
    if srgb is None:
        return
    # Remove any existing alpha so re-calls stay idempotent.
    for existing in srgb.findall(qn("a:alpha")):
        srgb.remove(existing)
    alpha_el = etree.SubElement(srgb, qn("a:alpha"))
    alpha_el.set("val", str(int(alpha)))


def _center_align():
    """Return PP_ALIGN.CENTER — imported lazily to keep the module lean."""
    from pptx.enum.text import PP_ALIGN
    return PP_ALIGN.CENTER
