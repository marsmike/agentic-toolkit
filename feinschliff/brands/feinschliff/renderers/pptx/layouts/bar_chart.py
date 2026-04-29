"""Feinschliff · Bar Chart — 4 horizontal bar rows with labelled tracks (HTML 13)."""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header

NAME = "Feinschliff · Bar Chart"

ROWS = [
    ("EMEA",  62, False),
    ("NAM",   24, True),
    ("APAC",  11, False),
    ("LATAM",  3, False),
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])
    paint_chrome(layout, variant="light", pgmeta="Data · Q3 results")

    content_header(
        layout,
        eyebrow="Share of revenue by region",
        title="EMEA still leads; NAM closing the gap.",
    )

    y0 = 540
    row_h = 80
    track_x = 100 + 240 + 24
    track_w = 1720 - 240 - 120 - 48

    for i, (label, pct, accent) in enumerate(ROWS):
        y = y0 + i * row_h
        # Label placeholder
        add_text_placeholder(
            layout, idx=20 + i * 2, name=f"Bar {i+1} Label", ph_type="body",
            x_px=100, y_px=y, w_px=240, h_px=40, prompt_text=label,
            size_px=T.SIZE_PX["bar_label"], weight="medium", color=T.BLACK,
        )
        # Track (background)
        add_rect(layout, track_x, y + 8, track_w, 32, fill=T.FOG)
        # Fill (data)
        fill_w = int(round(track_w * (pct / 100.0)))
        add_rect(
            layout, track_x, y + 8, fill_w, 32,
            fill=(T.ACCENT if accent else T.BLACK),
        )
        # Value placeholder (right aligned)
        add_text_placeholder(
            layout, idx=21 + i * 2, name=f"Bar {i+1} Value", ph_type="body",
            x_px=1700, y_px=y + 6, w_px=120, h_px=32, prompt_text=f"{pct}%",
            size_px=T.SIZE_PX["bar_num"], font=T.FONT_MONO,
            color=T.BLACK, align="r",
        )

    # Figure caption
    add_text_placeholder(
        layout, idx=40, name="Figure caption", ph_type="body",
        x_px=100, y_px=920, w_px=1720, h_px=30,
        prompt_text="Figure 01 · Sample data, Q3 FY25 · N = €14.1 bn",
        size_px=16, font=T.FONT_MONO,
        color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
    )
