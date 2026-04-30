"""Feinschliff · Title · Ink — ink-bg title slide (HTML ref: slide 02)."""
from __future__ import annotations

import theme as T
from components import (
    add_rule, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Title · Ink"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["ink"])
    paint_chrome(layout, variant="dark", pgmeta="Ferrari · Showcase 2026")

    add_rule(layout, 100, 498, width_px=80, height_px=4, color=T.ACCENT)

    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=100, y_px=542, w_px=1600, h_px=30,
        prompt_text="Title slide · ink variant",
        size_px=T.SIZE_PX["eyebrow"], font=T.FONT_MONO,
        color=T.ACCENT, uppercase=True, tracking_em=0.12,
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=596, w_px=1720, h_px=320,
        prompt_text="The same wordmark\nin a darker room.",
        size_px=T.SIZE_PX["display"], weight="light",
        color=T.WHITE, tracking_em=-0.035, line_height=0.95,
    )
