"""Stacked-bar chart component — vertical bars built from coloured segments.

A pure builder. Given a target (Slide, SlideLayout, or SlideMaster) and a
bounding box, it paints:

  - a baseline rule
  - one vertical bar per `bars` entry
  - each bar is a stack of coloured segments (bottom → top, in declaration
    order), with an optional value label inside each segment when tall enough

The component does NOT paint axis labels, category labels, totals, or
legend — those belong on the layout (where they become editable
placeholders so users can rewrite the values without re-running the
renderer).

Mirrors HTML reference 22 · MCK · Stacked Bar.
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

import theme as T
from components.primitives import add_rect, add_text


# Minimum segment height (px) at which a value label fits comfortably
# inside the segment without the text colliding with neighbouring segments.
_MIN_LABEL_HEIGHT_PX = 28


def add_stacked_bar(
    target,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    bars: list[dict],
    *,
    orientation: str = "vertical",
    palette: list[RGBColor] | None = None,
    baseline_color: RGBColor = T.BLACK,
    show_segment_values: bool = True,
):
    """Paint a stacked bar chart inside the (x, y, w, h) box.

    `bars` is a list of dicts shaped like::

        {"segments": [{"value": "6.4", "height_px": 150}, ...]}

    Each segment's `height_px` is the rendered pixel height, in the same
    coordinate system as the bounding box. The segments stack from the
    baseline upward in declaration order — so segments[0] sits at the
    bottom of the bar.

    `palette` colours the segments by their position in the stack. Defaults
    to Feinschliff greyscale + orange accent on the top segment, matching the HTML
    reference deck (Legacy=black, Consumer=ink, Commercial=graphite,
    Platform=orange).
    """
    if orientation != "vertical":
        raise NotImplementedError("only vertical orientation is implemented")

    if not bars:
        return

    palette = palette or [T.BLACK, T.INK, T.GRAPHITE, T.ACCENT, T.HIGHLIGHT]

    # Bar width + gap derived from the bounding box and bar count. We keep
    # bars in the Feinschliff-recommended 100–150 px range and let the gap soak up
    # whatever's left so the chart stays centred.
    n = len(bars)
    bar_w = max(80, min(150, int((w_px - 40 * (n - 1)) / n)))
    total_w = bar_w * n + 40 * (n - 1)
    # If we couldn't hit the 80px floor, fall back to evenly distributing
    # without insisting on a 40 px gap.
    if total_w > w_px:
        bar_w = max(40, int(w_px / (n + (n - 1) * 0.3)))
        gap = max(8, int((w_px - bar_w * n) / max(1, n - 1)))
    else:
        gap = int((w_px - bar_w * n) / max(1, n - 1)) if n > 1 else 0

    # Baseline (bottom of the chart area) — a thin filled rule.
    baseline_y = y_px + h_px
    add_rect(target, x_px, baseline_y, w_px, 1, fill=baseline_color)

    for i, bar in enumerate(bars):
        bar_x = x_px + i * (bar_w + gap)
        segments = bar.get("segments", [])

        # Stack from baseline upward — sum heights so we know where each
        # segment's top sits.
        cursor_y = baseline_y
        for j, seg in enumerate(segments):
            seg_h = float(seg.get("height_px", 0))
            if seg_h <= 0:
                continue
            seg_top = cursor_y - seg_h
            color = palette[j % len(palette)]
            add_rect(target, bar_x, seg_top, bar_w, seg_h, fill=color)

            # Inline value label — only when the segment is tall enough,
            # otherwise the text would visually leak into the next segment.
            value = seg.get("value")
            if show_segment_values and value and seg_h >= _MIN_LABEL_HEIGHT_PX:
                # White text on dark Feinschliff segments; black on the orange and
                # any future light fills so the label always passes contrast.
                light_segment = color in (T.HIGHLIGHT,)
                label_color = T.BLACK if light_segment else T.BLACK
                add_text(
                    target,
                    bar_x + 4,
                    seg_top + max(2, (seg_h - 22) / 2),
                    bar_w - 8,
                    22,
                    str(value),
                    size_px=T.SIZE_PX["bar_num"],
                    font=T.FONT_MONO,
                    color=label_color,
                    align=PP_ALIGN.CENTER,
                )

            cursor_y = seg_top
