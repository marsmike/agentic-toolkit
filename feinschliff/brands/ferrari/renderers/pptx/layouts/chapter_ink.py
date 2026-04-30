"""Ferrari · Chapter · Ink + Picture — cinematic dark chapter opener with right-half image.

Mirror of chapter_orange but with a 50/50 cinematic photo split: left half
carries the chapter title in display 500 -0.02em on near-black canvas;
right half is a full-bleed photographic plate (per DESIGN.md `hero-band-cinema`
+ `feature-card-photo`). Hairline brightness-step + Rosso Corsa eyebrow
carry the editorial register.
"""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, add_image_placeholder,
    add_hairline,
    paint_chrome, set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Chapter · Ink + Picture"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])

    # Right-half cinematic photo plate — full-bleed, no shadow.
    add_image_placeholder(
        layout, 960, 0, 960, 1080, label="Editorial image · 21:9", dark=True,
    )

    paint_chrome(layout, variant="dark", pgmeta="CHAPTER 02")

    # ── Hairline + Rosso Corsa eyebrow ───────────────────────────────────
    add_hairline(layout, 96, 436, 80, color=T.ACCENT, weight_px=2)
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=96, y_px=456, w_px=820, h_px=28,
        prompt_text="CHAPTER 02 · DESIGN",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True, tracking_em=0.1,
    )

    # ── Chapter title — slide-title 80 / 500 / -0.02em ───────────────────
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=96, y_px=520, w_px=820, h_px=360,
        prompt_text="Colour\n& Type.",
        size_px=T.SIZE_PX["slide_title"],
        weight="medium",
        font=T.FONT_DISPLAY,
        color=T.INK,
        tracking_em=-0.02,
        line_height=1.05,
    )
