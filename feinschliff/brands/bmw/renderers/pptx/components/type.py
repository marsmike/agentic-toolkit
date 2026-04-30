"""BMW typography components.

Wraps `add_text` with BMW DESIGN.md type policy:

  * Display headlines run BMW Type Next Latin **700 (bold)** with **tracking 0**.
    No negative letter-spacing — Apple-style tightening reads off-brand here.
  * Body runs **300 Light** (`weight="light"`) — the editorial signature is the
    700 / 300 contrast. Weight 500 is intentionally absent.
  * Eyebrows + captions run **UPPERCASE 700 with 1.5px tracking** — display
    sans, never mono. "LEARN MORE"-style label-uppercase voice.

Every wrapper here is a thin projection of `tokens.json` policy blocks
(HEADLINE_RULE, CHIP_RULE) so values stay in one place.
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

import theme as T
from components.primitives import add_text, add_line


_DISPLAY_TRACKING = float(T.HEADLINE_RULE.get("tracking-em", 0))
_CHIP_TRACKING    = float(T.CHIP_RULE.get("tracking-em", 0.115))


# ─── Rule — short filled bar, used as section marker ──────────────────────
def add_rule(target, x_px, y_px, *, width_px=80, height_px=4, color=T.INK):
    return add_line(target, x_px, y_px, width_px, height_px, color)


# ─── Eyebrow — display sans UPPERCASE 1.5px tracked, 700 weight ───────────
def add_eyebrow(target, x_px, y_px, text, *, color=T.SILVER, w_px=1600, h_px=30):
    """label-uppercase per BMW DESIGN.md: 16px / 700 / 1.5px tracking,
    UPPERCASE, display sans (NOT mono)."""
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color, uppercase=True,
        tracking_em=_CHIP_TRACKING,
    )


# ─── Slide title — 64px bold ──────────────────────────────────────────────
def add_slide_title(target, x_px, y_px, text, *, color=T.INK, w_px=1720, h_px=120):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["slide_title"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color,
        tracking_em=_DISPLAY_TRACKING,
        line_height=1.05,
    )


# ─── Display — 160px bold (title-slide hero headline) ─────────────────────
def add_display(target, x_px, y_px, text, *, color=T.INK, w_px=1720, h_px=320,
                size_px=None, align=PP_ALIGN.LEFT):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=size_px or T.SIZE_PX["display"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color,
        tracking_em=_DISPLAY_TRACKING,
        line_height=1.05,
        align=align,
    )


# ─── Huge — 128px bold (chapter numerals, big editorial moments) ──────────
def add_huge(target, x_px, y_px, text, *, color=T.INK, w_px=1400, h_px=260, size_px=None):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=size_px or T.SIZE_PX["huge"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color,
        tracking_em=_DISPLAY_TRACKING,
        line_height=1.0,
    )


# ─── Subtitle — 32px Light 300 (sub-headline / lead paragraph) ────────────
def add_subtitle(target, x_px, y_px, text, *, color=T.STEEL, w_px=1600, h_px=200):
    """Sub-headline runs Light 300 — the BMW editorial signature against
    700 display."""
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["sub"],
        weight="light",
        font=T.FONT_DISPLAY,
        color=color,
        tracking_em=0,
        line_height=1.15,
    )


# ─── Body — 20px Light 300 ────────────────────────────────────────────────
def add_body(target, x_px, y_px, text, *, color=T.STEEL, w_px=820, h_px=200):
    """Default body — Light 300. Don't bold — the 700/300 contrast is the
    BMW editorial signature."""
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["body"],
        weight="light",
        font=T.FONT_DISPLAY,
        color=color, line_height=1.55,
    )


# ─── Mono caption — 14px display-sans UPPERCASE tracked (figure notes) ────
# Renamed semantic: "caption" not "mono". BMW DESIGN.md doesn't use mono in
# chrome — captions are caption-style display sans.
def add_mono_caption(target, x_px, y_px, text, *, color=T.SILVER, w_px=1200, h_px=24, size_px=None):
    """Caption / figure note — UPPERCASE 700 1.5px tracked display sans.
    Name kept as `add_mono_caption` for backwards compatibility with shared
    layouts; actual font is FONT_DISPLAY."""
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=size_px or T.SIZE_PX["footer"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color, uppercase=True,
        tracking_em=_CHIP_TRACKING,
    )
