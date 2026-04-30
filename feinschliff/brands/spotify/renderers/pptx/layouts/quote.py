"""Spotify · Quote — pull-quote on dark canvas with equalizer marker."""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, paint_chrome,
    add_equalizer_marker,
    set_layout_background, set_layout_name,
)


NAME = "Feinschliff · Quote"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="VOICE")

    add_equalizer_marker(layout, x_px=120, y_px=300, w_px=200, h_px=64, bars=4)

    add_text_placeholder(
        layout, idx=0, name="Quote", ph_type="title",
        x_px=120, y_px=420, w_px=1680, h_px=440,
        prompt_text=("“Music happens between the notes — write copy the same way: "
                     "concrete nouns, short sentences, room to breathe.”"),
        size_px=T.SIZE_PX["quote"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.BLACK,
        tracking_em=0, line_height=1.2,
    )

    add_text_placeholder(
        layout, idx=10, name="Attribution", ph_type="body",
        x_px=120, y_px=900, w_px=1680, h_px=30,
        prompt_text="SPOTIFY DESIGN · BRAND VOICE",
        size_px=T.SIZE_PX["quote_attr"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT,
        uppercase=True, tracking_em=0.1,
    )
