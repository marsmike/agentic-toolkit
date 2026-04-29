"""Waterfall (bridge) chart component.

A waterfall shows how a starting total moves to an ending total via a
sequence of positive (`up`) and negative (`down`) drivers, bracketed by
two anchor bars (`start` and `total`). Each bar is the same width; their
heights and y-offsets encode the running cumulative.

Public:
    add_waterfall(target, x, y, w, h, bars)

`bars` is an ordered list of dicts, each:
    {"label": str, "value": float, "kind": "start"|"up"|"down"|"total"}

The component is a pure function — it lays out shapes on `target` and
returns nothing. All typography, fills, and connector hairlines come
from the Feinschliff theme tokens; no fields are placeholdered here. Layouts
that need editable bar labels/values overlay invisible
`add_text_placeholder` boxes on top.
"""
from __future__ import annotations

from pptx.enum.text import PP_ALIGN

import theme as T
from components.primitives import add_rect, add_line, add_text


# ─── Geometry constants (in CSS px, all relative to the chart bounds) ──────
TOP_PAD     = 60   # space above bars for value labels
BOTTOM_PAD  = 80   # space below baseline for category labels + foot rule
LABEL_BAND  = 60   # height of the label strip below baseline
VALUE_BAND  = 36   # height of the value strip above each bar
GAP         = 24   # horizontal gap between bars
CONNECTOR_H = 1    # connector hairline thickness (px)
CONNECTOR_DASH = 6 # px on / px off for the dashed connector
CONNECTOR_GAP  = 4


def add_waterfall(
    target,
    x: float,
    y: float,
    w: float,
    h: float,
    bars: list[dict],
) -> dict:
    """Draw a waterfall chart in (x, y, w, h).

    Returns a dict mapping bar index → its drawn rect bbox in px:
        {i: {"x": int, "y": int, "w": int, "h": int,
             "value_y": int, "label_y": int, "kind": str}}
    Layouts use the bbox to overlay placeholders.
    """
    n = len(bars)
    if n == 0:
        return {}

    # Plot area: bars sit between the value strip and the label strip.
    plot_top = y + TOP_PAD
    plot_bottom = y + h - BOTTOM_PAD
    plot_h = plot_bottom - plot_top

    # Bar width — divide remaining horizontal space equally.
    bar_w = (w - GAP * (n - 1)) / n

    # Compute running cumulative + per-bar geometry. Anchors (`start`,
    # `total`) reset the running total to their absolute value; `up` and
    # `down` are deltas off the current running total.
    max_value = _max_extent(bars)
    if max_value <= 0:
        max_value = 1.0  # avoid div/0 on degenerate input

    px_per_unit = plot_h / max_value

    bboxes: dict[int, dict] = {}
    running = 0.0
    last_top_y: float | None = None  # y of previous bar's top for connector

    for i, bar in enumerate(bars):
        kind = bar.get("kind", "up")
        value = float(bar.get("value", 0))

        bx = x + i * (bar_w + GAP)

        if kind in ("start", "total"):
            # Anchor: full-height bar from baseline up to `value`.
            bar_height = value * px_per_unit
            top_y = plot_bottom - bar_height
            running = value
            fill = T.ACCENT
        elif kind == "up":
            # Bar sits ON TOP of running total, extends UP by `value`.
            base_y = plot_bottom - running * px_per_unit
            bar_height = value * px_per_unit
            top_y = base_y - bar_height
            running += value
            fill = T.INK
        elif kind == "down":
            # Bar sits BELOW the previous top, extends DOWN by `value`.
            top_y = plot_bottom - running * px_per_unit
            bar_height = value * px_per_unit
            running -= value
            fill = T.STEEL
        else:
            # Unknown kind — render as a neutral bar so it's at least visible.
            bar_height = max(value * px_per_unit, 4)
            top_y = plot_bottom - bar_height
            fill = T.SILVER

        # Clamp to plot area (defensive — bad data shouldn't blow geometry).
        if bar_height < 2:
            bar_height = 2
        if top_y < plot_top:
            top_y = plot_top

        # Connector hairline from previous bar's top (or running cumulative
        # for `down` bars where the bar itself starts at the cumulative).
        if last_top_y is not None and i > 0:
            prev_bar = bars[i - 1]
            conn_y = last_top_y if prev_bar.get("kind") != "down" \
                else (plot_bottom - _cumulative_at(bars, i - 1) * px_per_unit)
            connector_x0 = bx - GAP - 2  # extend a hair into prior bar
            connector_x1 = bx + 2        # extend a hair into this bar
            _add_dashed_hairline(
                target, connector_x0, conn_y,
                connector_x1 - connector_x0, CONNECTOR_H, T.GRAPHITE,
            )

        # The bar itself.
        add_rect(target, bx, top_y, bar_w, bar_height, fill=fill)

        # Track top for connector to next bar. For `down` bars the next
        # connector should anchor to the new (lower) running total, not
        # the bar top. We store the bar top here and resolve at draw time.
        last_top_y = top_y

        # Compute the running-total y for `down` bars (used by the next
        # connector). For up/anchor bars, the bar top IS the running top.
        bboxes[i] = {
            "x": int(bx),
            "y": int(top_y),
            "w": int(bar_w),
            "h": int(bar_height),
            "value_y": int(top_y - VALUE_BAND - 4),
            "label_y": int(plot_bottom + 8),
            "kind": kind,
        }

    # Baseline rule — a 1px ink hairline under the bars.
    add_line(target, x, plot_bottom, w, 1, T.INK)

    return bboxes


# ─── Helpers ───────────────────────────────────────────────────────────────
def _max_extent(bars: list[dict]) -> float:
    """Maximum running cumulative — sets the chart's vertical scale.

    Walks the same accumulator the renderer uses so a tall `up` bar can't
    spill past the top of the plot area.
    """
    running = 0.0
    peak = 0.0
    for bar in bars:
        kind = bar.get("kind", "up")
        value = float(bar.get("value", 0))
        if kind in ("start", "total"):
            running = value
        elif kind == "up":
            running += value
        elif kind == "down":
            running -= value
        peak = max(peak, running, value)
    return peak


def _cumulative_at(bars: list[dict], idx: int) -> float:
    """Running total after applying `bars[0..idx]` (inclusive)."""
    running = 0.0
    for i in range(idx + 1):
        kind = bars[i].get("kind", "up")
        value = float(bars[i].get("value", 0))
        if kind in ("start", "total"):
            running = value
        elif kind == "up":
            running += value
        elif kind == "down":
            running -= value
    return running


def _add_dashed_hairline(target, x, y, w, h, color):
    """Approximate a dashed rule with a row of tiny filled rects.

    python-pptx doesn't expose dash style on a filled rect, so we tile.
    """
    if w <= 0:
        return
    step = CONNECTOR_DASH + CONNECTOR_GAP
    cur = x
    end = x + w
    while cur < end:
        seg_w = min(CONNECTOR_DASH, end - cur)
        if seg_w > 0:
            add_rect(target, cur, y, seg_w, h, fill=color)
        cur += step
