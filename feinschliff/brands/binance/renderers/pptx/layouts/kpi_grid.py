"""Binance · KPI Grid — 4 trust-badge cards on dark canvas.

Per DESIGN.md `trust-badge` and the homepage hero stat block ("No.1
Trading Volume", "No.1 Customer Service", "316M users"). Each card is an
elevated `surface-card-dark` block (paper / #1E2329) at radius 12px, no
shadow — Binance is shadow-free per the policy block. Yellow KPI value
in BinancePlex 700, UPPERCASE label below in muted silver, trading-up /
trading-down chip in the corner of one cell to anchor the trading-floor
voice.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rounded_rect, add_text, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header

NAME = "Feinschliff · KPI Grid"

SAMPLES = [
    # (value, unit, key, delta, direction)
    ("316",  "M",  "USERS WORLDWIDE",      "+3.1% YoY",   "up"),
    ("$429", "M",  "FUNDS RECOVERED",      "Since 2018",  "neutral"),
    ("No.1", "",   "TRADING VOLUME",       "Global rank", "neutral"),
    ("100",  "%",  "BINANCE-AUDITED",      "PoR · Nov '26", "up"),
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="EXCHANGE · 2026")

    content_header(
        layout,
        eyebrow="EXCHANGE · 2026 · TRUST",
        title="Why Binance.",
    )

    # 4 cards across 1720px content width with 32px gutters.
    gap = 32
    n = 4
    card_w = (1720 - (n - 1) * gap) / n  # = 401
    card_h = 360
    y0 = 540

    for i, (value, unit, key, delta, direction) in enumerate(SAMPLES):
        x = 100 + i * (card_w + gap)

        # Card surface — paper (#1E2329), radius 12, no shadow.
        add_rounded_rect(
            layout, x, y0, card_w, card_h,
            radius_px=T.RADIUS["card"],
            fill=T.PAPER,
        )

        pad = 32
        idx_base = 20 + i * 4

        # Yellow KPI value — BinancePlex 700. Sized to fit the 401px card
        # width without wrapping ("316M", "$429M", "No.1", "100%" all fit at
        # 88px). Width is unconstrained-tight so multi-character values
        # ($429M) lay out on one line.
        add_text_placeholder(
            layout, idx=idx_base, name=f"KPI {i+1} Value", ph_type="body",
            x_px=x + pad, y_px=y0 + pad + 30,
            w_px=card_w - 2 * pad, h_px=140,
            prompt_text=value + (unit if unit else ""),
            size_px=88,
            weight="bold", font=T.FONT_MONO,
            color=T.ACCENT,
            tracking_em=-0.02, line_height=1.0,
        )

        # UPPERCASE muted label — chip-rule voice.
        add_text_placeholder(
            layout, idx=idx_base + 1, name=f"KPI {i+1} Key", ph_type="body",
            x_px=x + pad, y_px=y0 + pad + 200,
            w_px=card_w - 2 * pad, h_px=28,
            prompt_text=key,
            size_px=T.SIZE_PX["kpi_key"],
            weight="semibold", font=T.FONT_DISPLAY,
            color=T.SILVER, uppercase=True,
            tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
        )

        # Delta caption — BinancePlex 500, green/red text per direction
        # (trading-up / trading-down) or steel for neutral.
        delta_color = {
            "up":      T.TRADING_UP,
            "down":    T.TRADING_DOWN,
            "neutral": T.STEEL,
        }.get(direction, T.STEEL)
        delta_glyph = {"up": "▲ ", "down": "▼ ", "neutral": ""}.get(direction, "")
        add_text_placeholder(
            layout, idx=idx_base + 2, name=f"KPI {i+1} Delta", ph_type="body",
            x_px=x + pad, y_px=y0 + pad + 240,
            w_px=card_w - 2 * pad, h_px=28,
            prompt_text=delta_glyph + delta,
            size_px=T.SIZE_PX["kpi_delta"],
            weight="medium", font=T.FONT_MONO,
            color=delta_color,
        )
