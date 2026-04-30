"""Binance · Chapter · Accent — yellow upper / dark lower split divider.

Mirrors the Arena Gradient at lower intensity: a flat 40/60 split with
yellow on top (30% of canvas height) and surface-dark on the bottom. The
chapter number sits inside the dark band as a transparent BinancePlex
backdrop ('01 / 06'), with the headline reading as UPPERCASE display-lg
700 in pure white.
"""
from __future__ import annotations

from lxml import etree
from pptx.oxml.ns import qn

import theme as T
from components import (
    add_rect, add_text, add_text_placeholder, add_section_marker,
    paint_chrome, set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Chapter · Accent"


def build(layout):
    set_layout_name(layout, NAME)
    # Whole canvas is surface-dark; the upper 30% is painted yellow on top.
    set_layout_background(layout, T.HEX["surface_dark"])

    # Yellow upper band — 30% of canvas (324px tall).
    add_rect(layout, 0, 0, 1920, 324, fill=T.ACCENT)

    paint_chrome(layout, variant="accent", pgmeta="CHAPTER 01")

    # Big faded BinancePlex chapter numeral inside the dark lower band —
    # right-aligned, bottom-anchored, 22% alpha.
    big = add_text(
        layout, 1100, 780, 800, 220, "01 / 06",
        size_px=220, weight="bold", font=T.FONT_MONO,
        color=T.GRAPHITE, tracking_em=-0.04, line_height=0.85,
    )
    _apply_alpha_to_last_run(big, alpha_pct=18)

    # Yellow ▌ marker + headline stack.  The marker overlaps the yellow→dark
    # boundary, sitting on the dark lower band so it reads as 'active row'
    # against the dark surface.
    add_section_marker(layout, x_px=100, y_px=440, h_px=380)

    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=140, y_px=440, w_px=1600, h_px=28,
        prompt_text="CHAPTER · ACCENT",
        size_px=T.SIZE_PX["eyebrow"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=140, y_px=490, w_px=1300, h_px=380,
        prompt_text="01\nBrand.",
        size_px=T.SIZE_PX["huge"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.GRAPHITE,
        tracking_em=float(T.HEADLINE_RULE.get("tracking-em", -0.02)),
        line_height=1.05,
    )


def _apply_alpha_to_last_run(textbox, *, alpha_pct: int):
    """Inject <a:alpha val="N000"/> into the run's solidFill so the text
    becomes semi-transparent (matches HTML `rgba(255,255,255,0.18)`)."""
    tf = textbox.text_frame
    for p in tf.paragraphs:
        for r in p.runs:
            rPr = r._r.get_or_add_rPr()
            fill = rPr.find(qn("a:solidFill"))
            if fill is None:
                continue
            srgb = fill.find(qn("a:srgbClr"))
            if srgb is None:
                continue
            existing_alpha = srgb.find(qn("a:alpha"))
            if existing_alpha is not None:
                srgb.remove(existing_alpha)
            alpha = etree.SubElement(srgb, qn("a:alpha"))
            alpha.set("val", str(alpha_pct * 1000))
