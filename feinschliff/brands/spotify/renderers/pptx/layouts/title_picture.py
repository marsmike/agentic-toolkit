"""Spotify · Title + Picture — split cover, headline left, photo right."""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder,
    add_button, add_equalizer_marker,
    paint_chrome, set_layout_background, set_layout_name,
)
from components.media import add_image_placeholder


NAME = "Feinschliff · Title + Picture"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])

    add_image_placeholder(layout, 1040, 140, 760, 800, label="HERO · 1:1", dark=True)

    paint_chrome(layout, variant="dark", pgmeta="MADE FOR YOU")

    add_equalizer_marker(layout, x_px=120, y_px=200, w_px=140, h_px=40, bars=3)

    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=120, y_px=280, w_px=820, h_px=30,
        prompt_text="MADE FOR YOU · WEEKLY",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True, tracking_em=0.1,
    )

    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=120, y_px=340, w_px=820, h_px=300,
        prompt_text="Discover\nWeekly.",
        size_px=T.SIZE_PX["slide_title"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.BLACK,
        tracking_em=0, line_height=1.05,
    )

    add_text_placeholder(
        layout, idx=11, name="Body", ph_type="body",
        x_px=120, y_px=680, w_px=820, h_px=160,
        prompt_text=("30 tracks tuned to your last week of listening — refreshed every "
                     "Monday, all yours."),
        size_px=T.SIZE_PX["body"],
        weight="regular", font=T.FONT_DISPLAY,
        color=T.STEEL, line_height=1.55,
    )

    add_button(layout, x_px=120, y_px=890, label="Play",   variant="primary", w_px=160, h_px=56)
    add_button(layout, x_px=300, y_px=890, label="Follow", variant="ghost",   w_px=180, h_px=56)
