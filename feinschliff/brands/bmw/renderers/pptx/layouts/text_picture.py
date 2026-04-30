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
        layout, 1040, 200, 780, 720, label="Product hero",
    )

    paint_chrome(layout, variant="light", pgmeta="Layout · text + picture")

    # Left column — rule, eyebrow, huge title, body
    add_rule(layout, 100, 200, width_px=80, height_px=4)
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=100, y_px=240, w_px=760, h_px=30,
        prompt_text="Flagship · 2026",
        size_px=T.SIZE_PX["eyebrow"], weight="bold", font=T.FONT_DISPLAY,
        color=T.BLACK, uppercase=True, tracking_em=0.115,
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=280, w_px=760, h_px=240,
        prompt_text="A flagship that\nlearns the user.",
        size_px=T.SIZE_PX["slide_title"], weight="bold",
        font=T.FONT_DISPLAY,
        color=T.INK, tracking_em=0, line_height=1.05,
    )
    add_text_placeholder(
        layout, idx=11, name="Body", ph_type="body",
        x_px=100, y_px=560, w_px=720, h_px=200,
        prompt_text=("Adaptive heat zones that calibrate to each pan automatically "
                     "and hold their target to within 2 °C, across the whole surface."),
        size_px=T.SIZE_PX["body"],
        weight="light",
        font=T.FONT_DISPLAY,
        color=T.STEEL, line_height=1.55,
    )

    # Buttons — BMW Blue primary CTA + ghost secondary
    add_button(layout, 100, 800, "Read the brief", variant="primary", w_px=260, h_px=80)
    add_button(layout, 380, 800, "Spec sheet",     variant="ghost",   w_px=210, h_px=80)

