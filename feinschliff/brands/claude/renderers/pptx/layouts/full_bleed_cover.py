"""Feinschliff · Full-bleed Cover — full-bleed image area with orange title block (HTML 12).

Picture-fill is handled as a full-bleed rect sized 1920x1080 (paintable), not
a picture placeholder — PowerPoint/LibreOffice z-order behaviour renders
placeholders above fixed shapes, so chrome stays visible above a fixed fill.
Users can right-click the fill shape and Format → Fill → Picture to drop an
image into place.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_rule, add_text_placeholder,
    paint_chrome, set_layout_background, set_layout_name,
)
from components.media import add_image_placeholder

NAME = "Feinschliff · Full-bleed Cover"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])

    # Full-bleed fixed rectangle — behind everything else on the layout.
    add_image_placeholder(
        layout, 0, 0, 1920, 1080, label="Drop cover image",
    )

    # Chrome (logo + pgmeta + footer)
    paint_chrome(layout, variant="light", pgmeta="Cover")

    # Orange title block — needs to fit rule + eyebrow + 2-line title at 72px.
    # Rule 4 + gap 28 + eyebrow 22 + gap 16 + title 2 × 72 = 214px; plus 32px
    # top/bottom padding → block height ≈ 278.
    add_rect(layout, 100, 680, 820, 280, fill=T.ACCENT)
    add_rule(layout, 140, 712, width_px=80, height_px=4, color=T.BLACK)
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=140, y_px=748, w_px=740, h_px=30,
        prompt_text="Layout · full-bleed cover",
        size_px=T.SIZE_PX["eyebrow"], font=T.FONT_MONO,
        color=T.BLACK, uppercase=True, tracking_em=0.12,
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=140, y_px=790, w_px=740, h_px=160,
        prompt_text="An image does\nthe talking.",
        size_px=72, weight="light",
        color=T.BLACK, tracking_em=-0.03, line_height=1.0,
    )
