"""Ferrari · Chapter · Accent — chapter divider with full Rosso Corsa livery band.

Per Ferrari DESIGN.md `livery-band` component, the Rosso Corsa accent band
is the brand's chapter divider. Replaces BMW's M-stripe role and Spotify's
equalizer-marker role.

Composition:
  * Cinematic dark canvas (#181818)
  * Big chapter numeral right, brightness-step on canvas (barely-there)
  * Eyebrow — caption-uppercase voice
  * Livery band — 4px Rosso Corsa rule between eyebrow and title
  * Chapter title — display 500 -0.02em
  * Sub-headline — display-md 500
"""
from __future__ import annotations

import theme as T
from components import (
    add_text, add_text_placeholder,
    add_livery_band,
    paint_chrome, set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Chapter · Accent"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="CHAPTER 01")

    # ── Big chapter numeral — barely-there brightness-step on canvas ─────
    add_text(
        layout, 1100, 240, 720, 280, "01",
        size_px=240,
        weight="medium",
        font=T.FONT_DISPLAY,
        color=T.PAPER_4,    # surface-strong (#2A2A2A) — barely-there
        tracking_em=-0.02,
        line_height=1.0,
    )

    # ── Eyebrow ──────────────────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=96, y_px=440, w_px=1600, h_px=28,
        prompt_text="CHAPTER 01 · MODELS",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.STEEL, uppercase=True,
        tracking_em=0.1,
    )

    # ── Livery band — 4px Rosso Corsa rule ───────────────────────────────
    add_livery_band(layout, x_px=96, y_px=494, w_px=560, h_px=4)

    # ── Chapter title — display 500 -0.02em ──────────────────────────────
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=96, y_px=540, w_px=1300, h_px=240,
        prompt_text="Models &\nNew Releases.",
        size_px=T.SIZE_PX["slide_title"],
        weight="medium",
        font=T.FONT_DISPLAY,
        color=T.INK,
        tracking_em=-0.02,
        line_height=1.05,
    )

    # ── Subtitle — display-md 500 ────────────────────────────────────────
    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=96, y_px=820, w_px=1100, h_px=80,
        prompt_text="The full lineup at a glance — V8, V12, hybrid, GT.",
        size_px=T.SIZE_PX["lead"],
        weight="medium",
        font=T.FONT_DISPLAY,
        color=T.STEEL,
        tracking_em=0,
        line_height=1.4,
    )
