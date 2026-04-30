"""Typography components.

These wrap `add_text` with the Feinschliff type-scale tokens so layouts don't need
to remember the sizes. Each function mirrors a named CSS class in the HTML
reference deck (.display, .huge, .slide-title, .eyebrow, .body, .rule).
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

import theme as T
from components.primitives import add_text, add_line


# ─── Rule — short filled bar used as a section marker ─────────────────────
# Default colour is Binance Yellow — content layouts that want a different
# colour pass it explicitly. Width/height defaults match the legacy 80×4
# horizontal-rule shape so existing layouts that haven't been rebuilt yet
# stay byte-stable; the bespoke layouts use `add_section_marker` (vertical
# yellow ▌) directly.
def add_rule(
    target,
    x_px: float,
    y_px: float,
    *,
    width_px: float = 80,
    height_px: float = 4,
    color: RGBColor = T.ACCENT,
):
    return add_line(target, x_px, y_px, width_px, height_px, color)


# ─── Eyebrow — UPPERCASE display SemiBold tracked label above a title ─────
# Binance chrome runs the chip-rule type voice — UPPERCASE, BinanceNova,
# weight 600, 1.4px tracking. NOT BinancePlex/mono — that's reserved for
# numerics per DESIGN.md.
def add_eyebrow(target, x_px, y_px, text, *, color=T.ACCENT, w_px=1600, h_px=30):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["eyebrow"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=color, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )


# ─── Slide title — bold (default 64px / weight 600) ───────────────────────
def add_slide_title(target, x_px, y_px, text, *, color=T.OFF_WHITE, w_px=1720, h_px=80):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["slide_title"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=color, tracking_em=-0.015, line_height=1.1,
    )


# ─── Display — hero h1 register, BOLD per Binance DESIGN.md ───────────────
# Display weight is 700 (bold) — the trading-platform "this number must
# read at a glance" weight. Binance NEVER softens display to weight 400 the
# way Airtable or Stripe does.
def add_display(target, x_px, y_px, text, *, color=T.OFF_WHITE, w_px=1720, h_px=320, size_px=None, align=PP_ALIGN.LEFT):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=size_px or T.SIZE_PX["display"],
        weight="bold", font=T.FONT_DISPLAY,
        color=color,
        tracking_em=float(T.HEADLINE_RULE.get("tracking-em", -0.02)),
        line_height=1.0, align=align,
    )


# ─── Huge — 120px BOLD (display-lg / 'FUNDS ARE SAFU' brand-claim voice) ──
def add_huge(target, x_px, y_px, text, *, color=T.OFF_WHITE, w_px=1400, h_px=260, size_px=None):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=size_px or T.SIZE_PX["huge"],
        weight="bold", font=T.FONT_DISPLAY,
        color=color,
        tracking_em=float(T.HEADLINE_RULE.get("tracking-em", -0.02)),
        line_height=1.05,
    )


# ─── Subtitle — 32px regular ──────────────────────────────────────────────
def add_subtitle(target, x_px, y_px, text, *, color=T.STEEL, w_px=1600, h_px=200):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["sub"],
        weight="regular", font=T.FONT_DISPLAY,
        color=color, tracking_em=0, line_height=1.4,
    )


# ─── Body — 26px regular, graphite by default ─────────────────────────────
def add_body(target, x_px, y_px, text, *, color=T.GRAPHITE, w_px=820, h_px=200):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["body"], color=color, line_height=1.5,
    )


# ─── Mono caption — 16px mono uppercase tracked (figure notes, tags) ──────
def add_mono_caption(target, x_px, y_px, text, *, color=T.GRAPHITE, w_px=1200, h_px=24, size_px=16):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=size_px, font=T.FONT_MONO,
        color=color, uppercase=True, tracking_em=0.1,
    )
