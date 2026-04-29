"""Feinschliff · Title · Accent — orange-bg title slide (HTML ref: slide 01).

Bottom-left stacked rule, eyebrow, big Noto Sans Light display title.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rule, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Title · Accent"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["accent"])
    paint_chrome(layout, variant="light", pgmeta="Feinschliff Design System · 2026")

    # HTML opener-stack has bottom:180px. Work upwards:
    #   display = 160px × 2 lines × 0.95 lh = 304px → top = 1080 - 180 - 304 = 596
    #   eyebrow gap 32, eyebrow ~22 → eyebrow top = 596 - 32 - 22 = 542
    #   rule margin 40, rule 4 → rule top = 542 - 40 - 4 = 498
    add_rule(layout, 100, 498, width_px=80, height_px=4, color=T.BLACK)

    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=100, y_px=542, w_px=1600, h_px=30,
        prompt_text="A showcase of the Feinschliff 2026 system",
        size_px=T.SIZE_PX["eyebrow"], font=T.FONT_MONO,
        color=T.BLACK, uppercase=True, tracking_em=0.12,
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=596, w_px=1720, h_px=320,
        prompt_text="Feinschliff\nshowcase deck.",
        size_px=T.SIZE_PX["display"], weight="light",
        color=T.BLACK, tracking_em=-0.035, line_height=0.95,
    )
