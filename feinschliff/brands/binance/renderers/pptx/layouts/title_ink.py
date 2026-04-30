"""Binance · Title · Ink — the Markets-Hero cover.

Half hero headline + signup pill, half markets-table-card with five live
ticker rows. The Binance equivalent of Spotify's album-art-tile cover and
BMW's M-stripe-rule cover — translates the homepage's signature surface
("316,258,026 USERS TRUST US" + the 5-row markets table) into a single
deck slide.

Per DESIGN.md `markets-table-card` + `hero-band-dark` + `button-primary-pill`:
  - Background: `surface-dark` (#0B0E11) — Binance's deep crypto-black.
  - Left half: yellow eyebrow ('EXCHANGE · 2026') + display headline 96px /
    700 / -0.02em + sub-headline in steel + yellow signup pill.
  - Right half: a `markets-table-card` (paper #1E2329, radius 12, padding 32),
    tab row at top, five `add_ticker_row` calls — placeholder coin pairs
    BTC / ETH / SOL / BNB / USDT, two with green ▲, one with red ▼,
    others neutral.
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

import theme as T
from components import (
    add_text, add_text_placeholder, add_rounded_rect, add_rect,
    add_signup_pill, add_ticker_row, add_hairline, paint_chrome,
    set_layout_background, set_layout_name,
)


NAME = "Feinschliff · Title · Ink"

# Placeholder coin discs — colour-evoking, non-licensed. Each disc carries
# a single ink letter (the symbol's first char) — abstracts the brand glyph
# without claiming the licensed coin marks.
TICKERS = [
    # (symbol, icon_letter, icon_color_hex, price, change_pct, direction)
    ("BTC/USDT", "B", "F7931A", "79,065.04", "+0.45%", "up"),
    ("ETH/USDT", "E", "627EEA", "2,348.91",  "+1.20%", "up"),
    ("SOL/USDT", "S", "9945FF", "151.62",    "−0.62%", "down"),
    ("BNB/USDT", "B", "F0B90B", "612.30",    "+0.18%", "up"),
    ("USDT/USD", "T", "26A17B", "1.0001",    "0.00%",  "neutral"),
]


def _hex(s: str) -> RGBColor:
    return RGBColor(int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="EXCHANGE · 2026")

    # ─── Left half: hero stack ────────────────────────────────────────────
    # Yellow eyebrow → display headline → sub → signup pill + log-in link.
    left_x = 100
    left_w = 820

    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=left_x, y_px=320, w_px=left_w, h_px=28,
        prompt_text="EXCHANGE · 2026",
        size_px=T.SIZE_PX["eyebrow"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )

    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=left_x, y_px=370, w_px=left_w, h_px=300,
        prompt_text="316M users\ntrust Binance.",
        size_px=96,
        weight="bold", font=T.FONT_DISPLAY,
        color=T.GRAPHITE,
        tracking_em=float(T.HEADLINE_RULE.get("tracking-em", -0.02)),
        line_height=1.05,
    )

    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=left_x, y_px=720, w_px=left_w, h_px=120,
        prompt_text="The world's largest crypto exchange — spot, futures, savings, and Web3.",
        size_px=T.SIZE_PX["lead"],
        weight="regular", font=T.FONT_DISPLAY,
        color=T.STEEL, tracking_em=0, line_height=1.4,
    )

    # Yellow signup pill + ghost "Log In" text-link to its right.
    add_signup_pill(layout, x_px=left_x, y_px=870, label="Sign Up", w_px=200, h_px=64)
    add_text(
        layout, left_x + 220, 870, 240, 64,
        "Already a user? Log In",
        size_px=T.SIZE_PX["btn"],
        weight="regular", font=T.FONT_DISPLAY,
        color=T.OFF_WHITE,
        anchor=MSO_ANCHOR.MIDDLE,
    )

    # ─── Right half: markets-table-card ───────────────────────────────────
    # Card geometry: x=1000, y=200, w=820, h=720 → fits between top chrome
    # (y=80) and footer (y=1010) with 120px top margin and 90px bottom.
    card_x, card_y = 1000, 200
    card_w, card_h = 820, 720
    card_pad = 32

    add_rounded_rect(
        layout, card_x, card_y, card_w, card_h,
        radius_px=T.RADIUS["card"],
        fill=T.PAPER,
    )

    # Tab row at top: POPULAR (active, yellow) · NEW · TOP GAINERS.
    tab_y = card_y + card_pad
    tabs = [("POPULAR", T.ACCENT), ("NEW LISTING", T.SILVER), ("TOP GAINERS", T.SILVER)]
    tab_x = card_x + card_pad
    for label, color in tabs:
        add_text(
            layout, tab_x, tab_y, 200, 28, label,
            size_px=T.SIZE_PX["chip"],
            weight="semibold", font=T.FONT_DISPLAY,
            color=color, uppercase=True,
            tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
        )
        tab_x += 200

    # Yellow underline below the active tab (POPULAR).
    add_rect(layout, card_x + card_pad, tab_y + 36, 88, 2, fill=T.ACCENT)

    # Hairline below tab row.
    add_hairline(
        layout,
        card_x + card_pad, tab_y + 56,
        card_w - 2 * card_pad,
    )

    # Table column header row — PAIR · LAST PRICE · 24H CHANGE.
    header_y = tab_y + 80
    header_color = T.SILVER
    add_text(
        layout, card_x + card_pad + 46, header_y, 220, 24,
        "PAIR",
        size_px=T.SIZE_PX["col_num"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=header_color, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )
    # Price column header right-aligned over the price column.
    add_text(
        layout, card_x + card_w - card_pad - 40 - 180 - 240, header_y, 240, 24,
        "LAST PRICE",
        size_px=T.SIZE_PX["col_num"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=header_color, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
        align=PP_ALIGN.RIGHT,
    )
    add_text(
        layout, card_x + card_w - card_pad - 40 - 180, header_y, 180, 24,
        "24H CHANGE",
        size_px=T.SIZE_PX["col_num"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=header_color, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
        align=PP_ALIGN.RIGHT,
    )

    # Hairline below the column header.
    add_hairline(
        layout,
        card_x + card_pad, header_y + 32,
        card_w - 2 * card_pad,
    )

    # Five ticker rows.
    row_pitch = 90
    row_y = header_y + 50
    for symbol, icon_letter, icon_hex, price, pct, direction in TICKERS:
        add_ticker_row(
            layout,
            card_x + card_pad, row_y,
            card_w - 2 * card_pad,
            symbol=symbol,
            icon_letter=icon_letter,
            icon_color=_hex(icon_hex),
            price=price,
            change_pct=pct,
            direction=direction,
            show_hairline=(symbol != TICKERS[-1][0]),
        )
        row_y += row_pitch
