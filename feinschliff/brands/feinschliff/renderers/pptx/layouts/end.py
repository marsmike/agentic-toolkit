"""Feinschliff · End — orange-bg centered "Thank you" (HTML 16)."""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · End"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["accent"])
    paint_chrome(layout, variant="light", pgmeta="End")

    # Centred rule (1920/2 - 60 = 900)
    add_rect(layout, 900, 380, 120, 4, fill=T.BLACK)
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=420, w_px=1720, h_px=280,
        prompt_text="Thank you.",
        size_px=200, weight="light",
        color=T.BLACK, tracking_em=-0.035, line_height=0.95,
        align="c",
    )
    add_text_placeholder(
        layout, idx=10, name="Caption", ph_type="body",
        x_px=100, y_px=720, w_px=1720, h_px=40,
        prompt_text="Feinschliff. Design System · v1.0 · 2026",
        size_px=T.SIZE_PX["eyebrow"], font=T.FONT_MONO,
        color=T.BLACK, uppercase=True, tracking_em=0.12,
        align="c",
    )
