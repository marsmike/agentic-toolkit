"""Pyramid component — stacked trapezoidal tiers, wide at base → narrow at apex.

A pyramid visualises a hierarchy / value ladder: the widest tier at the
bottom is the foundation, the narrowest at the top is the strategic or
aspirational layer. Each intermediate tier is a trapezoid; the apex is a
triangle. Together the silhouette reads as a single pyramid.

The component draws only the tier shapes — labels (name / detail /
side-note) are managed by the layout as editable placeholders so they
stay Feinschliff-typography-compliant.

Sharp corners are mandatory in Feinschliff; trapezoids are straight-edged by
definition, so intermediate tiers are freeform 4-point polygons. The
apex uses MSO_SHAPE.ISOSCELES_TRIANGLE so users can recognise it as a
single primitive when editing.
"""
from __future__ import annotations

from typing import Sequence

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

import theme as T
from geometry import px
from components.primitives import _shapes


# Default fill rotation (base → apex). T.INK is the strongest tone; banding
# alternates high-contrast → supporting neutrals so the stack reads as
# distinct tiers even on a flat brand palette.
_DEFAULT_FILLS_BY_ROLE = ("ink", "accent", "graphite", "fog", "steel")


def _resolve_fills(n: int, fills: Sequence[RGBColor] | None) -> list[RGBColor]:
    """Return `n` fills in apex → base order.

    If the caller provides an explicit palette we cycle through it; otherwise
    we use the Feinschliff default banding.
    """
    if fills is not None:
        palette = list(fills)
    else:
        palette = [getattr(T, key.upper()) for key in _DEFAULT_FILLS_BY_ROLE]
    # Apex is index 0 (top). We want the base to be T.INK for visual weight,
    # so we pick the first n entries apex-first but reverse so base = palette[0].
    # Concretely: apex = palette[n-1], base = palette[0].
    out = []
    for i in range(n):
        # i = 0 is apex (narrowest), i = n-1 is base (widest).
        # Map apex → later palette entry, base → first palette entry.
        idx = (n - 1 - i) % len(palette)
        out.append(palette[idx])
    return out


def add_pyramid(
    target,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    tiers: Sequence[dict],
    *,
    apex_w_px: float | None = None,
    base_w_px: float | None = None,
    fills: Sequence[RGBColor] | None = None,
    gap_px: float = 4,
):
    """Draw a pyramid inside (x_px, y_px, w_px, h_px).

    Args:
        target: Slide / SlideLayout / SlideMaster shape host.
        x_px, y_px, w_px, h_px: bounding box of the pyramid in CSS px.
        tiers: list of tier dicts (apex-first). Only `len(tiers)` matters here —
            labels are drawn by the layout. 3 ≤ len(tiers) ≤ 5.
        apex_w_px: width at the very top. Default = 0 (pure triangle tip).
        base_w_px: width at the very bottom. Default = w_px.
        fills: optional palette of RGBColor to use base→apex. Defaults to
            T.INK → T.ACCENT → T.GRAPHITE → T.FOG → T.STEEL.
        gap_px: blank gap between tiers. 0 = continuous silhouette.

    Returns:
        list of shapes created, in apex-down (top-down) order.
    """
    n = len(tiers)
    if not 3 <= n <= 5:
        raise ValueError(f"pyramid needs 3-5 tiers, got {n}")

    if apex_w_px is None:
        apex_w_px = 0.0
    if base_w_px is None:
        base_w_px = w_px

    total_gap = gap_px * (n - 1)
    slice_h = (h_px - total_gap) / n

    def boundary_w(i: int) -> float:
        """Width at boundary i (0 = top edge of apex tier, n = bottom of base)."""
        t = i / n
        return apex_w_px + (base_w_px - apex_w_px) * t

    cx = x_px + w_px / 2  # pyramid is horizontally centred

    tier_fills = _resolve_fills(n, fills)
    shapes_out = []
    cy = y_px

    for i in range(n):
        w_top = boundary_w(i)
        w_bot = boundary_w(i + 1)
        fill = tier_fills[i]

        if i == 0 and w_top <= 1.0:
            # True apex — w_top ~ 0: render as an isosceles triangle so users
            # see "a triangle" in PowerPoint's shape pane, not a degenerate
            # freeform. Width equals the base of this tier.
            sh = _shapes(target).add_shape(
                MSO_SHAPE.ISOSCELES_TRIANGLE,
                px(cx - w_bot / 2), px(cy),
                px(w_bot), px(slice_h),
            )
            sh.fill.solid()
            sh.fill.fore_color.rgb = fill
            sh.line.fill.background()
            sh.shadow.inherit = False
        else:
            # Trapezoid — 4 corners clockwise from top-left.
            tl = (cx - w_top / 2, cy)
            tr = (cx + w_top / 2, cy)
            br = (cx + w_bot / 2, cy + slice_h)
            bl = (cx - w_bot / 2, cy + slice_h)

            ff = _shapes(target).build_freeform(
                start_x=px(tl[0]), start_y=px(tl[1]),
            )
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
            sh.fill.fore_color.rgb = fill
            sh.line.fill.background()
            sh.shadow.inherit = False

        shapes_out.append(sh)
        cy += slice_h + gap_px

    return shapes_out


def pyramid_geometry(
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    n_tiers: int,
    *,
    apex_w_px: float | None = None,
    base_w_px: float | None = None,
    gap_px: float = 4,
) -> list[dict]:
    """Pure geometry helper — per-tier positions for label placement.

    Returns a list (apex-first) of dicts:
        {
            "y": int,          # top y of tier
            "h": int,          # tier height
            "cx": int,         # horizontal centre
            "top_w": int,      # width at top edge
            "bot_w": int,      # width at bottom edge
            "left_top": int,   # x of the tier's top-left corner
            "right_top": int,  # x of the tier's top-right corner
            "left_bot": int,   # x of the tier's bottom-left corner
            "right_bot": int,  # x of the tier's bottom-right corner
        }
    """
    if apex_w_px is None:
        apex_w_px = 0.0
    if base_w_px is None:
        base_w_px = w_px

    total_gap = gap_px * (n_tiers - 1)
    slice_h = (h_px - total_gap) / n_tiers
    cx = x_px + w_px / 2

    def boundary_w(i: int) -> float:
        t = i / n_tiers
        return apex_w_px + (base_w_px - apex_w_px) * t

    out = []
    cy = y_px
    for i in range(n_tiers):
        w_top = boundary_w(i)
        w_bot = boundary_w(i + 1)
        out.append(
            {
                "y": int(cy),
                "h": int(slice_h),
                "cx": int(cx),
                "top_w": int(w_top),
                "bot_w": int(w_bot),
                "left_top": int(cx - w_top / 2),
                "right_top": int(cx + w_top / 2),
                "left_bot": int(cx - w_bot / 2),
                "right_bot": int(cx + w_bot / 2),
            }
        )
        cy += slice_h + gap_px

    return out
