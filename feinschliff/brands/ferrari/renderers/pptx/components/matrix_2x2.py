"""2×2 Matrix component — McKinsey-style prioritisation grid.

Pure shape primitives; no placeholders. Layouts wrap this with editable
text placeholders for the per-cell content + axis titles.

Geometry (CSS px on the 1920 × 1080 canvas):

    grid box  →  (x, y, w, h) — passed in by caller
    cells     →  4 quadrants in reading order: TL, TR, BL, BR
    axes      →  L-shape rule on left + bottom edges (graphite)
    extremes  →  small "LOW"/"HIGH" labels at the outer ends of each axis
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN

import theme as T
from components.primitives import _shapes, add_line, add_rect, add_text
from geometry import px


# Visual constants — tuned to Feinschliff MCK reference (HTML §2×2 Matrix).
# Inner cross is now graphite at 3px so the matrix reads as an axis grid,
# not just 4 detached boxes. Arrow tips at the positive axis ends signal
# direction (impact up, effort right).
RULE_AXIS_W_PX = 2          # outer axis line weight (graphite)
RULE_INNER_W_PX = 3         # inner axis cross — graphite, thicker than before
EXTREME_OFFSET_PX = 18      # gap between axis line and "LOW/HIGH" label
EXTREME_LABEL_W_PX = 80
EXTREME_LABEL_H_PX = 22
ARROW_TIP_PX = 20           # arrow head size at positive axis ends


def add_matrix_2x2(
    target,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    cells: list[dict] | None = None,
    axis_x_low: str = "Low",
    axis_x_high: str = "High",
    axis_y_low: str = "Low",
    axis_y_high: str = "High",
    axis_color: RGBColor = T.GRAPHITE,
    inner_color: RGBColor = T.FOG,
    focus_fill: RGBColor = T.ACCENT,
    cell_fill: RGBColor | None = None,
):
    """Draw the 2×2 matrix chrome — axis lines, inner divider rules,
    LOW/HIGH extreme labels, and focus-cell fills.

    Args:
      target: Slide / SlideLayout / SlideMaster shape tree.
      x, y, w, h: grid bounding box (CSS px). Cells are split 50/50.
      cells: optional list of 4 dicts with `focus: bool` to fill the
             corresponding quadrant with `focus_fill` (subtle accent).
             Order: TL, TR, BL, BR. Other keys ignored — text is
             rendered by the layout's editable placeholders.
      axis_x_low/high, axis_y_low/high: extreme axis labels (mono caps).
      axis_color, inner_color, focus_fill, cell_fill: theme overrides.

    Returns: dict with the four cell rects keyed by position name
             ("tl", "tr", "bl", "br") for the caller to position
             placeholders against.
    """
    half_w = w / 2
    half_h = h / 2

    # ─── Cell backgrounds (focus first, so rules paint on top) ───────────
    cell_rects = {
        "tl": (x,          y,          half_w, half_h),
        "tr": (x + half_w, y,          half_w, half_h),
        "bl": (x,          y + half_h, half_w, half_h),
        "br": (x + half_w, y + half_h, half_w, half_h),
    }
    positions = ("tl", "tr", "bl", "br")
    cells = cells or []
    for pos, spec in zip(positions, cells):
        cx, cy, cw, ch = cell_rects[pos]
        is_focus = bool(spec.get("focus"))
        if is_focus:
            add_rect(target, cx, cy, cw, ch, fill=focus_fill)
        elif cell_fill is not None:
            add_rect(target, cx, cy, cw, ch, fill=cell_fill)

    # ─── Inner cross — graphite, thick. Defines the matrix as an axis grid,
    # not four detached boxes. Paint AFTER cell fills so it lies on top.
    add_line(target, x + half_w - RULE_INNER_W_PX / 2, y,
             RULE_INNER_W_PX, h, axis_color)
    add_line(target, x, y + half_h - RULE_INNER_W_PX / 2,
             w, RULE_INNER_W_PX, axis_color)

    # ─── Outer axes — left edge (y-axis) + bottom edge (x-axis) ──────────
    add_line(target, x - RULE_AXIS_W_PX, y,
             RULE_AXIS_W_PX, h + RULE_AXIS_W_PX, axis_color)
    add_line(target, x - RULE_AXIS_W_PX, y + h,
             w + RULE_AXIS_W_PX, RULE_AXIS_W_PX, axis_color)

    # ─── Arrow tips at the positive axis ends — conveys direction. ────────
    # Y-axis arrow: triangle pointing UP at the top of the y-axis.
    y_arrow = _shapes(target).add_shape(
        MSO_SHAPE.ISOSCELES_TRIANGLE,
        px(x - RULE_AXIS_W_PX - ARROW_TIP_PX / 2), px(y - ARROW_TIP_PX),
        px(ARROW_TIP_PX), px(ARROW_TIP_PX),
    )
    y_arrow.fill.solid()
    y_arrow.fill.fore_color.rgb = axis_color
    y_arrow.line.fill.background()
    # X-axis arrow: triangle pointing RIGHT at the right of the x-axis.
    x_arrow = _shapes(target).add_shape(
        MSO_SHAPE.RIGHT_TRIANGLE,
        px(x + w), px(y + h - ARROW_TIP_PX / 2 + RULE_AXIS_W_PX / 2),
        px(ARROW_TIP_PX), px(ARROW_TIP_PX),
    )
    x_arrow.rotation = 270  # RIGHT_TRIANGLE's hypotenuse faces up-left; rotate so point is right
    x_arrow.fill.solid()
    x_arrow.fill.fore_color.rgb = axis_color
    x_arrow.line.fill.background()

    # ─── Extreme labels: LOW/HIGH on each axis ───────────────────────────
    # x-axis: LOW at left of the bottom edge, HIGH at right.
    label_y = y + h + EXTREME_OFFSET_PX
    add_text(
        target, x, label_y, EXTREME_LABEL_W_PX, EXTREME_LABEL_H_PX,
        axis_x_low, size_px=14, weight="bold", font=T.FONT_DISPLAY,
        color=axis_color, uppercase=True, tracking_em=0.14,
    )
    add_text(
        target, x + w - EXTREME_LABEL_W_PX, label_y,
        EXTREME_LABEL_W_PX, EXTREME_LABEL_H_PX,
        axis_x_high, size_px=14, weight="bold", font=T.FONT_DISPLAY,
        color=axis_color, uppercase=True, tracking_em=0.14,
        align=PP_ALIGN.RIGHT,
    )

    # y-axis: LOW at the bottom of the left edge, HIGH at the top.
    label_x = x - EXTREME_OFFSET_PX - EXTREME_LABEL_W_PX
    add_text(
        target, label_x, y + h - EXTREME_LABEL_H_PX,
        EXTREME_LABEL_W_PX, EXTREME_LABEL_H_PX,
        axis_y_low, size_px=14, weight="bold", font=T.FONT_DISPLAY,
        color=axis_color, uppercase=True, tracking_em=0.14,
        align=PP_ALIGN.RIGHT,
    )
    add_text(
        target, label_x, y, EXTREME_LABEL_W_PX, EXTREME_LABEL_H_PX,
        axis_y_high, size_px=14, weight="bold", font=T.FONT_DISPLAY,
        color=axis_color, uppercase=True, tracking_em=0.14,
        align=PP_ALIGN.RIGHT,
    )

    return cell_rects
