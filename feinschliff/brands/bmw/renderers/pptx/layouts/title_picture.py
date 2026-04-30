"""BMW · Title · Half-photo — split cover with model render right.

Per BMW DESIGN.md photography is edge-to-edge with no shadow; the right
half holds a 16:10 model render, left half holds the headline stack on
white canvas. Hairline rule above the eyebrow is the engineered touchpoint.
"""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, add_image_placeholder,
    add_chevron_link, add_hairline,
    paint_chrome, set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Title + Picture"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["paper"])

    # ── Right-half edge-to-edge photo (no shadow) ──────────────────────
    add_image_placeholder(
        layout, 960, 0, 960, 1080, label="Model render · 16:10",
    )

    paint_chrome(layout, variant="light", pgmeta="MODEL OVERVIEW")

    # ── Hairline + eyebrow stack on left half ──────────────────────────
    add_hairline(layout, 120, 460, 80, color=T.INK, weight_px=2)
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=120, y_px=480, w_px=820, h_px=30,
        prompt_text="MODELS · BMW iX3",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.SILVER, uppercase=True,
        tracking_em=0.115,
    )

    # ── Headline ────────────────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=120, y_px=540, w_px=820, h_px=240,
        prompt_text="Engineered\nin Munich.",
        size_px=T.SIZE_PX["slide_title"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.INK,
        tracking_em=0,
        line_height=1.05,
    )

    # ── Body — Light 300 ────────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=11, name="Body", ph_type="body",
        x_px=120, y_px=790, w_px=780, h_px=140,
        prompt_text=("The left half holds the headline stack; the right half holds the "
                     "model render edge-to-edge — no shadow, no border. Depth comes "
                     "from photo subject + light, never from a frame."),
        size_px=T.SIZE_PX["body"],
        weight="light",
        font=T.FONT_DISPLAY,
        color=T.STEEL,
        line_height=1.55,
    )

    # ── BMW Blue chevron CTA ────────────────────────────────────────────
    add_chevron_link(
        layout, x_px=120, y_px=950, w_px=400, h_px=30,
        text="LEARN MORE", color=T.ACCENT,
    )
