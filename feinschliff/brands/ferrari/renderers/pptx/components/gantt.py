"""Gantt (swimlane) component — time-axis header + horizontal lane bars.

A Gantt visualises a project programme: named periods across the top,
horizontal workstream lanes below, and one or more bars per lane spanning
a single period (or a contiguous run of them). Milestones are small
orange diamonds pinned to a specific lane-date pair.

Public:
    add_gantt(target, x, y, w, h, lanes, periods)

`periods` is a list of period label strings (e.g. ["Q1 · Plan", ...]).
The x-axis is divided into equal columns — one per period — and bars are
anchored to 0-based column indices.

`lanes` is a list of dicts:
    {
        "name":    str,                        # lane row label (left gutter)
        "owner":   str | None,                 # small mono hint under the lane name
        "bars":    [
            {
                "period":  int,               # 0-based column index (required)
                "span":    int | None,        # number of columns the bar covers (default 1)
                "label":   str | None,        # optional centred label inside the bar
                "style":   "default"|"accent"|"ghost"|None,  # fill variant
            },
            ...
        ],
        "milestones": [
            {"period": int, "offset_frac": float | None},   # diamond at period + offset (0..1)
        ] | None,
    }

The component is pure: it lays out shapes on `target` and returns a
layout dict so the hosting layout can place editable placeholders over
the lane labels and bar labels.

    {
        "header": {"x": ..., "y": ..., "w": ..., "h": ..., "col_w": ...,
                   "cols": [{"x": int, "y": int, "w": int, "h": int}, ...]},
        "lanes":  [{"row":   {"x": int, "y": int, "w": int, "h": int},
                    "label": {"x": int, "y": int, "w": int, "h": int},
                    "bars":  [{"x": int, "y": int, "w": int, "h": int}, ...]}],
    }
"""
from __future__ import annotations

from pptx.enum.shapes import MSO_SHAPE

import theme as T
from geometry import px
from components.primitives import _shapes, add_rect, add_line


# ─── Geometry constants (in CSS px, relative to the chart bounds) ─────────
HEADER_H         = 48    # height of the time-axis band
LABEL_COL_W      = 300   # left gutter for lane name + owner
LANE_ROW_H       = 80    # total height per lane row (label + bar band)
BAR_H            = 28    # height of a regular bar
GHOST_BAR_H      = 6     # height of a "dependency window" ghost bar
ROW_GAP          = 0     # extra gap between lane rows (rows touch by default)
HAIRLINE_PX      = 1     # separator line thickness
MILESTONE_SIDE   = 18    # side length of milestone diamond (before 45° rotate)


# Style → fill colour for bars. "ghost" is rendered as a thin dashed strip
# to suggest a dependency window, matching the HTML reference.
_STYLE_FILLS = {
    "default": T.INK,
    "accent":  T.ACCENT,
    "ghost":   T.FOG,
}


def add_gantt(
    target,
    x: float,
    y: float,
    w: float,
    h: float,
    lanes: list[dict],
    periods: list[str],
) -> dict:
    """Draw a Gantt chart into (x, y, w, h).

    Returns a layout dict describing the drawn positions of the header,
    lane rows, lane labels, and per-bar rects — layouts use it to overlay
    editable text placeholders without having to recompute geometry.
    """
    n_cols = max(1, len(periods))
    n_lanes = len(lanes)

    # ─── Header band: period labels separated by vertical hairlines ────────
    header_x = x + LABEL_COL_W
    header_y = y
    header_w = w - LABEL_COL_W
    col_w = header_w / n_cols

    cols: list[dict] = []
    for i, label in enumerate(periods):
        cx = header_x + i * col_w
        # Vertical hairline at the LEFT edge of every column except the
        # first — mirrors HTML `.qh { border-left: 1px solid fog }` rule.
        if i > 0:
            add_line(target, cx, header_y, HAIRLINE_PX, HEADER_H, T.FOG)
        # Period label: mono uppercase, left-aligned inside the column.
        # The hosting layout overlays an editable placeholder on top of
        # this region so we do NOT draw the text here — only the geometry.
        cols.append({
            "x": int(cx),
            "y": int(header_y),
            "w": int(col_w),
            "h": int(HEADER_H),
        })

    # Horizontal rule under the header separating it from the lane rows.
    add_line(target, x, header_y + HEADER_H, w, HAIRLINE_PX, T.INK)

    # Continue the column hairlines down through the lane band so the
    # grid reads as one continuous frame.
    lane_band_y = header_y + HEADER_H
    lane_band_h = n_lanes * LANE_ROW_H
    for i in range(1, n_cols):
        cx = header_x + i * col_w
        add_line(target, cx, lane_band_y, HAIRLINE_PX, lane_band_h, T.FOG)

    # ─── Lane rows ────────────────────────────────────────────────────────
    lane_layouts: list[dict] = []
    for li, lane in enumerate(lanes):
        row_y = lane_band_y + li * LANE_ROW_H
        # Lane label gutter — pure geometry, placeholder text comes from layout.
        label_bbox = {
            "x": int(x),
            "y": int(row_y),
            "w": int(LABEL_COL_W),
            "h": int(LANE_ROW_H),
        }
        row_bbox = {
            "x": int(x),
            "y": int(row_y),
            "w": int(w),
            "h": int(LANE_ROW_H),
        }

        # Bars — centred vertically within the row.
        bars = lane.get("bars", []) or []
        bar_bboxes: list[dict] = []
        for bi, bar in enumerate(bars):
            period = int(bar.get("period", 0))
            span = int(bar.get("span", 1) or 1)
            # Clamp to stay inside the grid.
            period = max(0, min(period, n_cols - 1))
            span = max(1, min(span, n_cols - period))

            style = bar.get("style") or "default"
            fill = _STYLE_FILLS.get(style, T.INK)

            this_h = GHOST_BAR_H if style == "ghost" else BAR_H
            bar_x = header_x + period * col_w + 6  # small inset from column edge
            bar_w = span * col_w - 12
            bar_y = row_y + (LANE_ROW_H - this_h) / 2

            if style == "ghost":
                _add_dashed_hairline_h(
                    target, bar_x, bar_y + this_h / 2 - HAIRLINE_PX / 2,
                    bar_w, HAIRLINE_PX, T.SILVER,
                )
            else:
                add_rect(target, bar_x, bar_y, bar_w, this_h, fill=fill)

            bar_bboxes.append({
                "x": int(bar_x),
                "y": int(bar_y),
                "w": int(bar_w),
                "h": int(this_h),
                "style": style,
            })

        # Milestones — drawn on top of bars so they remain visible.
        for m in (lane.get("milestones") or []):
            period = int(m.get("period", 0))
            offset_frac = float(m.get("offset_frac", 0.5) or 0.5)
            period = max(0, min(period, n_cols - 1))
            offset_frac = max(0.0, min(offset_frac, 1.0))
            mx = header_x + (period + offset_frac) * col_w - MILESTONE_SIDE / 2
            my = row_y + (LANE_ROW_H - MILESTONE_SIDE) / 2
            _add_milestone(target, mx, my, MILESTONE_SIDE)

        # Thin bottom hairline between lane rows.
        if li < n_lanes - 1:
            add_line(target, x, row_y + LANE_ROW_H, w, HAIRLINE_PX, T.FOG)

        lane_layouts.append({
            "row":   row_bbox,
            "label": label_bbox,
            "bars":  bar_bboxes,
        })

    # Baseline under the whole Gantt — mirrors the under-header rule.
    bottom_y = lane_band_y + lane_band_h
    add_line(target, x, bottom_y, w, HAIRLINE_PX, T.INK)

    return {
        "header": {
            "x": int(header_x),
            "y": int(header_y),
            "w": int(header_w),
            "h": int(HEADER_H),
            "col_w": col_w,
            "cols": cols,
        },
        "lanes": lane_layouts,
    }


# ─── Helpers ──────────────────────────────────────────────────────────────
def _add_milestone(target, x_px: float, y_px: float, side_px: float):
    """Filled orange diamond marker. Feinschliff uses sharp corners; diamond = rotated square."""
    shape = _shapes(target).add_shape(
        MSO_SHAPE.DIAMOND,
        px(x_px), px(y_px), px(side_px), px(side_px),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = T.ACCENT
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape


def _add_dashed_hairline_h(target, x, y, w, h, color, dash_px: int = 6, gap_px: int = 6):
    """Tile tiny filled rects to fake a dashed horizontal hairline.

    python-pptx doesn't expose dash style on filled rects; same trick the
    waterfall connector uses. Kept local to avoid cross-component imports.
    """
    if w <= 0:
        return
    step = dash_px + gap_px
    cur = x
    end = x + w
    while cur < end:
        seg_w = min(dash_px, end - cur)
        if seg_w > 0:
            add_rect(target, cur, y, seg_w, h, fill=color)
        cur += step
