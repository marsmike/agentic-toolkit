"""BMW · Quote — full-bleed dark navy editorial pull-quote.

BMW Blue is action-only — never a hero fill. Quotes earn the dark navy
hero band (one of the page-rhythm beats) with the quote in 700 white,
M-stripe at top as the editorial signature, attribution in
label-uppercase 1.5px tracked.
"""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, paint_chrome,
    add_m_stripe,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Quote"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="VOICE")

    # ── M-stripe at top — editorial signature ─────────────────────────────
    add_m_stripe(layout, x_px=0, y_px=144, w_px=1920, h_px=4)

    # ── Quote — 700 weight, BMW Type Next, white on dark ─────────────────
    # No light quotation marks; the quote lives on the page typographically.
    add_text_placeholder(
        layout, idx=0, name="Quote", ph_type="title",
        x_px=120, y_px=380, w_px=1680, h_px=440,
        prompt_text=("“Form follows function. Engineer for clarity, not "
                     "for spectacle.”"),
        size_px=T.SIZE_PX["quote"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.WHITE,
        tracking_em=0,
        line_height=1.15,
    )

    # ── Attribution — UPPERCASE label-uppercase 700 1.5px tracked ────────
    add_text_placeholder(
        layout, idx=10, name="Attribution", ph_type="body",
        x_px=120, y_px=880, w_px=1680, h_px=30,
        prompt_text="BMW DESIGN SYSTEM · VOICE GUIDELINE",
        size_px=T.SIZE_PX["quote_attr"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.HIGHLIGHT,
        uppercase=True,
        tracking_em=0.115,
    )
