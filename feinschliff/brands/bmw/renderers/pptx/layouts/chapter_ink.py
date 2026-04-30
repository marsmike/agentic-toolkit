"""BMW · Chapter · Dark — chapter divider on dark navy with M-stripe.

The dark counterpart of the light chapter divider. Per BMW DESIGN.md, dark
navy bands appear at most once or twice per page rhythm (light → dark →
light) — chapter dividers are one of the slots where the dark band lands.

  * surface-dark navy canvas with on-dark text.
  * Big chapter numeral 240px / 700 white at low alpha.
  * UPPERCASE eyebrow on dark, M-stripe divider, big title.
  * Right half holds an optional 16:10 model render (no shadow, edge-to-edge).
"""
from __future__ import annotations

from lxml import etree
from pptx.oxml.ns import qn

import theme as T
from components import (
    add_text, add_text_placeholder,
    add_image_placeholder, add_m_stripe,
    paint_chrome, set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Chapter · Ink + Picture"


def _apply_alpha(textbox, *, alpha_pct: int):
    """Inject <a:alpha val="N000"/> for semi-transparent text."""
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


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])

    # ── Right-half optional model render ──────────────────────────────────
    add_image_placeholder(
        layout, 960, 0, 960, 1080, label="Model render · 16:10", dark=True,
    )

    paint_chrome(layout, variant="dark", pgmeta="CHAPTER 02")

    # ── Big chapter numeral — alpha-faded white, watermark register ───────
    big = add_text(
        layout, 80, 240, 800, 280, "02",
        size_px=240,
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.WHITE,
        tracking_em=0,
        line_height=1.0,
    )
    _apply_alpha(big, alpha_pct=14)

    # ── Eyebrow ───────────────────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=120, y_px=470, w_px=820, h_px=28,
        prompt_text="CHAPTER 02 · DESIGN",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.OFF_WHITE_2, uppercase=True,
        tracking_em=0.115,
    )

    # ── M-stripe divider on dark band ─────────────────────────────────────
    add_m_stripe(layout, x_px=120, y_px=518, w_px=420, h_px=4)

    # ── Chapter title ─────────────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=120, y_px=560, w_px=820, h_px=280,
        prompt_text="Form follows\nfunction.",
        size_px=T.SIZE_PX["slide_title"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.WHITE,
        tracking_em=0,
        line_height=1.05,
    )

    # ── Subtitle ──────────────────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=120, y_px=860, w_px=820, h_px=80,
        prompt_text="The new design language — sharper, calmer, more deliberate.",
        size_px=T.SIZE_PX["lead"],
        weight="light",
        font=T.FONT_DISPLAY,
        color=T.OFF_WHITE_2,
        tracking_em=0,
        line_height=1.4,
    )
