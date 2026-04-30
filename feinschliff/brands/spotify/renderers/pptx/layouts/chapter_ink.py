"""Spotify · Chapter · Editorial — chapter divider with hero image left."""
from __future__ import annotations

from lxml import etree
from pptx.oxml.ns import qn

import theme as T
from components import (
    add_text, add_text_placeholder,
    add_equalizer_marker,
    paint_chrome, set_layout_background, set_layout_name,
)
from components.media import add_image_placeholder


NAME = "Feinschliff · Chapter · Ink + Picture"


def _apply_alpha(textbox, *, alpha_pct: int):
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
            existing = srgb.find(qn("a:alpha"))
            if existing is not None:
                srgb.remove(existing)
            alpha = etree.SubElement(srgb, qn("a:alpha"))
            alpha.set("val", str(alpha_pct * 1000))


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])

    add_image_placeholder(layout, 120, 140, 720, 800, label="HERO · 1:1", dark=True)

    paint_chrome(layout, variant="dark", pgmeta="CHAPTER 02")

    add_equalizer_marker(layout, x_px=900, y_px=240, w_px=180, h_px=56, bars=4)

    big = add_text(
        layout, 900, 320, 800, 280, "02",
        size_px=240, weight="bold", font=T.FONT_DISPLAY,
        color=T.BLACK,
        tracking_em=0, line_height=1.0,
    )
    _apply_alpha(big, alpha_pct=12)

    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=900, y_px=580, w_px=900, h_px=28,
        prompt_text="CHAPTER 02 · LIBRARY",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True, tracking_em=0.1,
    )

    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=900, y_px=640, w_px=900, h_px=300,
        prompt_text="Your\nLibrary.",
        size_px=T.SIZE_PX["slide_title"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.BLACK,
        tracking_em=0, line_height=1.05,
    )

    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=900, y_px=950, w_px=900, h_px=60,
        prompt_text="Playlists, albums, and podcasts you've saved — all in one place.",
        size_px=T.SIZE_PX["lead"],
        weight="regular", font=T.FONT_DISPLAY,
        color=T.STEEL,
        tracking_em=0, line_height=1.4,
    )
