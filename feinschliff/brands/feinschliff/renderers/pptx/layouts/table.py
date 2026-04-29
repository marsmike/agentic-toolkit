"""Feinschliff · Table — row/column data grid for management readouts.

Reference: brands/feinschliff/claude-design/feinschliff-2026.html `MCK · Table`.

A McKinsey-style performance matrix: 5+ rows of comparable metrics
(product lines, regions, teams) across 3-6 columns of numbers and
variances. Used when the pattern in the data is easier to see in
a grid than in a chart.

Composition:
  - Standard content header (eyebrow + title) painted by `content_header`.
  - Grid below via `add_data_table` — header band with a 2 px ink rule,
    body rows separated by 1 px FOG hairlines, no vertical cell borders.
  - Column headers (mono uppercase orange, tracked) as editable placeholders.
  - Left column (row labels) in display medium ink — the emphasised column.
  - Other body cells in body graphite.
  - Mono source caption at the bottom.

Placeholder map (idx → slot):
    0               action_title
    10              kicker (eyebrow)
    20 + j          column headers (j = 0..4 — 5 columns max incl. label col)
    30 + i          row labels (left column; i = 0..4 — up to 5 rows)
    40 + i*4 + j    body cells (i = 0..4 rows, j = 0..3 body cols) — 40..59
    60              source caption
"""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)
from components.data_table import add_data_table
from layouts._shared import content_header


NAME = "Feinschliff · Table"
BG = "white"
PGMETA = "Table"
EYEBROW_PROMPT = "FY25 preliminary"
TITLE_PROMPT = (
    "Across five product lines, only dishwashers and ovens beat both "
    "revenue and margin plan."
)

# ─── Schema — preserved verbatim from the stub ─────────────────────────────
SLOTS_SCHEMA = {
    "kicker": {
        "type": "string",
        "maxLength": 40,
        "optional": True
    },
    "action_title": {
        "type": "string",
        "maxLength": 180
    },
    "headers": {
        "type": "array",
        "minItems": 3,
        "maxItems": 7,
        "items": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "maxLength": 24
                },
                "numeric": {
                    "type": "boolean",
                    "optional": True
                }
            },
            "required": [
                "label"
            ]
        }
    },
    "rows": {
        "type": "array",
        "minItems": 3,
        "maxItems": 10,
        "items": {
            "type": "object",
            "properties": {
                "emphasize": {
                    "type": "boolean",
                    "optional": True
                },
                "cells": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "maxLength": 40
                    }
                }
            },
            "required": [
                "cells"
            ]
        }
    },
    "source": {
        "type": "string",
        "maxLength": 160,
        "optional": True
    }
}

# ─── Grid geometry ────────────────────────────────────────────────────────
GRID_X = 100
GRID_Y = 460
GRID_W = 1720
GRID_H = 480

# The layout supports up to 5 columns (1 row-label column + 4 body columns)
# and up to 5 rows. The idx budget (40..59 = 20 cells) fits 5 × 4 body cells.
N_COLS = 5
N_ROWS = 5
N_BODY_COLS = N_COLS - 1

# ─── Demo content — mirrors the HTML reference (trimmed to fit budget) ────
# HTML ref is 5 rows × 6 cols; we keep the full 5 rows, drop the "Verdict"
# column so the table reads as 5 rows × 5 cols (label + 4 body) within
# the layout's placeholder budget.
HEADER_PROMPTS = [
    "Product line",       # row-label column header
    "Revenue · €m",       # body col 0
    "vs. plan",           # body col 1
    "Margin",             # body col 2
    "vs. plan",           # body col 3
]

# Each row: (row label, [body cell values])
ROWS = [
    ("Dishwashers",       ["3,240", "+3.8%", "14.2%", "+0.6 pt"]),
    ("Ovens",             ["2,910", "+2.2%", "13.5%", "+0.4 pt"]),
    ("Refrigeration",     ["3,480", "+0.3%", "11.1%", "−0.2 pt"]),
    ("Laundry",           ["2,610", "−0.9%", "10.4%", "−0.3 pt"]),
    ("Category 4",  ["1,860", "−1.4%", "9.2%",  "−0.7 pt"]),
]

SOURCE_PROMPT = (
    "Source · Internal finance, FY25 preliminary · EUR m · plan set Oct 2024"
)


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX[BG])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    content_header(layout, eyebrow=EYEBROW_PROMPT, title=TITLE_PROMPT)

    # ── Grid chrome (header rule + body hairlines) ─────────────────────
    geom = add_data_table(
        layout,
        GRID_X, GRID_Y, GRID_W, GRID_H,
        n_cols=N_COLS, n_rows=N_ROWS,
    )

    # ── Column headers (idx 20..24) ────────────────────────────────────
    # Mono uppercase orange, tracked — matches the Feinschliff eyebrow pattern
    # and gives the grid a clear chrome row that reads as metadata, not
    # data.
    for j, hdr in enumerate(geom["header_cells"]):
        prompt = HEADER_PROMPTS[j] if j < len(HEADER_PROMPTS) else ""
        add_text_placeholder(
            layout, idx=20 + j,
            name=f"Header {j+1}", ph_type="body",
            x_px=hdr["text_x"], y_px=hdr["text_y"],
            w_px=hdr["text_w"], h_px=hdr["text_h"],
            prompt_text=prompt,
            size_px=T.SIZE_PX.get("eyebrow", 18), font=T.FONT_MONO,
            color=T.ACCENT, uppercase=True, tracking_em=0.12,
        )

    # ── Row labels (idx 30..34) — emphasised left column ───────────────
    # Display medium ink — heavier than body cells so the row identity
    # dominates each line visually.
    for i, lc in enumerate(geom["label_cells"]):
        label = ROWS[i][0] if i < len(ROWS) else ""
        add_text_placeholder(
            layout, idx=30 + i,
            name=f"Row {i+1} Label", ph_type="body",
            x_px=lc["text_x"], y_px=lc["text_y"],
            w_px=lc["text_w"], h_px=lc["text_h"],
            prompt_text=label,
            size_px=T.SIZE_PX.get("col_body", 22), weight="medium",
            color=T.INK, line_height=1.25,
        )

    # ── Body cells (idx 40..59) — graphite body text ───────────────────
    # One placeholder per (row, body-col) cell. idx = 40 + i*4 + j so a
    # 5×4 grid lands at 40..59 — strictly below the source idx of 60.
    for i in range(N_ROWS):
        row_vals = ROWS[i][1] if i < len(ROWS) else []
        for j in range(N_BODY_COLS):
            cell = geom["body_cells"][i][j]
            prompt = row_vals[j] if j < len(row_vals) else ""
            add_text_placeholder(
                layout, idx=40 + i * N_BODY_COLS + j,
                name=f"Cell r{i+1}c{j+1}", ph_type="body",
                x_px=cell["text_x"], y_px=cell["text_y"],
                w_px=cell["text_w"], h_px=cell["text_h"],
                prompt_text=prompt,
                size_px=T.SIZE_PX.get("col_body", 22),
                color=T.GRAPHITE, line_height=1.25,
            )

    # ── Source caption (mono, bottom) ──────────────────────────────────
    add_text_placeholder(
        layout, idx=60, name="Source", ph_type="body",
        x_px=GRID_X, y_px=GRID_Y + GRID_H + 40,
        w_px=GRID_W, h_px=24,
        prompt_text=SOURCE_PROMPT,
        size_px=14, font=T.FONT_MONO,
        color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
    )
