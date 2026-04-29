"""Feinschliff · Text + Picture — text left, picture right, with body paragraph (HTML 11)."""
from __future__ import annotations

import theme as T
from components import (
    add_rule, add_text_placeholder, add_image_placeholder, add_button,
    paint_chrome, set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Text + Picture"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])

    # Right picture — fixed rect.
    add_image_placeholder(
        layout, 1040, 200, 780, 720, label="Induction hob",
    )

    paint_chrome(layout, variant="light", pgmeta="Layout · text + picture")

    # Left column — rule, eyebrow, huge title, body
    add_rule(layout, 100, 200, width_px=80, height_px=4)
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=100, y_px=240, w_px=760, h_px=30,
        prompt_text="Induction · 2026",
        size_px=T.SIZE_PX["eyebrow"], font=T.FONT_MONO,
        color=T.BLACK, uppercase=True, tracking_em=0.12,
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=280, w_px=760, h_px=380,
        prompt_text="Induction that\nlearns your\ncooking.",
        size_px=T.SIZE_PX["huge"], weight="light",
        color=T.BLACK, tracking_em=-0.03, line_height=1.0,
    )
    add_text_placeholder(
        layout, idx=11, name="Body", ph_type="body",
        x_px=100, y_px=700, w_px=720, h_px=140,
        prompt_text=("Adaptive heat zones that calibrate to each pan automatically "
                     "and hold their target to within 2 °C, across the whole surface."),
        size_px=T.SIZE_PX["body"], color=T.GRAPHITE, line_height=1.5,
    )

    # Buttons below body (fixed shapes — decorative CTAs).
    add_button(layout, 100, 870, "Read the brief", variant="primary", w_px=260, h_px=80)
    add_button(layout, 380, 870, "Spec sheet",     variant="ghost",   w_px=210, h_px=80)

