"""Ferrari · Title · Ink — cinematic dark cover.

Per Ferrari DESIGN.md `hero-band-cinema`: full-bleed near-black canvas
(#181818, never pure black). The photograph IS the depth treatment when
present; without a photograph, the dark canvas alone carries the cinematic
register. Headlines float at lower-left in display-mega 500 / -0.02em with
a Rosso Corsa primary CTA and an outline-on-dark secondary CTA.

This is Ferrari's canonical cover slot — the most editorial of the title
variants. `title_orange` is the livery accent variant; `title_picture` is
the photo-split variant.
"""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, paint_chrome,
    add_button, add_uppercase_link, add_hairline,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Title · Ink"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="Ferrari · 2026")

    # ── Hairline brightness-step, just above eyebrow ─────────────────────
    add_hairline(layout, 96, 540, 80, color=T.ACCENT, weight_px=2)

    # ── Eyebrow — caption-uppercase, Rosso Corsa accent ───────────────────
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=96, y_px=560, w_px=1600, h_px=28,
        prompt_text="A SHOWCASE · 2026",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True,
        tracking_em=0.1,
    )

    # ── Hero headline — slide-title 80px / 500 / -0.02em ─────────────────
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=96, y_px=620, w_px=1500, h_px=240,
        prompt_text="Ferrari\nShowcase Deck.",
        size_px=T.SIZE_PX["slide_title"],
        weight="medium",  # 500 — never bold on display
        font=T.FONT_DISPLAY,
        color=T.INK,
        tracking_em=-0.02,
        line_height=1.05,
    )

    # ── Sub-headline — display-md 26px / 500 ─────────────────────────────
    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=96, y_px=860, w_px=1100, h_px=80,
        prompt_text="A showcase of the Ferrari design system.",
        size_px=T.SIZE_PX["lead"],
        weight="medium",
        font=T.FONT_DISPLAY,
        color=T.STEEL,
        tracking_em=0,
        line_height=1.4,
    )

    # ── Rosso Corsa primary CTA — sharp 0px, UPPERCASE 700 ───────────────
    add_button(
        layout, x_px=96, y_px=950, label="Discover",
        variant="primary", w_px=200, h_px=56,
    )
