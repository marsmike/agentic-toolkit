"""Feinschliff · Title + Picture — split layout, text left, picture right (HTML 03)."""
from __future__ import annotations

import theme as T
from components import (
    add_rule, add_text_placeholder, add_image_placeholder,
    paint_chrome, set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Title + Picture"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])

    # Right-half image frame — fixed rect (not a placeholder) because image
    # placeholders z-order above fixed shapes in LibreOffice, obscuring chrome.
    # To replace with a real image: right-click → Format Shape → Fill → Picture.
    add_image_placeholder(
        layout, 960, 0, 960, 1080, label="Product shot · 16:9",
    )

    paint_chrome(layout, variant="light", pgmeta="Title + picture")

    # Left stack — rule, eyebrow, huge title, body.
    # HTML ref: .opener-stack bottom:180px; stack height = 454 (body + title +
    # eyebrow + rule + gaps). Stack top = 1080 − 180 − 454 = 446.
    add_rule(layout, 100, 450, width_px=80, height_px=4)
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=100, y_px=494, w_px=820, h_px=30,
        prompt_text="Layout 03 · title + picture",
        size_px=T.SIZE_PX["eyebrow"], weight="bold", font=T.FONT_DISPLAY,
        color=T.BLACK, uppercase=True, tracking_em=0.1,
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=544, w_px=820, h_px=260,
        prompt_text="Pair a title\nwith a product.",
        size_px=T.SIZE_PX["huge"], weight="medium",
        color=T.BLACK, tracking_em=-0.03, line_height=1.0,
    )
    add_text_placeholder(
        layout, idx=11, name="Body", ph_type="body",
        x_px=100, y_px=820, w_px=780, h_px=100,
        prompt_text=("Full-bleed image on the right half, title stacked on the left. "
                     "The logo and page meta sit on top, unchanged."),
        size_px=T.SIZE_PX["body"], color=T.GRAPHITE, line_height=1.5,
    )
