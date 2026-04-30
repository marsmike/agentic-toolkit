"""Process-Flow component — a horizontal row of chevron-shaped stages.

A process flow visualises 3–6 sequential stages (brief → prototype → pilot →
harden → scale) as a left-to-right chain of chevron-clipped cards. Each
card has a pointy right edge and a notched left edge, so successive cards
lock together like arrowheads and the eye is pulled along the sequence.

The component draws only the chevron shapes themselves — per-stage text
(number / title / body) is managed by the layout as editable placeholders
so users can rewrite the copy without touching the visual design.

Chevrons use `MSO_SHAPE.CHEVRON`, which gives a PowerPoint-native arrow
shape with a pointy right edge. The first stage gets a `PENTAGON` instead,
because its left edge should be flat (nothing flows into it). Stages are
laid out with a small horizontal overlap so the notch of stage N+1 tucks
into the point of stage N — exactly like the HTML reference's clip-path
trick with `margin-right: -28px`.

An "active" stage (flagged with `active: True`) reverses the colour pair:
dark `fill_active` background with light text, while neighbours use a
paper fill with dark text. This mirrors the HTML `.flow .step.on` state.
"""
from __future__ import annotations

from typing import Sequence

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

import theme as T
from geometry import px
from components.primitives import _shapes


# Horizontal overlap between successive chevrons (CSS px). Matches the
# HTML reference's -28px margin so the arrow point of stage N lands
# inside the notch of stage N+1.
CHEVRON_OVERLAP_PX = 28


def add_process_flow(
    target,
    x: float,
    y: float,
    w: float,
    h: float,
    stages: Sequence[dict],
    *,
    overlap_px: float = CHEVRON_OVERLAP_PX,
    fill: RGBColor = T.PAPER,
    fill_active: RGBColor = T.INK,
) -> list[dict]:
    """Draw a horizontal chain of chevron stage cards into (x, y, w, h).

    Args:
        target: Slide / SlideLayout / SlideMaster shape host.
        x, y, w, h: bounding box of the full chain in CSS px.
        stages: list of stage dicts. Only `len(stages)` and each dict's
            optional `active: bool` key affect this component — all text
            is drawn by the layout. 3 ≤ len(stages) ≤ 6.
        overlap_px: how far stage N+1's notch tucks into stage N's point.
        fill: background for normal (inactive) stages.
        fill_active: background for the stage flagged `active: True`.

    Returns:
        A list (one entry per stage, left-to-right) of bbox dicts:
            {
                "x": int, "y": int, "w": int, "h": int,
                "text_x": int, "text_w": int,  # safe region for text
                "active": bool,
            }
        The layout uses these bboxes to position editable placeholders
        for the number/title/body of each stage, staying inside the
        chevron's straight interior (clear of the pointy tip and notch).
    """
    n = len(stages)
    if not 3 <= n <= 6:
        raise ValueError(f"process flow needs 3–6 stages, got {n}")

    # Per-stage width: slices overlap by `overlap_px`, so total width is
    #     n * stage_w - (n - 1) * overlap_px = w
    # → stage_w = (w + (n - 1) * overlap_px) / n
    stage_w = (w + (n - 1) * overlap_px) / n

    # Width of the pointy tip / notch at each side of a chevron — matches
    # the HTML clip-path `28px` trapezoid on the right edge.
    tip_px = overlap_px

    bboxes: list[dict] = []
    for i, stage in enumerate(stages):
        sx = x + i * (stage_w - overlap_px)
        is_active = bool(stage.get("active"))

        # Shape choice: first card has a flat left edge (PENTAGON points
        # right only); every subsequent card is a full CHEVRON (arrow
        # point right, arrow notch left).
        shape_kind = MSO_SHAPE.PENTAGON if i == 0 else MSO_SHAPE.CHEVRON
        shape = _shapes(target).add_shape(
            shape_kind, px(sx), px(y), px(stage_w), px(h),
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill_active if is_active else fill
        shape.line.fill.background()
        shape.shadow.inherit = False

        # Safe text region: inset from the pointy tip (right) and, for
        # non-first stages, from the notch (left). HTML uses a 32/60 px
        # pad; we bias text left so it still reads even after the point.
        text_inset_left = 60 if i > 0 else 32
        text_inset_right = tip_px + 16

        bboxes.append({
            "x": int(sx),
            "y": int(y),
            "w": int(stage_w),
            "h": int(h),
            "text_x": int(sx + text_inset_left),
            "text_w": int(stage_w - text_inset_left - text_inset_right),
            "active": is_active,
        })

    return bboxes
