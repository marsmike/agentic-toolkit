"""Funnel component — vertical trapezoidal funnel narrowing top → bottom.

A funnel visualises a multi-stage conversion or filtering: wide at the top
(everyone enters), narrow at the bottom (few survive). Each "slice" is a
trapezoid; successive slices share an edge so the funnel reads as one
continuous shape.

The component draws only the trapezoid stack — labels (name/volume/detail)
sit to the right of each slice and are managed by the layout as editable
placeholders, so they stay Feinschliff-typography-compliant.

Sharp corners are mandatory in Feinschliff; trapezoids are by definition straight
edges, so we use freeform polygons (4 points, closed) for full control over
top-width, bottom-width, and height per slice.
"""
from __future__ import annotations

from typing import Sequence

from pptx.dml.color import RGBColor
from pptx.util import Emu, Pt

import theme as T
from geometry import px
from components.primitives import _shapes


def add_funnel(
    target,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    stages: Sequence[dict],
    *,
    top_w_px: float | None = None,
    bottom_w_px: float | None = None,
    accent_index: int | None = None,
    fill_color: RGBColor = T.INK,
    accent_color: RGBColor = T.ACCENT,
    gap_px: float = 4,
):
    """Draw a vertical trapezoidal funnel into (x, y, w, h).

    Args:
        target: Slide / SlideLayout / SlideMaster shape host.
        x_px, y_px, w_px, h_px: bounding box of the funnel in CSS px.
        stages: list of stage dicts. Only `len(stages)` and an optional
            `weight` key matter to this component — labels/values are drawn
            by the layout. 3 ≤ len(stages) ≤ 6.
        top_w_px, bottom_w_px: explicit top/bottom widths. Default to
            full w_px on top, 25% on bottom.
        accent_index: 0-based index of the slice to fill in `accent_color`
            instead of `fill_color`. None = no accent.
        fill_color: solid fill for non-accent slices.
        accent_color: solid fill for the accent slice.
        gap_px: blank gap between slices, in CSS px. 0 = continuous funnel.

    Returns:
        list of the freeform shapes created (one per slice), in top-down order.
    """
    n = len(stages)
    if not 3 <= n <= 6:
        raise ValueError(f"funnel needs 3–6 stages, got {n}")

    if top_w_px is None:
        top_w_px = w_px
    if bottom_w_px is None:
        bottom_w_px = w_px * 0.25

    # Per-stage height — equal slices (sum to h_px including gaps).
    total_gap = gap_px * (n - 1)
    slice_h = (h_px - total_gap) / n

    # Width at the boundary BETWEEN slice i and slice i+1, measured top-down.
    #   boundary 0 = top edge of slice 0  = top_w_px
    #   boundary n = bottom edge of slice n-1 = bottom_w_px
    # Linear interpolation across n+1 boundaries.
    def boundary_w(i: int) -> float:
        t = i / n  # 0..1
        return top_w_px + (bottom_w_px - top_w_px) * t

    cx = x_px + w_px / 2  # horizontal centre — slices stay centred

    shapes_out = []
    cy = y_px
    for i in range(n):
        w_top = boundary_w(i)
        w_bot = boundary_w(i + 1)

        # 4 corners, clockwise from top-left.
        tl = (cx - w_top / 2, cy)
        tr = (cx + w_top / 2, cy)
        br = (cx + w_bot / 2, cy + slice_h)
        bl = (cx - w_bot / 2, cy + slice_h)

        ff = _shapes(target).build_freeform(start_x=px(tl[0]), start_y=px(tl[1]))
        ff.add_line_segments(
            [
                (px(tr[0]), px(tr[1])),
                (px(br[0]), px(br[1])),
                (px(bl[0]), px(bl[1])),
            ],
            close=True,
        )
        sh = ff.convert_to_shape()

        sh.fill.solid()
        sh.fill.fore_color.rgb = (
            accent_color if accent_index is not None and i == accent_index else fill_color
        )
        sh.line.fill.background()
        sh.shadow.inherit = False

        shapes_out.append(sh)
        cy += slice_h + gap_px

    return shapes_out


def funnel_geometry(
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    n_stages: int,
    *,
    top_w_px: float | None = None,
    bottom_w_px: float | None = None,
    gap_px: float = 4,
) -> list[dict]:
    """Pure geometry helper — return per-slice positions for label placement.

    The layout uses this to position name / detail / volume / rate text
    placeholders flush with the right edge of each slice + a small inset.

    Returns a list of dicts, one per slice (top-down):
        {
            "y": int,        # top y of slice
            "h": int,        # slice height
            "cx": int,       # horizontal centre
            "right_edge_top": int,  # x of the slice's top-right corner
            "right_edge_bot": int,  # x of the slice's bottom-right corner
        }
    """
    if top_w_px is None:
        top_w_px = w_px
    if bottom_w_px is None:
        bottom_w_px = w_px * 0.25

    total_gap = gap_px * (n_stages - 1)
    slice_h = (h_px - total_gap) / n_stages
    cx = x_px + w_px / 2

    def boundary_w(i: int) -> float:
        t = i / n_stages
        return top_w_px + (bottom_w_px - top_w_px) * t

    out = []
    cy = y_px
    for i in range(n_stages):
        w_top = boundary_w(i)
        w_bot = boundary_w(i + 1)
        out.append(
            {
                "y": int(cy),
                "h": int(slice_h),
                "cx": int(cx),
                "right_edge_top": int(cx + w_top / 2),
                "right_edge_bot": int(cx + w_bot / 2),
            }
        )
        cy += slice_h + gap_px

    return out
