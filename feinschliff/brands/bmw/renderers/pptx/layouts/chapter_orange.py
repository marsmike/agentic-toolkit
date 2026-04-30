"""BMW · Chapter · Light — chapter divider on white canvas with M-stripe.

Per BMW DESIGN.md the M-stripe (4px tricolor) is the canonical chapter
divider — appears between major editorial bands. Layout pattern:

  * White canvas, page rhythm light → dark → light (this is one of the
    light beats).
  * Big chapter numeral 240px / 700 — the iconic BMW spec-cell-style number.
  * UPPERCASE label-uppercase eyebrow above (1.5px tracked).
  * Chapter title 64px / 700 below the M-stripe.
  * 4px M-stripe runs full-width between the eyebrow and the title.
"""
from __future__ import annotations

import theme as T
from components import (
    add_text, add_text_placeholder,
    add_m_stripe,
    paint_chrome, set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Chapter · Accent"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["paper"])  # white canvas
    paint_chrome(layout, variant="light", pgmeta="CHAPTER 01")

    # ── Big chapter numeral — soft-grey, very large, sits behind ──────────
    # Right-aligned at the upper-right, near-watermark presence.
    add_text(
        layout, 1100, 240, 720, 280, "01",
        size_px=240,
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.PAPER_4,    # surface-strong — barely-there grey
        tracking_em=0,
        line_height=1.0,
    )

    # ── Eyebrow ───────────────────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=120, y_px=440, w_px=1600, h_px=28,
        prompt_text="CHAPTER 01 · MODELS",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.SILVER, uppercase=True,
        tracking_em=0.115,
    )

    # ── M-stripe divider ──────────────────────────────────────────────────
    add_m_stripe(layout, x_px=120, y_px=494, w_px=560, h_px=4)

    # ── Chapter title ─────────────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=120, y_px=540, w_px=1300, h_px=240,
        prompt_text="Models &\nNext Generation.",
        size_px=T.SIZE_PX["slide_title"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.INK,
        tracking_em=0,
        line_height=1.05,
    )

    # ── Subtitle — Light 300 ──────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=120, y_px=820, w_px=1100, h_px=80,
        prompt_text="The full lineup at a glance — combustion, plug-in hybrid, electric.",
        size_px=T.SIZE_PX["lead"],
        weight="light",
        font=T.FONT_DISPLAY,
        color=T.STEEL,
        tracking_em=0,
        line_height=1.4,
    )
