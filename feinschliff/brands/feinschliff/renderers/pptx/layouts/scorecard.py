"""Feinschliff · Scorecard — RAG grid across workstreams × time periods.

A portfolio/board-review scorecard: rows = workstreams/KPIs, columns =
time periods or views; each data cell carries a RAG dot (red/amber/
green) plus a short value/note the user edits via a placeholder. A
legend at the bottom maps the three colours to On / At risk / Off.

The public SLOTS_SCHEMA is preserved verbatim from the stub (Harvey-ball
vocabulary — `options` / `scores`) so existing /deck callers keep working.
The rendered visual is a RAG grid; /deck can project its 0–4 score scale
onto the palette (0–1 → red, 2 → amber, 3–4 → green) if it chooses.

Layout (1920 × 1080):
    y =   0..260  chrome (logo, pgmeta)          → paint_chrome
    y = 260..440  content_header (eyebrow + rule + slide title)
    y = 460..960  scorecard grid
    y = 980..1000 legend (static swatches)
    y =1000..1024 trailing source line (mono)
    y =1030       footer                         → paint_chrome

Idx allocation (must be unique within the layout):
    0           action_title (title placeholder)
    10          kicker (eyebrow placeholder)
    20..24      column headers (up to 5)
    30..34      row labels (workstream names, up to 5)
    40 + i*5 + j   data cell value/note text (i = row, j = col)
                   range for 4 rows × 4 cols: 40..58 — stays below 60
    60          source line (mono trailing)
"""
from __future__ import annotations

import theme as T
from components import (
    add_scorecard, add_text, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)
from components.scorecard import RAG_RED, RAG_AMBER, RAG_GREEN, _add_dot
from layouts._shared import content_header


NAME = "Feinschliff · Scorecard"
BG = "white"
PGMETA = "Scorecard"
EYEBROW_PROMPT = "Portfolio health · FY25 Q3"
TITLE_PROMPT = (
    "Four of five workstreams are on track; developer API slips into Q4 "
    "and data-platform integration is off the critical path."
)

# ─── Grid geometry ─────────────────────────────────────────────────────────
GRID_X = 100
GRID_Y = 460
GRID_W = 1720
GRID_H = 500

# ─── Demo content — 4 workstreams × 4 quarterly columns ───────────────────
# Status vocabulary: "g" (green · on track), "a" (amber · at risk),
# "r" (red · off track). The component renders the coloured dot; the
# value/note text is an editable placeholder so /deck can fill free-form
# status text per cell.
COLUMNS = ["Q1 FY25", "Q2 FY25", "Q3 FY25", "Q4 FY25"]

ROWS = [
    {
        "name": "Firmware consolidation",
        "cells": [
            {"status": "g", "text": "Cutover · 62%"},
            {"status": "g", "text": "Cutover · 100%"},
            {"status": "g", "text": "Shipped"},
            {"status": "g", "text": "Stable"},
        ],
    },
    {
        "name": "Default-on telemetry",
        "cells": [
            {"status": "a", "text": "Pilot factories"},
            {"status": "a", "text": "Rollout 40%"},
            {"status": "g", "text": "Rollout 85%"},
            {"status": "g", "text": "Default-on"},
        ],
    },
    {
        "name": "Developer API",
        "cells": [
            {"status": "r", "text": "Design only"},
            {"status": "a", "text": "Preview private"},
            {"status": "a", "text": "Preview public"},
            {"status": "r", "text": "GA → Q4 slip"},
        ],
    },
    {
        "name": "Data-platform integration",
        "cells": [
            {"status": "a", "text": "Scope locked"},
            {"status": "r", "text": "Vendor delay"},
            {"status": "r", "text": "Off plan"},
            {"status": "r", "text": "Re-baseline"},
        ],
    },
]

N_ROWS = len(ROWS)
N_COLS = len(COLUMNS)

# Schema preserved verbatim from the stub so /deck callers keep working.
SLOTS_SCHEMA = {
    "kicker": {
        "type": "string",
        "maxLength": 40,
        "optional": True,
    },
    "action_title": {
        "type": "string",
        "maxLength": 180,
    },
    "criteria": {
        "type": "array",
        "minItems": 3,
        "maxItems": 6,
        "items": {
            "type": "string",
            "maxLength": 24,
        },
    },
    "options": {
        "type": "array",
        "minItems": 3,
        "maxItems": 6,
        "items": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "maxLength": 40,
                },
                "subtitle": {
                    "type": "string",
                    "maxLength": 60,
                    "optional": True,
                },
                "scores": {
                    "type": "array",
                    "description": "0–4 Harvey ball fill level",
                    "items": {
                        "type": "number",
                    },
                },
                "note": {
                    "type": "string",
                    "maxLength": 120,
                    "optional": True,
                },
                "winner": {
                    "type": "boolean",
                    "optional": True,
                },
            },
            "required": [
                "name",
                "scores",
            ],
        },
    },
    "source": {
        "type": "string",
        "maxLength": 160,
        "optional": True,
    },
}


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX[BG])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    content_header(
        layout,
        eyebrow=EYEBROW_PROMPT,
        title=TITLE_PROMPT,
    )

    # Draw the grid chrome + RAG dots.
    geom = add_scorecard(
        layout,
        GRID_X, GRID_Y, GRID_W, GRID_H,
        ROWS, COLUMNS,
    )

    # ─── Column header placeholders (mono uppercase tracked) ───────────
    for j, col_label in enumerate(COLUMNS):
        hdr = geom["header_cells"][j]
        add_text_placeholder(
            layout, idx=20 + j,
            name=f"Column {j+1} Header", ph_type="body",
            x_px=hdr["x"] + 20, y_px=hdr["y"] + 18,
            w_px=hdr["w"] - 40, h_px=hdr["h"] - 18,
            prompt_text=col_label,
            size_px=T.SIZE_PX.get("eyebrow", 18), font=T.FONT_MONO,
            color=T.GRAPHITE, uppercase=True, tracking_em=0.12,
        )

    # ─── Row label placeholders (display typography — workstream names) ─
    for i, row in enumerate(ROWS):
        lc = geom["label_cells"][i]
        add_text_placeholder(
            layout, idx=30 + i,
            name=f"Row {i+1} Label", ph_type="body",
            x_px=lc["x"] + 20, y_px=lc["y"] + (lc["h"] - 40) / 2,
            w_px=lc["w"] - 32, h_px=40,
            prompt_text=row["name"],
            size_px=22, weight="medium",
            color=T.BLACK, tracking_em=-0.01, line_height=1.2,
        )

    # ─── Data cell value/note placeholders ─────────────────────────────
    # One per (row, col) cell. idx = 40 + i*5 + j so a 4×4 grid stays
    # under 60 (the source idx) without collision. Cells with no status
    # still get a placeholder so /deck can fill a value later.
    for i, row in enumerate(ROWS):
        for j in range(N_COLS):
            cell = geom["data_cells"][i][j]
            prompt = (row["cells"][j] if j < len(row["cells"]) else {}).get("text", "")
            add_text_placeholder(
                layout, idx=40 + i * 5 + j,
                name=f"Cell r{i+1}c{j+1}", ph_type="body",
                x_px=cell["text_x"], y_px=cell["text_y"],
                w_px=cell["text_w"], h_px=cell["text_h"],
                prompt_text=prompt,
                size_px=T.SIZE_PX.get("col_body", 20),
                color=T.GRAPHITE, line_height=1.3,
            )

    # ─── Legend (baked, not editable) ──────────────────────────────────
    # Three swatches + mono labels, right-aligned under the grid. Stays
    # as static shapes — the visual legend is part of the chart fixture
    # and always matches the dot palette; no user edit needed.
    legend_y = GRID_Y + GRID_H + 18
    legend_entries = [
        (RAG_GREEN, "On track"),
        (RAG_AMBER, "At risk"),
        (RAG_RED,   "Off track"),
    ]
    swatch_d = 14
    entry_gap = 40
    label_w = 110
    entry_w = swatch_d + 10 + label_w
    total_w = len(legend_entries) * entry_w + (len(legend_entries) - 1) * entry_gap
    lx = GRID_X + GRID_W - total_w
    for color, label in legend_entries:
        _add_dot(layout, lx, legend_y + 4, swatch_d, color)
        add_text(
            layout, lx + swatch_d + 10, legend_y,
            label_w, 24, label,
            size_px=14, font=T.FONT_MONO,
            color=T.GRAPHITE, uppercase=True, tracking_em=0.12,
        )
        lx += entry_w + entry_gap

    # ─── Trailing source line (mono, bottom) ───────────────────────────
    add_text_placeholder(
        layout, idx=60, name="Source", ph_type="body",
        x_px=GRID_X, y_px=1000, w_px=GRID_W, h_px=24,
        prompt_text="Source · Programme board · FY25 Q3 status review",
        size_px=14, font=T.FONT_MONO,
        color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
    )
