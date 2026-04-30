"""Binance · Chapter · Ink — full-dark chapter divider.

Yellow ▌ section-marker + UPPERCASE display-lg headline ('FUNDS ARE SAFU'
brand-claim voice) on the deep crypto-black canvas. Right half carries an
optional editorial photograph (placeholder) — when omitted, the headline
spans the full canvas width.
"""
from __future__ import annotations

import theme as T
from components import (
    add_section_marker, add_text_placeholder,
    add_image_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Chapter · Ink + Picture"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])

    # Right-half dark image placeholder (the lifestyle / trading-floor /
    # 3D coin-stack illustration). Fixed rect so chrome stays on top.
    add_image_placeholder(
        layout, 960, 0, 960, 1080, label="Chapter image · 16:9", dark=True,
    )

    paint_chrome(layout, variant="dark", pgmeta="CHAPTER 02")

    # Yellow ▌ marker + huge UPPERCASE display headline.
    # Marker height matches the headline cap-height — 3 lines × 120px ×
    # 1.05 lh ≈ 380px.
    add_section_marker(layout, x_px=100, y_px=440, h_px=380)

    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=140, y_px=440, w_px=820, h_px=28,
        prompt_text="CHAPTER · INK",
        size_px=T.SIZE_PX["eyebrow"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )

    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=140, y_px=490, w_px=820, h_px=380,
        prompt_text="02\nFunds Are\nSafu.",
        size_px=T.SIZE_PX["huge"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.GRAPHITE,
        tracking_em=float(T.HEADLINE_RULE.get("tracking-em", -0.02)),
        line_height=1.05,
    )
