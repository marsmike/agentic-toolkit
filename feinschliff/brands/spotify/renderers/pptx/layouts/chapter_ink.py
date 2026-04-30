"""Feinschliff · Chapter · Ink + Picture — dark chapter opener with right-half image (HTML 06)."""
from __future__ import annotations

import theme as T
from components import (
    add_rule, add_text_placeholder, add_image_placeholder,
    paint_chrome, set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Chapter · Ink + Picture"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["ink"])

    # Right-half dark image frame. Fixed rect so chrome stays on top.
    add_image_placeholder(
        layout, 960, 0, 960, 1080, label="Editorial image · 16:9", dark=True,
    )

    paint_chrome(layout, variant="dark", pgmeta="Chapter 02")

    # 3 lines of huge (120px × 1.0 lh) = 360 → title top ~ 540
    add_rule(layout, 100, 440, width_px=80, height_px=4, color=T.ACCENT)
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=100, y_px=484, w_px=820, h_px=30,
        prompt_text="Chapter opener · ink",
        size_px=T.SIZE_PX["eyebrow"], font=T.FONT_MONO,
        color=T.ACCENT, uppercase=True, tracking_em=0.12,
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=540, w_px=820, h_px=360,
        prompt_text="02\nColour\n& Type.",
        size_px=T.SIZE_PX["huge"], weight="light",
        color=T.BLACK, tracking_em=-0.03, line_height=1.0,
    )
