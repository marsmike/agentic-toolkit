"""Feinschliff · Agenda — 6 agenda rows, 2 × 3 grid (HTML 04)."""
from __future__ import annotations

import theme as T
from components import (
    add_rule, add_line, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Agenda"

ROWS = [
    ("01 / 06", "Brand mark",  "Wordmark, contrast, clear space."),
    ("02 / 06", "Colour",      "One orange, seven neutrals."),
    ("03 / 06", "Type",        "Noto Sans, 28pt titles."),
    ("04 / 06", "Layouts",     "Chapter, content, picture, data."),
    ("05 / 06", "Components",  "Buttons, chips, KPIs, rules."),
    ("06 / 06", "Voice",       "Quiet confidence."),
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])
    paint_chrome(layout, variant="light", pgmeta="Agenda")

    # Top: rule + eyebrow + big light title
    add_rule(layout, 100, 180, width_px=80, height_px=4)
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=100, y_px=220, w_px=1600, h_px=30,
        prompt_text="Only title layout",
        size_px=T.SIZE_PX["eyebrow"], weight="semibold", font=T.FONT_DISPLAY,
        color=T.BLACK, uppercase=True, tracking_em=0.1,
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=260, w_px=1720, h_px=100,
        prompt_text="What we'll cover.",
        size_px=56, weight="bold",
        color=T.BLACK, tracking_em=-0.02, line_height=1.05,
    )

    # 6 agenda rows — 2 cols × 3 rows
    col_w = 860
    row_h = 112
    y0 = 420
    for i, (n, t, d) in enumerate(ROWS):
        col = i % 2
        row = i // 2
        x = 100 + col * (col_w + 40)
        y = y0 + row * row_h

        add_line(layout, x, y, col_w, 1, T.FOG)
        idx_base = 20 + i * 3
        add_text_placeholder(
            layout, idx=idx_base, name=f"Row {i+1} Num", ph_type="body",
            x_px=x, y_px=y + 14, w_px=110, h_px=30, prompt_text=n,
            size_px=T.SIZE_PX["agenda_num"], weight="semibold", font=T.FONT_MONO,
            color=T.ACCENT, tracking_em=0.08,
        )
        add_text_placeholder(
            layout, idx=idx_base + 1, name=f"Row {i+1} Title", ph_type="body",
            x_px=x + 120, y_px=y + 10, w_px=col_w - 120, h_px=40, prompt_text=t,
            size_px=T.SIZE_PX["agenda_t"], weight="medium",
            color=T.BLACK, tracking_em=-0.01,
        )
        add_text_placeholder(
            layout, idx=idx_base + 2, name=f"Row {i+1} Desc", ph_type="body",
            x_px=x + 120, y_px=y + 52, w_px=col_w - 120, h_px=32, prompt_text=d,
            size_px=T.SIZE_PX["agenda_d"], color=T.GRAPHITE,
        )
