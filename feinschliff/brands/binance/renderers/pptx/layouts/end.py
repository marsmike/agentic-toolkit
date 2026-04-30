"""Binance · End — closing slide with the iconic light footer reset.

Per DESIGN.md `footer-light`: every Binance page closes with a light gray
footer surface (`surface-soft-light` / #FAFAFA) below the dark canvas — a
deliberate inversion that visually closes the page. We translate that to
the deck's End slide:

  - Top 75% of the slide: deep crypto-black canvas with a centred yellow
    display headline ("Trade on Binance.") and a yellow signup pill below.
  - Bottom 25%: the light footer-reset band — `surface-soft-light` fill,
    ink-on-light caption text, and the wordmark in pure ink. The chrome
    flips to `variant="ink"` so the lockup reads black-on-#FAFAFA.

This is Binance's most distinctive layout choice — the light footer on a
dark page — and it's the right closing register for the deck.
"""
from __future__ import annotations

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

import theme as T
from components import (
    add_rect, add_text_placeholder, add_signup_pill,
    set_layout_background, set_layout_name,
)
from components.chrome import (
    add_logo, add_pgmeta, add_footer_left, add_footer_right,
    _append_slide_num_field,
)

NAME = "Feinschliff · End"


def build(layout):
    set_layout_name(layout, NAME)
    # Dark crypto-black canvas for the upper band.
    set_layout_background(layout, T.HEX["surface_dark"])

    # ─── Light footer-reset band (lower 25%) ─────────────────────────────
    # 1080 × 0.25 = 270px tall. Bottom band painted as a flat rect; chrome
    # ink-on-light is then placed inside it.
    band_y, band_h = 810, 270
    add_rect(layout, 0, band_y, 1920, band_h, fill=T.SURFACE_SOFT_LIGHT)

    # Chrome — split: TOP wordmark sits over the dark canvas (yellow lockup,
    # silver chrome); but the bottom footer-left + footer-right + slide
    # number need to sit INSIDE the light band, in ink-on-light. We can't
    # use `paint_chrome(variant="ink")` because that would also flip the top
    # wordmark to ink. So we paint the parts manually.
    add_logo(layout, variant="dark")              # yellow lockup top-left
    add_pgmeta(layout, "EXCHANGE · 2026", color=T.SILVER)  # silver top-right

    # Footer pieces sit inside the light band — explicit ink color.
    add_footer_left(layout, "JAN 2026 · SHOWCASE", color=T.INK)
    tb = add_footer_right(layout, "SLIDE ", color=T.INK)
    _append_slide_num_field(tb, total=None, color=T.INK)

    # Footer caption — small uppercase mono, sits centred in the light band.
    add_text_placeholder(
        layout, idx=10, name="Caption", ph_type="body",
        x_px=100, y_px=900, w_px=1720, h_px=32,
        prompt_text="BINANCE · DESIGN SYSTEM · v1.0 · 2026",
        size_px=T.SIZE_PX["eyebrow"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.INK, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
        align="c",
    )

    # ─── Upper band: centred yellow display headline + pill ─────────────
    # Headline at display-lg (huge / 120px), one line, sits in the upper
    # half of the dark band. Pill anchored ~50px below the headline so it
    # never overlaps multi-line copy.
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=300, w_px=1720, h_px=200,
        prompt_text="Trade on Binance.",
        size_px=T.SIZE_PX["huge"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT,
        tracking_em=float(T.HEADLINE_RULE.get("tracking-em", -0.02)),
        line_height=1.0,
        align="c",
    )

    # Yellow signup pill below the headline, centred horizontally.
    pill_w, pill_h = 240, 80
    add_signup_pill(
        layout,
        x_px=(1920 - pill_w) / 2, y_px=540,
        label="Sign Up", w_px=pill_w, h_px=pill_h,
    )
