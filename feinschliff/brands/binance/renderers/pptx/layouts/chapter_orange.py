"""Feinschliff · Chapter · Accent — chapter opener with transparent big-number (HTML 05)."""
from __future__ import annotations

from lxml import etree
from pptx.oxml.ns import qn

import theme as T
from components import (
    add_rule, add_text, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Chapter · Accent"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["accent"])
    paint_chrome(layout, variant="accent", pgmeta="Chapter 01")

    # Big faded background numeral (HTML: right:100, bottom:80, 220px).
    # Bottom edge at y=1000, text height ≈ 220, so top ≈ 780. Add slack.
    big = add_text(
        layout, 1100, 780, 800, 220, "01 / 06",
        size_px=220, weight="light",
        color=T.BLACK, tracking_em=-0.04, line_height=0.85,
    )
    _apply_alpha_to_last_run(big, alpha_pct=22)

    add_rule(layout, 100, 498, width_px=80, height_px=4, color=T.BLACK)
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=100, y_px=542, w_px=1600, h_px=30,
        prompt_text="Chapter opener · orange",
        size_px=T.SIZE_PX["eyebrow"], font=T.FONT_MONO,
        color=T.BLACK, uppercase=True, tracking_em=0.12,
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=596, w_px=1300, h_px=320,
        prompt_text="01\nBrand.",
        size_px=T.SIZE_PX["display"], weight="light",
        color=T.BLACK, tracking_em=-0.035, line_height=0.95,
    )


def _apply_alpha_to_last_run(textbox, *, alpha_pct: int):
    """Inject <a:alpha val="N000"/> into the run's solidFill so the text
    becomes semi-transparent (matches HTML `rgba(0,0,0,0.22)`)."""
    tf = textbox.text_frame
    for p in tf.paragraphs:
        for r in p.runs:
            rPr = r._r.get_or_add_rPr()
            # Find solidFill
            fill = rPr.find(qn("a:solidFill"))
            if fill is None:
                continue
            srgb = fill.find(qn("a:srgbClr"))
            if srgb is None:
                continue
            # Append <a:alpha val="..."/>
            existing_alpha = srgb.find(qn("a:alpha"))
            if existing_alpha is not None:
                srgb.remove(existing_alpha)
            alpha = etree.SubElement(srgb, qn("a:alpha"))
            alpha.set("val", str(alpha_pct * 1000))
