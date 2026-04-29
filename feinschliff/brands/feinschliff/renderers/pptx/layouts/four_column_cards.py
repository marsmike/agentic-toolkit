"""Feinschliff · 4-Column Cards — quarterly plan grid, paper-card style (HTML 10)."""
from __future__ import annotations

import theme as T
from components import (
    add_rect, paint_chrome,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header, column_placeholders

NAME = "Feinschliff · 4-Column Cards"

CARDS = [
    ("Q1 · Plan",  "Align the 2026 product roadmap across regions.",
     "Finalise priorities, staff crews, lock budget."),
    ("Q2 · Build", "Ship the platform foundations and first feature set.",
     "New OS core, updated Platform SDK."),
    ("Q3 · Pilot", "Field-test with 2,000 households across DACH.",
     "Instrument, measure, iterate weekly."),
    ("Q4 · Scale", "Roll out globally with phased regional launches.",
     "EMEA, then NAM, then APAC."),
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])
    paint_chrome(layout, variant="light", pgmeta="Roadmap · 2026")

    content_header(
        layout,
        eyebrow="Plan, build, pilot, scale",
        title="The year, in four quarters.",
    )

    # 4W + 3*16 = 1720 → W = 418
    col_w = 418
    gap = 16
    x0 = 100
    y0 = 500
    h = 440

    for i, (num, t, body) in enumerate(CARDS):
        x = x0 + i * (col_w + gap)
        add_rect(layout, x, y0, col_w, h, fill=T.PAPER)
        column_placeholders(
            layout, idx_base=20 + i * 3, x=x + 32, y=y0 + 40,
            w=col_w - 64, prompt_num=num, prompt_title=t, prompt_body=body,
            title_size=28,
        )
