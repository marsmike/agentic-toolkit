"""Line chart component — 1–3 polyline series with axes, ticks, gridlines, dots.

Pure renderer. The hosting layout is responsible for the title, eyebrow,
legend (separate from the chart frame), figure caption, and source line —
this component only paints the chart itself inside its bounding box.

Layout inside the bounding box (CSS px, top-left origin):

    +-----------------------------------------------------+
    | Y |                                                  |  <- top headroom
    | l |        ----- gridline (T.FOG)  ---------         |
    | a |    ●…………                                         |
    | b |          \\                                       |
    | s |    ●------●---------●                            |
    | . |                       \\                          |
    |   +----------------------------------------------+   |  <- x-axis (T.INK)
    | tick   tick    tick   tick   tick               |       <- x-labels (mono)
    +-----------------------------------------------------+

Margins inside the box:
  AXIS_LEFT_PX     : 56  — width reserved for y-axis tick labels
  AXIS_BOTTOM_PX   : 50  — height for x-axis line + category labels
  AXIS_TOP_PX      : 24  — headroom so the topmost data point can breathe
  AXIS_RIGHT_PX    : 16  — small padding on the right edge

Polyline technique: python-pptx exposes `shapes.build_freeform(start_x, start_y)`
which returns a freeform builder. We feed it `add_line_segments([(x, y), ...])`
and call `.convert_to_shape()` to commit a single MSO_SHAPE.FREEFORM that
holds the whole polyline. Result is a sharp, segmented stroke (no curves) —
exactly the Feinschliff look. One shape per series instead of N small lines.
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Pt

import theme as T
from geometry import px
from components.primitives import _shapes, add_rect, add_text


# ─── Layout constants (px inside the chart bbox) ──────────────────────────
AXIS_LEFT_PX = 56
AXIS_BOTTOM_PX = 50
AXIS_TOP_PX = 24
AXIS_RIGHT_PX = 16

GRIDLINE_PX = 1
AXIS_LINE_PX = 2

# Series styling. Series 1 is the accent (orange, slightly thicker stroke);
# series 2/3 are neutral darks. Stroke widths are in CSS px (matches HTML
# .line-a stroke-width: 3 / .line-b stroke-width: 2).
SERIES_COLORS = (T.ACCENT, T.INK, T.GRAPHITE)
SERIES_STROKE_PX = (3.0, 2.0, 2.0)
DOT_DIAMETER_PX = 10  # HTML uses r=5 → diameter 10

# Y-axis tick count (5 lines including 0 and y_max — 4 internal gridlines).
Y_TICKS = 5


def add_line_chart(
    target,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    series: list[dict],
    *,
    x_labels: list[str] | None = None,
    y_max: float | None = None,
):
    """Render a 1–3-series line chart inside (x_px, y_px, w_px, h_px).

    `series` is a list of dicts with keys:
        name   : str       — used for sizing only; rendered by the layout's legend
        values : list[num] — must all share the same length

    `x_labels` (optional): one string per data point along the x-axis.
        If omitted, x-axis labels are skipped (the layout may render its own).

    `y_max` (optional): force the y-axis upper bound. If omitted, derived
        from data (max of all series values, rounded up to a nice tick).
    """
    if not series:
        return

    n_points = len(series[0]["values"])
    if n_points < 2:
        return  # need at least two points to draw a line

    # ─── Compute data bounds ───
    all_values = [v for s in series for v in s["values"]]
    data_max = max(all_values)
    data_min = min(0, min(all_values))  # baseline at 0 unless data dips lower
    if y_max is None:
        y_max = _nice_ceiling(data_max)
    y_min = data_min

    # ─── Inner chart area (where the polylines live) ───
    chart_x0 = x_px + AXIS_LEFT_PX
    chart_y0 = y_px + AXIS_TOP_PX
    chart_x1 = x_px + w_px - AXIS_RIGHT_PX
    chart_y1 = y_px + h_px - AXIS_BOTTOM_PX
    chart_w = chart_x1 - chart_x0
    chart_h = chart_y1 - chart_y0

    # ─── Y gridlines + tick labels ───
    for i in range(Y_TICKS):
        ratio = i / (Y_TICKS - 1)
        gy = chart_y1 - ratio * chart_h
        # Gridline (skip the bottom one — the x-axis sits there).
        if i > 0:
            add_rect(target, chart_x0, gy - GRIDLINE_PX / 2,
                     chart_w, GRIDLINE_PX, fill=T.FOG)
        tick_value = y_min + ratio * (y_max - y_min)
        add_text(
            target,
            x_px, gy - 11,            # vertical-center the 22-px label band
            AXIS_LEFT_PX - 8, 22,
            _format_tick(tick_value),
            size_px=14, font=T.FONT_MONO, color=T.GRAPHITE,
            align=PP_ALIGN.RIGHT, tracking_em=0.08, uppercase=True,
        )

    # ─── X-axis line ───
    add_rect(target, chart_x0, chart_y1 - AXIS_LINE_PX / 2,
             chart_w, AXIS_LINE_PX, fill=T.INK)

    # ─── X tick labels ───
    if x_labels:
        n_lab = len(x_labels)
        for i, label in enumerate(x_labels):
            cx = _x_for_index(i, n_lab, chart_x0, chart_w)
            tw = 120
            add_text(
                target, cx - tw / 2, chart_y1 + 14, tw, 22, label,
                size_px=14, font=T.FONT_MONO, color=T.GRAPHITE,
                align=PP_ALIGN.CENTER, tracking_em=0.08, uppercase=True,
            )

    # ─── Series polylines + dots ───
    for s_idx, s in enumerate(series[:3]):
        color = SERIES_COLORS[s_idx]
        stroke_px = SERIES_STROKE_PX[s_idx]
        values = s["values"]
        points = [
            (
                _x_for_index(i, n_points, chart_x0, chart_w),
                _y_for_value(v, y_min, y_max, chart_y0, chart_h),
            )
            for i, v in enumerate(values)
        ]
        _add_polyline(target, points, color=color, stroke_px=stroke_px)
        for (cx, cy) in points:
            _add_dot(target, cx, cy, color=color)


# ─── Polyline + dot helpers ───────────────────────────────────────────────
def _add_polyline(target, points: list[tuple[float, float]], *,
                  color: RGBColor, stroke_px: float):
    """Commit a single freeform shape that walks through every point.

    python-pptx `build_freeform(x, y)` opens a builder at the start point;
    `add_line_segments([(x, y), ...])` pushes additional vertices; the final
    `convert_to_shape()` call writes the OOXML and returns the shape so we
    can style its line.
    """
    if len(points) < 2:
        return None
    sh = _shapes(target)
    x0, y0 = points[0]
    builder = sh.build_freeform(px(x0), px(y0))
    builder.add_line_segments(
        [(px(x), px(y)) for (x, y) in points[1:]],
        close=False,
    )
    shape = builder.convert_to_shape()
    # No fill (open polyline), solid stroke in series colour.
    shape.fill.background()
    shape.line.color.rgb = color
    shape.line.width = px(stroke_px)
    shape.shadow.inherit = False
    return shape


def _add_dot(target, cx_px: float, cy_px: float, *, color: RGBColor):
    """Filled circle marker centred on (cx_px, cy_px)."""
    r = DOT_DIAMETER_PX / 2
    shape = _shapes(target).add_shape(
        MSO_SHAPE.OVAL,
        px(cx_px - r), px(cy_px - r),
        px(DOT_DIAMETER_PX), px(DOT_DIAMETER_PX),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


# ─── Math ────────────────────────────────────────────────────────────────
def _x_for_index(i: int, n: int, chart_x0: float, chart_w: float) -> float:
    """Even-spaced x position. First point at chart_x0, last at chart_x1."""
    if n <= 1:
        return chart_x0 + chart_w / 2
    return chart_x0 + (i / (n - 1)) * chart_w


def _y_for_value(v: float, y_min: float, y_max: float,
                 chart_y0: float, chart_h: float) -> float:
    """Map a data value to a y pixel. y_min sits at the bottom (chart_y0+chart_h)."""
    if y_max == y_min:
        return chart_y0 + chart_h / 2
    ratio = (v - y_min) / (y_max - y_min)
    return chart_y0 + chart_h - ratio * chart_h


def _nice_ceiling(v: float) -> float:
    """Round v up to a 'nice' axis maximum (1·10^n, 2·10^n, or 5·10^n).

    Keeps tick labels readable. Falls back to v itself if v ≤ 0.
    """
    if v <= 0:
        return 1.0
    import math
    exp = math.floor(math.log10(v))
    base = 10 ** exp
    for mult in (1, 2, 2.5, 5, 10):
        candidate = mult * base
        if candidate >= v:
            return candidate
    return 10 * base


def _format_tick(v: float) -> str:
    """Render a tick value: integers stay integer, fractions get one decimal."""
    if abs(v - round(v)) < 1e-6:
        return f"{int(round(v))}"
    return f"{v:.1f}"
