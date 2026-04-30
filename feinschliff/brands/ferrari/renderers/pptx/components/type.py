"""Typography components.

These wrap `add_text` with the Feinschliff type-scale tokens so layouts don't need
to remember the sizes. Each function mirrors a named CSS class in the HTML
reference deck (.display, .huge, .slide-title, .eyebrow, .body, .rule).
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

import theme as T
from components.primitives import add_text, add_line


# ─── Rule — short filled bar used as a section marker ─────────────────────
def add_rule(
    target,
    x_px: float,
    y_px: float,
    *,
    width_px: float = 80,
    height_px: float = 4,
    color: RGBColor = T.BLACK,
):
    return add_line(target, x_px, y_px, width_px, height_px, color)


# ─── Eyebrow — mono uppercase tracked label above a title ─────────────────
def add_eyebrow(target, x_px, y_px, text, *, color=T.BLACK, w_px=1600, h_px=30):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["eyebrow"], weight="bold", font=T.FONT_DISPLAY,
        color=color, uppercase=True, tracking_em=0.1,
    )


# ─── Slide title — 37px bold ──────────────────────────────────────────────
def add_slide_title(target, x_px, y_px, text, *, color=T.BLACK, w_px=1720, h_px=80):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["slide_title"], weight="bold",
        color=color, tracking_em=-0.015, line_height=1.1,
    )


# ─── Display — 160px light (title-slide headline) ─────────────────────────
def add_display(target, x_px, y_px, text, *, color=T.BLACK, w_px=1720, h_px=320, size_px=None, align=PP_ALIGN.LEFT):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=size_px or T.SIZE_PX["display"], weight="medium",
        color=color, tracking_em=-0.035, line_height=0.95, align=align,
    )


# ─── Huge — 120px light ───────────────────────────────────────────────────
def add_huge(target, x_px, y_px, text, *, color=T.BLACK, w_px=1400, h_px=260, size_px=None):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=size_px or T.SIZE_PX["huge"], weight="medium",
        color=color, tracking_em=-0.03, line_height=1.0,
    )


# ─── Subtitle — 44px regular ──────────────────────────────────────────────
def add_subtitle(target, x_px, y_px, text, *, color=T.BLACK, w_px=1600, h_px=200):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["sub"], color=color,
        tracking_em=-0.012, line_height=1.15,
    )


# ─── Body — 26px regular, graphite by default ─────────────────────────────
def add_body(target, x_px, y_px, text, *, color=T.GRAPHITE, w_px=820, h_px=200):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["body"], color=color, line_height=1.5,
    )


# ─── Mono caption — 16px mono uppercase tracked (figure notes, tags) ──────
def add_mono_caption(target, x_px, y_px, text, *, color=T.GRAPHITE, w_px=1200, h_px=24, size_px=16):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=size_px, weight="bold", font=T.FONT_DISPLAY,
        color=color, uppercase=True, tracking_em=0.1,
    )
