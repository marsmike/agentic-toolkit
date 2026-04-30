"""Ferrari · Quote — cinematic dark canvas with display-mega pull quote.

Per Ferrari DESIGN.md, quotes are heroically large editorial pull quotes
in display-mega register: 80px / 500 / -1.6px tracking. Sentence case,
white on near-black. The attribution is caption-uppercase 1.1px tracked
at the bottom — Rosso Corsa to claim a single voltage of accent.
"""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, paint_chrome, add_hairline,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Quote"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="VOICE")

    # ── Hairline + Rosso Corsa ─────────────────────────────────────────────
    add_hairline(layout, 96, 380, 80, color=T.ACCENT, weight_px=2)

    # ── Pull quote — display-mega 500 -0.02em ─────────────────────────────
    add_text_placeholder(
        layout, idx=0, name="Quote", ph_type="title",
        x_px=96, y_px=420, w_px=1500, h_px=420,
        prompt_text=("“The cinematic photograph carries the depth — "
                     "the type stays editorial, never bombastic.”"),
        size_px=T.SIZE_PX["quote"],
        weight="medium",
        font=T.FONT_DISPLAY,
        color=T.INK,
        tracking_em=-0.02,
        line_height=1.1,
    )

    # ── Attribution — caption-uppercase voice, Rosso Corsa ────────────────
    add_text_placeholder(
        layout, idx=10, name="Attribution", ph_type="body",
        x_px=96, y_px=900, w_px=1728, h_px=30,
        prompt_text="FERRARI · DESIGN VOICE · 2026",
        size_px=T.SIZE_PX["quote_attr"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True, tracking_em=0.1,
    )
