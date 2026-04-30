"""Spotify · Title · Editorial — single hero album tile + headline stack.

Now-playing / hero-album treatment from the Spotify app: a square album
art tile on the left, equalizer marker + headline stack + pill CTAs on
the right.
"""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, paint_chrome,
    add_button, add_equalizer_marker,
    set_layout_background, set_layout_name,
)
from components.media import add_image_placeholder


NAME = "Feinschliff · Title · Ink"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="NOW PLAYING")

    add_image_placeholder(layout, 120, 200, 720, 720, label="ALBUM ART · 1:1", dark=True)

    add_equalizer_marker(layout, x_px=900, y_px=200, w_px=180, h_px=48, bars=4)

    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=900, y_px=290, w_px=900, h_px=28,
        prompt_text="ALBUM · 2026",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True, tracking_em=0.1,
    )

    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=900, y_px=350, w_px=900, h_px=300,
        prompt_text="Made for\nrhythm.",
        size_px=T.SIZE_PX["slide_title"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.BLACK,
        tracking_em=0, line_height=1.05,
    )

    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=900, y_px=680, w_px=900, h_px=120,
        prompt_text="A 12-track set arranged for late-night listening — sequenced, mastered, ready.",
        size_px=T.SIZE_PX["lead"],
        weight="regular", font=T.FONT_DISPLAY,
        color=T.STEEL,
        tracking_em=0, line_height=1.4,
    )

    add_button(layout, x_px=900,  y_px=830, label="Play",   variant="primary", w_px=160, h_px=56)
    add_button(layout, x_px=1080, y_px=830, label="Follow", variant="ghost",   w_px=180, h_px=56)
