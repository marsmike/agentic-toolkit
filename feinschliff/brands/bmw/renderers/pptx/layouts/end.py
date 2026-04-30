"""BMW · End — closing slide on white canvas with dark navy hero band.

Mirrors the cover composition (light → dark band) for symmetry. BMW Blue
appears only as the chevron CTA — the spec forbids it as hero fill.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_text_placeholder, paint_chrome,
    add_m_stripe, add_chevron_link,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · End"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["paper"])  # white canvas

    # ── Bottom dark navy band (mirrors cover) ─────────────────────────────
    band_y = int(1080 * 0.58)  # band starts at ~626
    add_rect(layout, 0, band_y, 1920, 1080 - band_y, fill=T.SURFACE_DARK)

    # ── M-stripe on the boundary ──────────────────────────────────────────
    add_m_stripe(layout, x_px=0, y_px=band_y - 4, w_px=1920, h_px=4)

    # ── Chrome — light variant on the upper canvas ───────────────────────
    paint_chrome(layout, variant="light", pgmeta="THANK YOU")

    # ── "Thank you." — 700 white on dark band, large but not overpowering ─
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=120, y_px=band_y + 80, w_px=1680, h_px=200,
        prompt_text="Thank you.",
        size_px=T.SIZE_PX["slide_title"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.WHITE,
        tracking_em=0,
        line_height=1.05,
    )

    # ── Caption — UPPERCASE label-uppercase ───────────────────────────────
    add_text_placeholder(
        layout, idx=10, name="Caption", ph_type="body",
        x_px=120, y_px=band_y + 290, w_px=1680, h_px=30,
        prompt_text="BMW · 2026 SHOWCASE",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.OFF_WHITE_2,
        uppercase=True,
        tracking_em=0.115,
    )

    # ── Chevron link — DISCOVER › on dark band ───────────────────────────
    add_chevron_link(
        layout, x_px=120, y_px=band_y + 360, w_px=400, h_px=30,
        text="DISCOVER", color=T.WHITE,
    )
