"""Spotify · Chapter — chapter divider with equalizer marker on dark canvas."""
from __future__ import annotations

import theme as T
from components import (
    add_text, add_text_placeholder,
    add_equalizer_marker,
    paint_chrome, set_layout_background, set_layout_name,
)


NAME = "Feinschliff · Chapter · Accent"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="CHAPTER 01")

    # Big chapter numeral — soft watermark right
    add_text(
        layout, 1100, 240, 720, 280, "01",
        size_px=240, weight="bold", font=T.FONT_DISPLAY,
        color=T.RULE_DARK,
        tracking_em=0, line_height=1.0,
    )

    # Equalizer marker
    add_equalizer_marker(layout, x_px=120, y_px=440, w_px=180, h_px=56, bars=4)

    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=120, y_px=540, w_px=1600, h_px=28,
        prompt_text="CHAPTER 01 · DISCOVER",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True, tracking_em=0.1,
    )

    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=120, y_px=600, w_px=1300, h_px=280,
        prompt_text="Discover\n& Listen.",
        size_px=T.SIZE_PX["slide_title"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.BLACK,
        tracking_em=0, line_height=1.05,
    )

    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=120, y_px=900, w_px=1100, h_px=80,
        prompt_text="The radio shelf, made-for-you mixes, and weekly refreshes.",
        size_px=T.SIZE_PX["lead"],
        weight="regular", font=T.FONT_DISPLAY,
        color=T.STEEL,
        tracking_em=0, line_height=1.4,
    )
