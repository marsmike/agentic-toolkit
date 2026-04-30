"""Spotify · Title — primary cover slide.

Per Spotify DESIGN.md, Spotify Green is functional-only — never decorative,
never on a hero background. The canonical cover is **near-black canvas
with album-art shelf and a green pill CTA** at lower-left.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rounded_rect, add_text_placeholder, paint_chrome,
    add_button,
    set_layout_background, set_layout_name,
)


NAME = "Feinschliff · Title · Accent"

_TILE_RADIUS = T.RADIUS.get("card", 8)


def _shelf(layout, *, x_px, y_px, w_px, h_px, rows=2, cols=5, gap=14):
    """Album-art shelf — rows x cols rounded tiles on `paper` / `paper-2`
    with elevated shadow. Each tile is decorative; replace with image fills
    in actual usage."""
    tile_w = (w_px - gap * (cols - 1)) / cols
    tile_h = (h_px - gap * (rows - 1)) / rows
    for r in range(rows):
        for c in range(cols):
            tx = x_px + c * (tile_w + gap)
            ty = y_px + r * (tile_h + gap)
            fill = T.PAPER_2 if (r + c) % 2 == 0 else T.PAPER
            add_rounded_rect(
                layout, tx, ty, tile_w, tile_h,
                radius_px=_TILE_RADIUS,
                fill=fill,
                shadow="elevated",
            )


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="SPOTIFY · 2026")

    # Album-art shelf
    _shelf(layout, x_px=120, y_px=160, w_px=1680, h_px=400, rows=2, cols=5)

    # Eyebrow
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=120, y_px=620, w_px=1600, h_px=28,
        prompt_text="NEW · 2026",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True, tracking_em=0.1,
    )

    # Hero headline — sentence-case 700 white
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=120, y_px=680, w_px=1500, h_px=240,
        prompt_text="Sound is\neverything.",
        size_px=T.SIZE_PX["slide_title"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.BLACK,
        tracking_em=0, line_height=1.05,
    )

    # Sub-headline
    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=120, y_px=920, w_px=1100, h_px=60,
        prompt_text="Open the app to listen, or scroll for the showcase.",
        size_px=T.SIZE_PX["lead"],
        weight="regular", font=T.FONT_DISPLAY,
        color=T.STEEL,
        tracking_em=0, line_height=1.4,
    )

    # Green pill PLAY CTA
    add_button(layout, x_px=120, y_px=975, label="Play",
               variant="primary", w_px=160, h_px=48)
