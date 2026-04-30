"""Binance · Full-bleed Cover — lifestyle photo + yellow CTA overlay.

Translates the homepage's "Trade on the go" lifestyle-photo treatment to a
deck cover. Full-bleed image area (placeholder), with a small dark
`surface-card-dark` block in the lower-left carrying eyebrow + title +
yellow signup pill — the iconic CTA that overlays every Binance lifestyle
photo per DESIGN.md `feature-photo-card`.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rounded_rect, add_signup_pill, add_text_placeholder,
    paint_chrome, set_layout_background, set_layout_name,
)
from components.media import add_image_placeholder

NAME = "Feinschliff · Full-bleed Cover"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])

    # Full-bleed image placeholder behind everything.
    add_image_placeholder(
        layout, 0, 0, 1920, 1080, label="Lifestyle photo · 16:9", dark=True,
    )

    # Chrome — silver on dark, sits over the image's top region.
    paint_chrome(layout, variant="dark", pgmeta="APP · 2026")

    # Lower-left CTA card — `surface-card-dark` 12px-radius block per
    # DESIGN.md `feature-photo-card` / `qr-promo-card`. Sits over the
    # bottom-left vignette of the photograph. Sized to fit eyebrow (28) +
    # title (2 × 56 lines) + pill (64) + 32px gaps = ~ 380 — round to 400.
    card_x, card_y, card_w, card_h = 100, 600, 700, 400
    add_rounded_rect(
        layout, card_x, card_y, card_w, card_h,
        radius_px=T.RADIUS["card"],
        fill=T.PAPER,
    )

    pad = 32
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=card_x + pad, y_px=card_y + pad,
        w_px=card_w - 2 * pad, h_px=28,
        prompt_text="APP · 2026",
        size_px=T.SIZE_PX["eyebrow"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )

    # Title — 56px so 2 lines fit in 140px height with 1.1 line-height.
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=card_x + pad, y_px=card_y + pad + 50,
        w_px=card_w - 2 * pad, h_px=160,
        prompt_text="Trade on the go.\nAnywhere, anytime.",
        size_px=56,
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.GRAPHITE,
        tracking_em=-0.015, line_height=1.1,
    )

    # Yellow signup pill anchored bottom-left of the card.
    add_signup_pill(
        layout,
        x_px=card_x + pad, y_px=card_y + card_h - pad - 64,
        label="Get the App", w_px=240, h_px=64,
    )
