"""BMW · Cover — HairlineHeader pattern.

Per BMW DESIGN.md `cover_pattern: hairline_header_with_dark_band`:

  * Top 58% of slide: light canvas, holds eyebrow + chrome.
  * Bottom 42%: surface-dark navy band — model name in 64px / 700 left,
    Light 300 sub-headline + LEARN MORE › chevron CTA below.
  * 4px M-stripe sits on the boundary between light and dark bands —
    tricolor (m-blue-light → m-blue-dark → m-red).
  * No image required; dropping a 21:9 photo into the dark band is the
    optional editorial flourish.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_text_placeholder,
    add_m_stripe, add_chevron_link, add_hairline,
    paint_chrome, set_layout_background, set_layout_name,
)
from components.media import add_image_placeholder

NAME = "Feinschliff · Full-bleed Cover"

_HERO_BAND_PCT = float(T.COVER.get("hero-band-height-pct", 0.42))
_HERO_BAND_Y   = int(1080 * (1 - _HERO_BAND_PCT))   # ~626


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["paper"])  # white canvas

    # ── Light canvas band (top ~58%) ───────────────────────────────────────
    # Optional editorial photo plate — surface-card grey, holds an image.
    add_image_placeholder(
        layout, 120, 200, 1680, _HERO_BAND_Y - 240, label="Model render · 16:10",
    )

    # ── Dark navy hero band (bottom ~42%) ──────────────────────────────────
    add_rect(layout, 0, _HERO_BAND_Y, 1920, 1080 - _HERO_BAND_Y, fill=T.SURFACE_DARK)

    # ── 4px M-stripe sits exactly on the light/dark boundary ───────────────
    add_m_stripe(layout, x_px=0, y_px=_HERO_BAND_Y - 4, w_px=1920, h_px=4)

    # ── Chrome — light variant on the upper canvas ─────────────────────────
    paint_chrome(layout, variant="light", pgmeta="BMW · 2026 SHOWCASE")

    # ── Eyebrow above the dark band, on light canvas ───────────────────────
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=120, y_px=_HERO_BAND_Y - 64, w_px=1200, h_px=28,
        prompt_text="THE NEW iX3 · ELECTRIC",
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.SILVER, uppercase=True,
        tracking_em=0.115,
    )

    # ── Hero headline on dark band — 64px / 700 / tracking 0 ──────────────
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=120, y_px=_HERO_BAND_Y + 80,
        w_px=1100, h_px=200,
        prompt_text="Sheer Driving\nPleasure.",
        size_px=T.SIZE_PX["slide_title"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=T.WHITE,
        tracking_em=0,
        line_height=1.05,
    )

    # ── Sub-headline — Light 300 ───────────────────────────────────────────
    add_text_placeholder(
        layout, idx=11, name="Subtitle", ph_type="body",
        x_px=120, y_px=_HERO_BAND_Y + 290,
        w_px=900, h_px=80,
        prompt_text="Engineered in Munich. Charged for the next chapter.",
        size_px=T.SIZE_PX["lead"],
        weight="light",
        font=T.FONT_DISPLAY,
        color=T.OFF_WHITE_2,
        tracking_em=0,
        line_height=1.4,
    )

    # ── LEARN MORE › chevron link, lower-right of dark band ────────────────
    add_chevron_link(
        layout, x_px=120, y_px=_HERO_BAND_Y + 380, w_px=400, h_px=30,
        text="DISCOVER", color=T.WHITE,
    )
