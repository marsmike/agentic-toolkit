"""BMW · Title · Dark — dark navy hero band cover variant.

The dark counterpart of the white-canvas cover. Per BMW DESIGN.md the
dark navy band is the canonical hero treatment — used as one beat of the
light → dark → light page rhythm. M-stripe (4px tricolor) marks the
top edge as the section signature.

Composition:
  * surface-dark navy full-bleed
  * 4px M-stripe at top
  * UPPERCASE eyebrow lower-left
  * 64px / 700 white headline
  * Light 300 on-dark-soft sub-headline
  * White chevron CTA
"""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, paint_chrome,
    add_m_stripe, add_chevron_link,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Title · Ink"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="BMW · 2026 SHOWCASE")

    # ── 4px M-stripe at top — signature chapter marker ──────────────────
    add_m_stripe(layout, x_px=0, y_px=144, w_px=1920, h_px=4)

    # ── Eyebrow ────────────────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=120, y_px=560, w_px=1600, h_px=30,
        prompt_text="THE NEW iX3 · ELECTRIC",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.HIGHLIGHT, uppercase=True,
        tracking_em=0.115,
    )

    # ── Big headline ────────────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=120, y_px=620, w_px=1500, h_px=240,
        prompt_text="Charged for\nthe next chapter.",
        size_px=T.SIZE_PX["slide_title"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.WHITE,
        tracking_em=0,
        line_height=1.05,
    )

    # ── Sub-headline ────────────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=120, y_px=850, w_px=1100, h_px=80,
        prompt_text="A title slide on the dark hero band — the alternative beat.",
        size_px=T.SIZE_PX["lead"],
        weight="light",
        font=T.FONT_DISPLAY,
        color=T.OFF_WHITE_2,
        tracking_em=0,
        line_height=1.4,
    )

    # ── Chevron CTA ─────────────────────────────────────────────────────
    add_chevron_link(
        layout, x_px=120, y_px=940, w_px=400, h_px=30,
        text="DISCOVER", color=T.WHITE,
    )
