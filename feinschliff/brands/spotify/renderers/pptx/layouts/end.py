"""Spotify · End — closing slide with green pill 'Open Spotify' CTA."""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, paint_chrome,
    add_button, add_equalizer_marker,
    set_layout_background, set_layout_name,
)


NAME = "Feinschliff · End"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="THANK YOU")

    add_equalizer_marker(layout, x_px=860, y_px=280, w_px=200, h_px=64, bars=4)

    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=120, y_px=420, w_px=1680, h_px=200,
        prompt_text="Thank you.",
        size_px=200,
        weight="bold", font=T.FONT_DISPLAY,
        color=T.BLACK,
        tracking_em=0, line_height=1.0,
        align="c",
    )

    add_text_placeholder(
        layout, idx=10, name="Caption", ph_type="body",
        x_px=120, y_px=720, w_px=1680, h_px=30,
        prompt_text="SPOTIFY · 2026 SHOWCASE",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.STEEL,
        uppercase=True, tracking_em=0.1,
        align="c",
    )

    add_button(layout, x_px=860, y_px=820, label="Open Spotify",
               variant="primary", w_px=200, h_px=56)
