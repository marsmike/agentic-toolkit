"""Binance · Components Showcase — UI-kit reference slide.

Two `surface-card-dark` panels side by side on the deep crypto-black
canvas, displaying the Binance UI vocabulary:

  - Left panel: signup pill (yellow), secondary pill (ink), inline
    trading-up / trading-down chip pair, trust-badge sample.
  - Right panel: a 3-row miniature markets-ticker (the brand's product
    DNA chrome — coin disc, pair, price, %, chevron), plus a hairline
    sample.

Reference rather than content — the buttons / chips / ticker are fixed
decoration showing the Binance UI kit. Only the top eyebrow + title are
placeholders.
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

import theme as T
from components import (
    add_text, add_rounded_rect, add_signup_pill, add_ticker_row,
    add_hairline, paint_chrome, set_layout_background, set_layout_name,
)
from layouts._shared import content_header

NAME = "Feinschliff · Components Showcase"


def _hex(s: str) -> RGBColor:
    return RGBColor(int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="UI KIT")

    content_header(
        layout,
        eyebrow="UI LIBRARY",
        title="Pills, ticker, badges.",
    )

    # Two panels, 32px gap → col width = (1720 - 32) / 2 = 844
    panel_w = 844
    panel_h = 480
    gap = 32
    y0 = 540
    x_left = 100
    x_right = x_left + panel_w + gap

    _left_panel(layout, x_left, y0, panel_w, panel_h)
    _right_panel(layout, x_right, y0, panel_w, panel_h)


# ─── Left panel: pills + chips ─────────────────────────────────────────────
def _left_panel(layout, x: float, y: float, w: float, h: float):
    """Surface-card with pill CTA pair + trading chip pair + a trust-badge."""
    add_rounded_rect(layout, x, y, w, h, radius_px=T.RADIUS["card"], fill=T.PAPER)

    pad = 32
    inner_x = x + pad

    _panel_label(layout, inner_x, y + pad, "PILLS")

    pill_y = y + pad + 60
    add_signup_pill(layout, inner_x,        pill_y, "Sign Up",  w_px=200, h_px=64, variant="primary")
    add_signup_pill(layout, inner_x + 220,  pill_y, "Log In",   w_px=200, h_px=64, variant="ink")

    _panel_label(layout, inner_x, y + pad + 170, "TRADING CHIPS")

    chip_y = y + pad + 220
    _trading_chip(layout, inner_x,        chip_y, "BUY",  fill=T.TRADING_UP)
    _trading_chip(layout, inner_x + 130,  chip_y, "SELL", fill=T.TRADING_DOWN)

    _panel_label(layout, inner_x, y + pad + 320, "TRUST BADGE")

    badge_y = y + pad + 370
    badge_w = 360
    badge_h = 56
    add_rounded_rect(layout, inner_x, badge_y, badge_w, badge_h,
                     radius_px=T.RADIUS["lg"], fill=T.PAPER_2)
    add_text(layout, inner_x + 20, badge_y, 80, badge_h,
             "No.1",
             size_px=24, weight="bold", font=T.FONT_MONO,
             color=T.ACCENT, anchor=MSO_ANCHOR.MIDDLE)
    add_text(layout, inner_x + 110, badge_y, badge_w - 130, badge_h,
             "TRADING VOLUME",
             size_px=T.SIZE_PX["chip"],
             weight="semibold", font=T.FONT_DISPLAY,
             color=T.OFF_WHITE, uppercase=True,
             tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
             anchor=MSO_ANCHOR.MIDDLE)


# ─── Right panel: miniature markets-ticker ─────────────────────────────────
def _right_panel(layout, x: float, y: float, w: float, h: float):
    """Surface-card with a 3-row markets-table preview + hairline sample."""
    add_rounded_rect(layout, x, y, w, h, radius_px=T.RADIUS["card"], fill=T.PAPER)

    pad = 32
    inner_x = x + pad
    inner_w = w - 2 * pad

    _panel_label(layout, inner_x, y + pad, "MARKETS TICKER")

    rows = [
        ("BTC/USDT", "B", "F7931A", "79,065.04", "+0.45%", "up"),
        ("ETH/USDT", "E", "627EEA", "2,348.91",  "+1.20%", "up"),
        ("SOL/USDT", "S", "9945FF", "151.62",    "−0.62%", "down"),
    ]
    row_y = y + pad + 60
    for i, (symbol, letter, hex_color, price, pct, direction) in enumerate(rows):
        add_ticker_row(
            layout, inner_x, row_y, inner_w,
            symbol=symbol, icon_letter=letter,
            icon_color=_hex(hex_color),
            price=price, change_pct=pct, direction=direction,
            show_hairline=(i < len(rows) - 1),
        )
        row_y += 90

    _panel_label(layout, inner_x, y + pad + 360, "HAIRLINE")
    add_hairline(layout, inner_x, y + pad + 410, inner_w)


def _trading_chip(layout, x, y, label, *, fill):
    """Small trading-up / trading-down inline chip — 4px radius, on dark."""
    add_rounded_rect(layout, x, y, 100, 36, radius_px=T.RADIUS["chip"], fill=fill)
    add_text(layout, x, y, 100, 36, label,
             size_px=T.SIZE_PX["chip"],
             weight="bold", font=T.FONT_DISPLAY,
             color=T.GRAPHITE, uppercase=True,
             tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
             align=PP_ALIGN.CENTER,
             anchor=MSO_ANCHOR.MIDDLE)


def _panel_label(layout, x: float, y: float, text: str):
    """Small UPPERCASE display semibold label above each component row."""
    add_text(
        layout, x, y, 400, 24, text,
        size_px=T.SIZE_PX["chip"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.SILVER, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )
