"""Binance · Title · Accent — the Arena Gradient launch hero.

Yellow→dark vertical linear gradient covers the full slide. The Binance
DESIGN.md `arena-hero-gradient` treatment, used scarcely (1-2 times per
deck) for product-launch / event / campaign hero moments. The yellow
voltage at the top fades to crypto-black at the bottom; the prize-pool
display number sits in the centre transition zone in BinancePlex 700.

Composition:
  - Full-bleed `add_arena_gradient` (yellow → surface-dark, vertical).
  - Top: `EXCHANGE · LIVE` eyebrow in ink (reads on yellow upper band).
  - Middle: huge BinancePlex prize-pool number ("$4,000,000 USDT") +
    sub-headline in pure white (reads on the transition / dark lower).
  - Bottom: centred yellow signup pill ("Join Now"), 280×80.

NAME stays "Feinschliff · Title · Accent" so slides.py keeps working.
"""
from __future__ import annotations

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

import theme as T
from components import (
    add_text_placeholder, add_arena_gradient,
    add_signup_pill, paint_chrome,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Title · Accent"


def build(layout):
    set_layout_name(layout, NAME)
    # Background is the gradient itself; set canvas to surface-dark so the
    # bottom of the gradient blends into anything painted below it.
    set_layout_background(layout, T.HEX["surface_dark"])

    # Vertical yellow→dark gradient covers the full canvas.
    add_arena_gradient(layout, x_px=0, y_px=0, w_px=1920, h_px=1080)

    # Chrome reads ink-on-yellow at the top — the upper third of the gradient
    # is yellow, so chrome stays in INK for contrast (variant="accent").
    paint_chrome(layout, variant="accent", pgmeta="EXCHANGE · LIVE")

    # ─── Eyebrow ─ ink on yellow, top-third of the canvas ────────────────
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=100, y_px=300, w_px=1720, h_px=30,
        prompt_text="EXCHANGE · LIVE",
        size_px=T.SIZE_PX["eyebrow"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.INK, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
        align="c",
    )

    # ─── Huge BinancePlex prize-pool number ──────────────────────────────
    # Centre transition zone. BinancePlex 700, slight negative tracking,
    # pure white so it reads against both the yellow upper third and the
    # dark lower transition.
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=380, w_px=1720, h_px=240,
        prompt_text="$4,000,000",
        size_px=T.SIZE_PX["display"],
        weight="bold", font=T.FONT_MONO,
        color=T.GRAPHITE,
        tracking_em=-0.025, line_height=1.0,
        align="c",
    )

    # Sub-headline below the number — section-head register, white.
    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=100, y_px=640, w_px=1720, h_px=80,
        prompt_text="USDT prize pool · Futures Masters Arena",
        size_px=T.SIZE_PX["sub"],
        weight="regular", font=T.FONT_DISPLAY,
        color=T.GRAPHITE,
        tracking_em=0, line_height=1.2,
        align="c",
    )

    # ─── Bottom: centered yellow signup pill ─────────────────────────────
    pill_w, pill_h = 240, 80
    pill_x = (1920 - pill_w) / 2
    add_signup_pill(layout, x_px=pill_x, y_px=860, label="Join Now",
                    w_px=pill_w, h_px=pill_h)
