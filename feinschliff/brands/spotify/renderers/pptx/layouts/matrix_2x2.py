"""Feinschliff · 2×2 Matrix — McKinsey-style prioritisation grid with focus quadrant."""
from __future__ import annotations

import theme as T
from components import (
    add_text, add_text_placeholder,
    paint_chrome, set_layout_background, set_layout_name,
)
from components.matrix_2x2 import add_matrix_2x2
from layouts._shared import content_header

NAME = 'Feinschliff · 2×2 Matrix'
BG = 'white'
PGMETA = '2×2 Matrix'
EYEBROW_PROMPT = '2×2 Matrix'
TITLE_PROMPT = 'Classic 2×2 prioritisation grid with one focus quadrant flag.'

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
    "x_axis_label": {
        "type": "string",
        "maxLength": 30
    },
    "y_axis_label": {
        "type": "string",
        "maxLength": 30
    },
    "cells": {
        "type": "array",
        "minItems": 4,
        "maxItems": 4,
        "description": "Cells in reading order: TL, TR, BL, BR.",
        "items": {
            "type": "object",
            "properties": {
                "tag": {
                    "type": "string",
                    "maxLength": 40
                },
                "heading": {
                    "type": "string",
                    "maxLength": 80
                },
                "body": {
                    "type": "string",
                    "maxLength": 140
                },
                "focus": {
                    "type": "boolean",
                    "optional": True
                }
            },
            "required": [
                "tag",
                "heading"
            ]
        }
    },
    "legend_title": {
        "type": "string",
        "maxLength": 40,
        "optional": True
    },
    "legend_body": {
        "type": "string",
        "maxLength": 240,
        "optional": True
    }
}


# ─── Geometry ──────────────────────────────────────────────────────────────
# Content area: x=100..1820, y=460..1020. Grid is centred around (960, 740).
# Reserve left margin for y-axis title, bottom margin for x-axis title.
GRID_X = 280
GRID_Y = 470
GRID_W = 1360
GRID_H = 540
HALF_W = GRID_W // 2     # 680
HALF_H = GRID_H // 2     # 270
CELL_PAD = 28            # inner padding inside each cell

# Per-cell idx allocation: tag-derived prompt + label@20+i*4, body@21+i*4.
# 4 indices reserved per cell (i=0..3) → 20..35. axis_x=41, axis_y=42.
DEMO_CELLS = [
    {  # TL — high y, low x
        "tag": "Q1 · High impact · low lift",
        "heading": "Guided sessions on the flagship line.",
        "body": "Ships on existing hardware; telemetry already collected; known user need.",
        "focus": True,
    },
    {  # TR — high y, high x
        "tag": "Q2 · High impact · high lift",
        "heading": "Full remote diagnosis across every product line.",
        "body": "Large prize; requires firmware convergence and a new field-service workflow.",
    },
    {  # BL — low y, low x
        "tag": "Q3 · Low impact · low lift",
        "heading": "Cosmetic refresh of onboarding.",
        "body": "Cheap to do; metrics rarely move meaningfully.",
    },
    {  # BR — low y, high x
        "tag": "Q4 · Low impact · high lift",
        "heading": "Voice control expansion.",
        "body": "Significant engineering and QA cost; adoption has plateaued.",
    },
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX[BG])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    content_header(
        layout,
        eyebrow="Prioritisation",
        title="Invest in the top-right quadrant first: high impact, low lift.",
    )

    # ─── Static chrome: grid lines, axis extremes, focus fill ────────────
    add_matrix_2x2(
        layout,
        GRID_X, GRID_Y, GRID_W, GRID_H,
        cells=DEMO_CELLS,
        axis_x_low="Low",
        axis_x_high="High",
        axis_y_low="Low",
        axis_y_high="High",
    )

    # ─── Per-cell editable placeholders ──────────────────────────────────
    # Cell rect order: TL, TR, BL, BR (matches DEMO_CELLS).
    cell_origins = [
        (GRID_X,          GRID_Y),           # TL · idx_base=20
        (GRID_X + HALF_W, GRID_Y),           # TR · idx_base=24
        (GRID_X,          GRID_Y + HALF_H),  # BL · idx_base=28
        (GRID_X + HALF_W, GRID_Y + HALF_H),  # BR · idx_base=32
    ]
    for i, ((cx, cy), demo) in enumerate(zip(cell_origins, DEMO_CELLS)):
        idx_label = 20 + i * 4
        idx_body = 21 + i * 4
        is_focus = bool(demo.get("focus"))
        # Tag (static, mono caps, decorative — not editable).
        # Sits inside the cell padding, above the editable label.
        tag_color = T.BLACK if is_focus else T.GRAPHITE
        add_text(
            layout, cx + CELL_PAD, cy + CELL_PAD,
            HALF_W - 2 * CELL_PAD, 22, demo["tag"],
            size_px=14, font=T.FONT_MONO,
            color=tag_color, uppercase=True, tracking_em=0.12,
        )
        # Editable cell label (heading).
        label_color = T.BLACK if is_focus else T.BLACK
        add_text_placeholder(
            layout, idx=idx_label, name=f"Cell{i+1} Label", ph_type="body",
            x_px=cx + CELL_PAD, y_px=cy + CELL_PAD + 32,
            w_px=HALF_W - 2 * CELL_PAD, h_px=80,
            prompt_text=demo["heading"],
            size_px=26, weight="medium",
            color=label_color, tracking_em=-0.012, line_height=1.15,
        )
        # Editable cell body (description).
        body_color = T.INK if is_focus else T.GRAPHITE
        add_text_placeholder(
            layout, idx=idx_body, name=f"Cell{i+1} Body", ph_type="body",
            x_px=cx + CELL_PAD, y_px=cy + CELL_PAD + 120,
            w_px=HALF_W - 2 * CELL_PAD, h_px=HALF_H - CELL_PAD - 130,
            prompt_text=demo["body"],
            size_px=18,
            color=body_color, line_height=1.4,
        )

    # ─── Axis title placeholders (editable) ──────────────────────────────
    # x-axis title — centred below the grid extreme labels.
    add_text_placeholder(
        layout, idx=41, name="X Axis Title", ph_type="body",
        x_px=GRID_X, y_px=GRID_Y + GRID_H + 56,
        w_px=GRID_W, h_px=24,
        prompt_text="Effort to ship",
        size_px=16, font=T.FONT_MONO,
        color=T.GRAPHITE, uppercase=True, tracking_em=0.14,
        align="c",
    )
    # y-axis title — narrow vertical column on the far left, stacked
    # bottom-up so it reads like a rotated label without OOXML rotation
    # (which placeholders don't expose cleanly).
    add_text_placeholder(
        layout, idx=42, name="Y Axis Title", ph_type="body",
        x_px=120, y_px=GRID_Y, w_px=80, h_px=GRID_H,
        prompt_text="I\nm\np\na\nc\nt",
        size_px=16, font=T.FONT_MONO,
        color=T.GRAPHITE, uppercase=True, tracking_em=0.14,
        align="c", anchor="m", line_height=1.2,
    )
