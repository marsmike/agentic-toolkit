"""V-Model component — 4-pair tapered verification/validation grid + pivot.

Draws a software V-model diagram inspired by the Claude Design HTML
reference. Four paired phases step inward on a 16-col grid; each pair
is joined by a dashed horizontal connector with a centred pill tag.
A pivot box at the bottom closes the V at "Coding & implementation".

Left-column phase blocks wear a 4px INK left border (verification arm,
top-down). Right-column test blocks wear a 4px ORANGE right border and
right-aligned text (validation arm, bottom-up). The pivot is INK-filled
with an ORANGE top border and white text.

Text is managed by the layout as editable placeholders. This component
only draws the non-text geometry and returns bboxes for every text slot.
"""
from __future__ import annotations

import theme as T
from geometry import px
from components.primitives import add_rect


# 16-col grid row spans, 1-based inclusive, matching the HTML reference.
# (L_start, L_end, C_start, C_end, R_start, R_end)
_ROW_SPANS = [
    (1, 2, 3, 14, 15, 16),
    (3, 4, 5, 12, 13, 14),
    (5, 6, 7, 10, 11, 12),
    (6, 7, 8, 9, 10, 11),
]
_PIVOT_COLS = (7, 10)  # inclusive

_STEP_H = 96
_ROW_GAP = 10
_PIVOT_GAP = 18
_PIVOT_H = 86
_BORDER_W = 4
_TEXT_INSET = 18
_TAG_W = 200
_TAG_H = 24


def add_v_model(target, x: float, y: float, w: float, h: float) -> dict:
    """Draw a 4-pair V-model diagram + pivot into (x, y, w, h).

    Returns bboxes for text placeholders:
        {
          "phases": [{x,y,w,h, counter_x,counter_y, title_x,title_y, text_w}, ...],
          "tests":  [same shape, right-aligned variant],
          "conns":  [{x,y,w,h} for the pill-tag box, text centred],
          "pivot":  {x,y,w,h, counter/title positions}
        }
    """
    n_rows = len(_ROW_SPANS)
    rows_total = n_rows * _STEP_H + (n_rows - 1) * _ROW_GAP
    total = rows_total + _PIVOT_GAP + _PIVOT_H
    y0 = y + max(0, (h - total) / 2)

    col_w = w / 16
    phases: list[dict] = []
    tests: list[dict] = []
    conns: list[dict] = []

    for i, (L1, L2, C1, C2, R1, R2) in enumerate(_ROW_SPANS):
        row_y = y0 + i * (_STEP_H + _ROW_GAP)

        # Left phase block (paper fill + 4px INK left border).
        lx = x + (L1 - 1) * col_w
        lw = (L2 - L1 + 1) * col_w
        add_rect(target, lx, row_y, lw, _STEP_H, fill=T.PAPER)
        add_rect(target, lx, row_y, _BORDER_W, _STEP_H, fill=T.INK)
        phases.append({
            "x": int(lx), "y": int(row_y), "w": int(lw), "h": int(_STEP_H),
            "text_x": int(lx + _TEXT_INSET),
            "text_w": int(lw - _TEXT_INSET * 2),
            "counter_y": int(row_y + 16),
            "title_y":   int(row_y + 40),
            "align": "l",
        })

        # Right test block (paper fill + 4px ORANGE right border).
        rx = x + (R1 - 1) * col_w
        rw = (R2 - R1 + 1) * col_w
        add_rect(target, rx, row_y, rw, _STEP_H, fill=T.PAPER)
        add_rect(target, rx + rw - _BORDER_W, row_y, _BORDER_W, _STEP_H, fill=T.ACCENT)
        tests.append({
            "x": int(rx), "y": int(row_y), "w": int(rw), "h": int(_STEP_H),
            "text_x": int(rx + _TEXT_INSET),
            "text_w": int(rw - _TEXT_INSET * 2),
            "counter_y": int(row_y + 16),
            "title_y":   int(row_y + 40),
            "align": "r",
        })

        # Dashed connector across the centre cols, with a centred tag window.
        cx = x + (C1 - 1) * col_w
        cw = (C2 - C1 + 1) * col_w
        line_y = row_y + _STEP_H / 2
        _add_dashed_line_h(target, cx, line_y, cw, T.SILVER, dash_px=6, gap_px=6)

        # Tag background — white rect punching a hole through the dashed line,
        # with the pill text drawn by the layout as a placeholder.
        tag_x = cx + (cw - _TAG_W) / 2
        tag_y = line_y - _TAG_H / 2
        add_rect(target, tag_x, tag_y, _TAG_W, _TAG_H, fill=T.INK)
        conns.append({
            "x": int(tag_x), "y": int(tag_y), "w": int(_TAG_W), "h": int(_TAG_H),
        })

    # Pivot block — ink fill + orange top rail.
    pivot_y = y0 + rows_total + _PIVOT_GAP
    P1, P2 = _PIVOT_COLS
    pvx = x + (P1 - 1) * col_w
    pvw = (P2 - P1 + 1) * col_w
    add_rect(target, pvx, pivot_y, pvw, _PIVOT_H, fill=T.INK)
    add_rect(target, pvx, pivot_y, pvw, _BORDER_W, fill=T.ACCENT)
    pivot = {
        "x": int(pvx), "y": int(pivot_y), "w": int(pvw), "h": int(_PIVOT_H),
        "text_x": int(pvx), "text_w": int(pvw),
        "counter_y": int(pivot_y + 16),
        "title_y":   int(pivot_y + 40),
    }

    return {"phases": phases, "tests": tests, "conns": conns, "pivot": pivot}


def _add_dashed_line_h(
    target, x: float, y: float, w: float, color, *,
    dash_px: int = 6, gap_px: int = 6, thickness_px: float = 1,
):
    """Tile tiny filled rects to emulate a 1px dashed horizontal hairline.

    python-pptx doesn't expose dash style on filled rects; same trick the
    waterfall + gantt connectors use. Kept local to avoid cross-component
    imports.
    """
    if w <= 0:
        return
    step = dash_px + gap_px
    cur = x
    end = x + w
    while cur < end:
        seg_w = min(dash_px, end - cur)
        if seg_w > 0:
            add_rect(target, cur, y - thickness_px / 2, seg_w, thickness_px, fill=color)
        cur += step
