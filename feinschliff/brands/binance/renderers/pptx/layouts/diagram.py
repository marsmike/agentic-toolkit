"""Feinschliff · Diagram — small title up top, large diagram frame below, caption at foot.

The diagram frame is a striped image placeholder so the unfilled layout is
obvious in the master. At slide-build time, the runtime places a real PNG
(typically an Excalidraw export) over this frame.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_rule, add_text, add_text_placeholder,
    paint_chrome, set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Diagram"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])

    # Diagram frame — a quiet FOG rect with a thin silver outline so an
    # unfilled layout is legible but not loud. A small mono label in the
    # top-left corner signals how to fill it. slides.add_diagram paints a
    # white rect over this frame before the PNG, so filled slides never
    # expose the FOG / label even when the PNG is aspect-fit and leaves
    # gaps.
    add_rect(
        layout, 100, 250, 1720, 680,
        fill=T.FOG, line=T.SILVER, line_weight_px=1,
    )
    add_text(
        layout, 120, 270, 400, 30, "DIAGRAM · FILL VIA /DECK",
        size_px=T.SIZE_PX["eyebrow"], weight="semibold", font=T.FONT_DISPLAY,
        color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
    )

    paint_chrome(layout, variant="light", pgmeta="Layout · diagram")

    # Top-left stack — rule, eyebrow, small title.
    add_rule(layout, 100, 120, width_px=80, height_px=4)
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=100, y_px=160, w_px=1720, h_px=30,
        prompt_text="Layout · diagram",
        size_px=T.SIZE_PX["eyebrow"], weight="semibold", font=T.FONT_DISPLAY,
        color=T.BLACK, uppercase=True, tracking_em=0.1,
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=195, w_px=1720, h_px=50,
        prompt_text="Architectural overview goes here.",
        size_px=T.SIZE_PX["slide_title"], weight="bold",
        color=T.BLACK, tracking_em=-0.02, line_height=1.1,
    )

    # Caption strip at the foot of the slide.
    add_text_placeholder(
        layout, idx=11, name="Caption", ph_type="body",
        x_px=100, y_px=955, w_px=1720, h_px=40,
        prompt_text="Caption · source, figure number, etc.",
        size_px=T.SIZE_PX["body"], color=T.GRAPHITE,
    )
