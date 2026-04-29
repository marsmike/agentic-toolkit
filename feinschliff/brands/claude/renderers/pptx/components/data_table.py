"""Data-table component — management-deck row/column grid.

Paints the chrome of a Feinschliff-style table: a heavy hairline under the
header row, thin FOG hairlines between body rows, no vertical cell
rules (columns separated by whitespace), sharp corners. Returns
per-cell bounding boxes so the hosting layout can overlay editable
text placeholders.

Visual contract:
  - Header band: mono uppercase orange column labels, 2 px ink rule
    below (heavier than body hairlines).
  - Body rows: plain white (no zebra); 1 px FOG hairline between rows.
  - Left column: emphasized (display medium, ink) for row labels.
  - Other cells: body graphite.
  - No vertical borders; column separation is whitespace + optional
    right-alignment for numeric columns.

Layout inside the bounding box (CSS px, top-left origin):

    +--------------+--------+--------+--------+--------+
    | PRODUCT LINE | HEADER | HEADER | HEADER | HEADER |   header band
    +==============+========+========+========+========+   2 px ink rule
    | Flagship A   | 3,240  | +3.8%  | 14.2%  | Ahead  |
    +--------------+--------+--------+--------+--------+   1 px FOG
    | Pro line     | 2,910  | +2.2%  | 13.5%  | Ahead  |
    +--------------+--------+--------+--------+--------+   1 px FOG
    ...
"""
from __future__ import annotations

from pptx.dml.color import RGBColor

import theme as T
from components.primitives import add_line


# Visual constants.
HAIRLINE_PX = 1
HEADER_RULE_PX = 2


def add_data_table(
    target,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    n_cols: int,
    n_rows: int,
    header_h_px: float = 56,
    row_label_w_px: float = 360,
    cell_pad_x_px: float = 24,
    cell_pad_y_px: float = 18,
    hairline_color: RGBColor = T.FOG,
    header_rule_color: RGBColor = T.BLACK,
):
    """Draw the table chrome (hairlines) and return per-cell geometry.

    Args:
      target: Slide / SlideLayout / SlideMaster shape tree.
      x, y, w, h: grid bounding box (CSS px).
      n_cols: total column count (INCLUDING the left row-label column).
      n_rows: body row count (excludes the header row).
      header_h_px: height reserved for the top header band.
      row_label_w_px: width reserved for the left column (row labels).
      cell_pad_x_px: horizontal cell padding applied to text hooks.
      cell_pad_y_px: vertical cell padding applied to text hooks.
      hairline_color: colour for the thin row separators (FOG by default).
      header_rule_color: colour for the 2 px rule under the header.

    Returns: dict with:
      - `header_cells`: list of per-column header bounding boxes.
          Each entry has: x, y, w, h, text_x, text_y, text_w, text_h.
          The first entry covers the row-label column.
      - `label_cells`: list of per-row left-column (row label) boxes.
      - `body_cells`: 2-D list [row][col_index_from_1] of body-cell
          bounding boxes (col_index_from_1: 0 = first non-label column).
          Each entry has: x, y, w, h, text_x, text_y, text_w, text_h.
    """
    assert n_cols >= 2, "data_table needs at least a label column + 1 body column"
    assert n_rows >= 1, "data_table needs at least one body row"

    # ─── Grid geometry ─────────────────────────────────────────────────
    data_x = x + row_label_w_px
    data_w = w - row_label_w_px
    n_body_cols = n_cols - 1
    col_w = data_w / n_body_cols
    body_y = y + header_h_px
    body_h = h - header_h_px
    row_h = body_h / n_rows

    # ─── Header bottom rule (2 px ink — heavier than row hairlines) ───
    add_line(target, x, body_y - HEADER_RULE_PX,
             w, HEADER_RULE_PX, header_rule_color)

    # ─── Horizontal row hairlines (after each body row, including last) ─
    # After the last row too so the table has a closing edge — matches
    # the HTML reference where every body <tr> has a bottom border.
    for i in range(1, n_rows + 1):
        ry = body_y + i * row_h - HAIRLINE_PX / 2
        add_line(target, x, ry, w, HAIRLINE_PX, hairline_color)

    # ─── Header cells ─────────────────────────────────────────────────
    # First header covers the row-label column; the rest split the
    # remaining width evenly.
    header_cells = [{
        "x": x,
        "y": y,
        "w": row_label_w_px,
        "h": header_h_px,
        "text_x": x + cell_pad_x_px,
        "text_y": y + cell_pad_y_px,
        "text_w": row_label_w_px - cell_pad_x_px * 2,
        "text_h": header_h_px - cell_pad_y_px,
    }]
    for j in range(n_body_cols):
        cx = data_x + j * col_w
        header_cells.append({
            "x": cx,
            "y": y,
            "w": col_w,
            "h": header_h_px,
            "text_x": cx + cell_pad_x_px,
            "text_y": y + cell_pad_y_px,
            "text_w": col_w - cell_pad_x_px * 2,
            "text_h": header_h_px - cell_pad_y_px,
        })

    # ─── Row label cells (left column) ────────────────────────────────
    label_cells = []
    for i in range(n_rows):
        cy = body_y + i * row_h
        label_cells.append({
            "x": x,
            "y": cy,
            "w": row_label_w_px,
            "h": row_h,
            "text_x": x + cell_pad_x_px,
            "text_y": cy + cell_pad_y_px,
            "text_w": row_label_w_px - cell_pad_x_px * 2,
            "text_h": row_h - cell_pad_y_px * 2,
        })

    # ─── Body cells (non-label columns) ───────────────────────────────
    body_cells: list[list[dict]] = []
    for i in range(n_rows):
        cy = body_y + i * row_h
        row_cells = []
        for j in range(n_body_cols):
            cx = data_x + j * col_w
            row_cells.append({
                "x": cx,
                "y": cy,
                "w": col_w,
                "h": row_h,
                "text_x": cx + cell_pad_x_px,
                "text_y": cy + cell_pad_y_px,
                "text_w": col_w - cell_pad_x_px * 2,
                "text_h": row_h - cell_pad_y_px * 2,
            })
        body_cells.append(row_cells)

    return {
        "header_cells": header_cells,
        "label_cells": label_cells,
        "body_cells": body_cells,
    }
