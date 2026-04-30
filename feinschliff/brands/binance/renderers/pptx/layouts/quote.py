"""Feinschliff · Quote — orange-bg centered quote (HTML 15)."""
from __future__ import annotations

import theme as T
from components import (
    add_rule, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Quote"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["accent"])
    paint_chrome(layout, variant="accent", pgmeta="Voice")

    # HTML .quote has max-width 1400px, vertically centered (top: 50%).
    add_rule(layout, 100, 420, width_px=80, height_px=4, color=T.BLACK)
    add_text_placeholder(
        layout, idx=0, name="Quote", ph_type="title",
        x_px=100, y_px=460, w_px=1400, h_px=420,
        prompt_text=("“Write like an engineer explaining their work to a colleague they respect. "
                     "Short sentences. Concrete nouns. No superlatives.”"),
        size_px=T.SIZE_PX["quote"], weight="light",
        color=T.BLACK, tracking_em=-0.025, line_height=1.1,
    )
    add_text_placeholder(
        layout, idx=10, name="Attribution", ph_type="body",
        x_px=100, y_px=900, w_px=1720, h_px=30,
        prompt_text="Feinschliff. Design System · Voice guideline",
        size_px=T.SIZE_PX["quote_attr"], font=T.FONT_MONO,
        color=T.BLACK, uppercase=True, tracking_em=0.12,
    )
