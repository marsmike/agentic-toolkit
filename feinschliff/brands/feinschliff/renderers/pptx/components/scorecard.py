"""Scorecard component — RAG-indicator grid (workstreams × periods).

Pure geometry. Draws the table chrome (header band, row/column hairlines,
left workstream column, RAG dots inside each data cell) and returns a
dict of cell bounding boxes so the hosting layout can overlay editable
text placeholders on the right hooks.

Layout inside the bounding box (CSS px, top-left origin):

    +------------+--------+--------+--------+--------+
    |            | COL 1  | COL 2  | COL 3  | COL 4  |   header band (mono caps)
    +------------+--------+--------+--------+--------+
    | Workstream | ● text | ● text | ● text | ● text |
    +------------+--------+--------+--------+--------+
    | Workstream | ● text | ● text | ● text | ● text |
    +------------+--------+--------+--------+--------+
    ...

RAG palette (overridable via kwargs):
  - "r" / "red"   → #A04848           (muted terra — at risk / off track)
  - "a" / "amber" → T.HIGHLIGHT (#E4C27A) (caution)
  - "g" / "green" → #8FB888           (sage — on track)
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

import theme as T
from components.primitives import _shapes, add_line, add_rect
from geometry import px


# ─── RAG palette ─────────────────────────────────────────────────────────
# Status hues are the one place the brand admits a non-gold third colour.
# Muted register (sage / terra) so they don't fight the gold-on-navy system.
RAG_RED   = RGBColor(0xA0, 0x48, 0x48)
RAG_AMBER = T.HIGHLIGHT
RAG_GREEN = RGBColor(0x8F, 0xB8, 0x88)

RAG_MAP = {
    "r": RAG_RED, "red": RAG_RED, "off": RAG_RED,
    "a": RAG_AMBER, "amber": RAG_AMBER, "risk": RAG_AMBER,
    "g": RAG_GREEN, "green": RAG_GREEN, "on": RAG_GREEN,
}

# Visual constants.
HAIRLINE_PX = 1
DOT_DIAMETER_PX = 18


def add_scorecard(
    target,
    x: float,
    y: float,
    w: float,
    h: float,
    rows: list[dict],
    columns: list[str],
    *,
    header_h_px: float = 56,
    row_label_w_px: float = 340,
    hairline_color: RGBColor = T.FOG,
    header_color: RGBColor = T.GRAPHITE,
    dot_diameter_px: float = DOT_DIAMETER_PX,
    rag_red: RGBColor = RAG_RED,
    rag_amber: RGBColor = RAG_AMBER,
    rag_green: RGBColor = RAG_GREEN,
):
    """Draw the scorecard grid chrome + RAG dots.

    Args:
      target: Slide / SlideLayout / SlideMaster shape tree.
      x, y, w, h: grid bounding box (CSS px).
      rows: list of row descriptors. Each dict has at minimum:
          - `cells`: list of per-column dicts with `status` ("r"/"a"/"g").
        Other keys (name, note, etc.) are ignored — text is rendered by
        the layout's editable placeholders.
      columns: list of column-header label strings. Drives column count
          and width (cells split the remainder equally).
      header_h_px: height reserved for the top header band.
      row_label_w_px: width reserved for the left workstream-name column.
      hairline_color: FOG by default — thin row/column separators.
      header_color: colour for the header underline + dividers.
      rag_red/amber/green: RGB overrides for the RAG palette.

    Returns: dict with:
      - `label_cells`: list of per-row label bounding boxes
            [{"x", "y", "w", "h"} × n_rows]
      - `header_cells`: list of per-column header bounding boxes
            [{"x", "y", "w", "h"} × n_cols]
      - `data_cells`: 2-D list [row][col] of data-cell bounding boxes
            (each with keys x, y, w, h, dot_x, dot_y, text_x, text_y,
             text_w, text_h) — the layout uses these to place editable
            text placeholders over each cell.
    """
    n_cols = len(columns)
    n_rows = len(rows)
    assert n_rows > 0 and n_cols > 0, "scorecard needs at least one row and column"

    palette = {"r": rag_red, "a": rag_amber, "g": rag_green}
    # Accept long-form keys too.
    palette.update({"red": rag_red, "amber": rag_amber, "green": rag_green})

    # ─── Grid geometry ─────────────────────────────────────────────────
    data_x = x + row_label_w_px
    data_w = w - row_label_w_px
    col_w = data_w / n_cols
    body_y = y + header_h_px
    body_h = h - header_h_px
    row_h = body_h / n_rows

    # ─── Header band bottom rule (heavier than row hairlines) ─────────
    add_line(target, x, body_y - HAIRLINE_PX, w, HAIRLINE_PX, header_color)

    # ─── Vertical dividers — full height ─────────────────────────────
    # One at the right edge of the row-label column + one between each
    # pair of data columns.
    add_line(target, data_x - HAIRLINE_PX / 2, y,
             HAIRLINE_PX, h, hairline_color)
    for j in range(1, n_cols):
        vx = data_x + j * col_w - HAIRLINE_PX / 2
        add_line(target, vx, y, HAIRLINE_PX, h, hairline_color)

    # ─── Horizontal row hairlines (between data rows, not after last) ──
    for i in range(1, n_rows):
        ry = body_y + i * row_h - HAIRLINE_PX / 2
        add_line(target, x, ry, w, HAIRLINE_PX, hairline_color)

    # ─── Header cells ─────────────────────────────────────────────────
    header_cells = []
    for j in range(n_cols):
        header_cells.append({
            "x": data_x + j * col_w,
            "y": y,
            "w": col_w,
            "h": header_h_px,
        })

    # ─── Row label cells ──────────────────────────────────────────────
    label_cells = []
    for i in range(n_rows):
        label_cells.append({
            "x": x,
            "y": body_y + i * row_h,
            "w": row_label_w_px,
            "h": row_h,
        })

    # ─── Data cells + RAG dots ────────────────────────────────────────
    # Dot sits at the top-left of each cell; text placeholder hook sits
    # to its right on the same baseline so layouts can pin a value/note.
    inset_x = 20
    inset_y = 18
    text_gap = 12

    data_cells: list[list[dict]] = []
    for i, row in enumerate(rows):
        cells = row.get("cells", []) if isinstance(row, dict) else []
        row_cells = []
        for j in range(n_cols):
            cx = data_x + j * col_w
            cy = body_y + i * row_h

            dot_x = cx + inset_x
            dot_y = cy + inset_y
            text_x = dot_x + dot_diameter_px + text_gap
            text_y = cy + inset_y - 4  # align text optical centre to dot
            text_w = col_w - (text_x - cx) - inset_x
            text_h = row_h - inset_y * 2

            # Paint the RAG dot if a status is given. Unknown / missing
            # status leaves the cell empty (hairline-only) so layouts can
            # fall back to a neutral state.
            if j < len(cells):
                status = (cells[j] or {}).get("status")
                if status:
                    color = palette.get(str(status).lower())
                    if color is not None:
                        _add_dot(target, dot_x, dot_y, dot_diameter_px, color)

            row_cells.append({
                "x": cx, "y": cy, "w": col_w, "h": row_h,
                "dot_x": dot_x, "dot_y": dot_y,
                "text_x": text_x, "text_y": text_y,
                "text_w": text_w, "text_h": text_h,
            })
        data_cells.append(row_cells)

    return {
        "header_cells": header_cells,
        "label_cells": label_cells,
        "data_cells": data_cells,
    }


def _add_dot(target, x_px: float, y_px: float, d_px: float, color: RGBColor):
    """Filled circle RAG indicator. Top-left anchored for simplicity —
    callers compute the anchor from cell geometry."""
    shape = _shapes(target).add_shape(
        MSO_SHAPE.OVAL,
        px(x_px), px(y_px), px(d_px), px(d_px),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
    shape.line.fill.background()
    shape.shadow.inherit = False
    return shape
