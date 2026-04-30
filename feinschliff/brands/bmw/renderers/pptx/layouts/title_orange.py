"""BMW · Title · Light — primary cover slide.

Per BMW DESIGN.md, BMW Blue is the action color — NOT a hero fill. The
canonical cover slot is therefore a **light canvas with hairline-marked
headline**. BMW Blue appears as the chevron-link CTA, not as background.

Composition:
  * White canvas, big asymmetric whitespace
  * UPPERCASE eyebrow (1.5px tracked)
  * 64px / 700 / tracking 0 headline lower-left
  * Light 300 sub-headline
  * BMW Blue "DISCOVER ›" chevron link
  * Hairline rule above eyebrow as the "engineered" touchpoint
"""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_text_placeholder, paint_chrome,
    add_chevron_link, add_hairline,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Title · Accent"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["paper"])  # white canvas
    paint_chrome(layout, variant="light", pgmeta="BMW · 2026 SHOWCASE")

    # ── Hairline above the eyebrow (engineered detail) ────────────────────
    add_hairline(layout, 120, 540, 80, color=T.INK, weight_px=2)

    # ── Eyebrow — UPPERCASE 1.5px tracked, BMW Blue ──────────────────────
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=120, y_px=560, w_px=1600, h_px=30,
        prompt_text="THE NEXT GENERATION · 2026",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True,
        tracking_em=0.115,
    )

    # ── Big headline — 64pt / 700 / tracking 0 ──────────────────────────
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=120, y_px=620, w_px=1500, h_px=240,
        prompt_text="Sheer Driving\nPleasure.",
        size_px=T.SIZE_PX["slide_title"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.INK,
        tracking_em=0,
        line_height=1.05,
    )

    # ── Sub-headline — Light 300 ──────────────────────────────────────────
    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=120, y_px=850, w_px=1100, h_px=80,
        prompt_text="A showcase of the BMW corporate design system.",
        size_px=T.SIZE_PX["lead"],
        weight="light",
        font=T.FONT_DISPLAY,
        color=T.STEEL,
        tracking_em=0,
        line_height=1.4,
    )

    # ── BMW Blue chevron CTA — the action color in its proper role ─────────
    add_chevron_link(
        layout, x_px=120, y_px=940, w_px=400, h_px=30,
        text="DISCOVER", color=T.ACCENT,
    )
