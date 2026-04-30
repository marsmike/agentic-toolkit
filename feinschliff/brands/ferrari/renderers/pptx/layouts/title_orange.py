"""Ferrari · Title · Accent — Rosso Corsa livery cover.

Per Ferrari DESIGN.md, Rosso Corsa is functional-only — primary CTAs, the
Cavallino mark, F1 race-position highlights. Full-bleed Rosso Corsa is
permitted ONLY in the `livery-band` component context (chapter dividers,
standout livery callouts) and on the cover slot when used as a deliberate
"livery" cover treatment. This layout claims the cover as a livery
treatment: a wide Rosso Corsa band carries the headline; the rest of the
slide stays cinematic dark.

Composition (Ferrari DESIGN.md `livery-band` + `hero-band-cinema`):
  * Top 60% — near-black canvas (#181818) with chrome
  * Bottom 40% — full-bleed Rosso Corsa livery band
  * Lower-left UPPERCASE eyebrow on the red, weight 700 / 0.1em tracking
  * Display-mega 500 / -0.02em headline on the red — sentence case, white
"""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Title · Accent"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])  # near-black
    paint_chrome(layout, variant="dark", pgmeta="Ferrari · 2026")

    # Bottom Rosso Corsa livery band — bottom 40% of slide
    band_y = 648  # 1080 * 0.6
    band_h = 1080 - band_y
    add_rect(layout, 0, band_y, 1920, band_h, fill=T.ACCENT)

    # ── Eyebrow on the red — caption-uppercase voice, white ──────────────
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=96, y_px=band_y + 96, w_px=1600, h_px=28,
        prompt_text="THE NEXT GENERATION · 2026",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.INK, uppercase=True,
        tracking_em=0.1,
    )

    # ── Hero headline — slide-title 500 -0.02em, sentence case, white ────
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=96, y_px=band_y + 140, w_px=1700, h_px=200,
        prompt_text="Made in\nMaranello.",
        size_px=T.SIZE_PX["slide_title"],
        weight="medium",  # 500 — Ferrari DESIGN.md never bolds display
        font=T.FONT_DISPLAY,
        color=T.INK,
        tracking_em=-0.02,
        line_height=1.05,
    )
