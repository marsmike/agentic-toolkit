"""Ferrari · End — cinematic dark closing slide with centered "Grazie."

Mirrors the cover (`title_ink`) — full-bleed near-black canvas, centered
display-mega 500 -0.02em headline, single Rosso Corsa CTA centered below.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_text_placeholder, paint_chrome,
    add_button,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · End"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="END")

    # ── Centered Rosso Corsa rule — DESIGN.md livery-band signature ──────
    add_rect(layout, 900, 380, 120, 4, fill=T.ACCENT)

    # ── Hero "Grazie." — display-mega 500 -0.02em ─────────────────────────
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=96, y_px=420, w_px=1728, h_px=240,
        prompt_text="Grazie.",
        size_px=200,
        weight="medium",
        font=T.FONT_DISPLAY,
        color=T.INK,
        tracking_em=-0.02,
        line_height=1.0,
        align="c",
    )

    # ── Caption — caption-uppercase voice, Rosso Corsa ───────────────────
    add_text_placeholder(
        layout, idx=10, name="Caption", ph_type="body",
        x_px=96, y_px=700, w_px=1728, h_px=40,
        prompt_text="FERRARI · 2026 SHOWCASE",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True, tracking_em=0.1,
        align="c",
    )

    # ── Centered Rosso Corsa CTA ──────────────────────────────────────────
    add_button(
        layout, x_px=860, y_px=780, label="Discover",
        variant="primary", w_px=200, h_px=56,
    )
