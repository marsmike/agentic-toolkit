"""Binance · Quote — display-md pull quote on the deep crypto-black canvas.

Yellow ▌ section-marker + sentence-case 600 quote in pure white +
attribution in muted silver. Matches the trading-floor editorial register
— Binance does not use serif quote glyphs ("smart quotes"); it uses
straight quotes inside a confident display run.
"""
from __future__ import annotations

import theme as T
from components import (
    add_section_marker, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Quote"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="VOICE")

    # Yellow ▌ marker stretches the height of the quote stack.
    add_section_marker(layout, x_px=100, y_px=380, h_px=440)

    add_text_placeholder(
        layout, idx=0, name="Quote", ph_type="title",
        x_px=140, y_px=380, w_px=1640, h_px=440,
        prompt_text=("“Trust isn’t a brand color. It’s the price feed "
                     "you can verify and the funds you can withdraw, every day.”"),
        size_px=T.SIZE_PX["quote"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.GRAPHITE,
        tracking_em=-0.015, line_height=1.15,
    )

    add_text_placeholder(
        layout, idx=10, name="Attribution", ph_type="body",
        x_px=140, y_px=860, w_px=1720, h_px=30,
        prompt_text="BINANCE · TRUST GUIDELINE",
        size_px=T.SIZE_PX["quote_attr"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.SILVER, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )
