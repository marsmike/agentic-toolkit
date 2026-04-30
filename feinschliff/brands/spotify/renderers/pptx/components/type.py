"""Spotify typography components.

Wraps `add_text` with Spotify DESIGN.md type policy:

  * Bold/regular **binary** — 700 for emphasis, 400 for body. 600 used
    sparingly for feature headings only. Display reads 700 (the workhorse).
  * Sentence case (or lowercase) for hero headlines — Spotify is content-
    confident, not label-uppercase like buttons.
  * UPPERCASE label voice ONLY on buttons, chips, eyebrows, captions —
    14px / 700 / 1.4px tracking (`chip-rule.tracking-em` = 0.1).
  * Tracking 0 on display headlines — Spotify's geometric sans reads
    confident at default tracking.

Every wrapper is a thin projection of `tokens.json` policy blocks.
"""
from __future__ import annotations

from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

import theme as T
from components.primitives import add_text, add_line


_DISPLAY_TRACKING = float(T.HEADLINE_RULE.get("tracking-em", 0))
_CHIP_TRACKING    = float(T.CHIP_RULE.get("tracking-em", 0.1))


# ─── Rule — short filled bar (legacy section-marker) ──────────────────────
# Spotify section-divider primary is `add_equalizer_marker` (chrome.py);
# this `add_rule` stays for body-text underlines and inline-rule moments.
def add_rule(target, x_px, y_px, *, width_px=80, height_px=3, color=None):
    return add_line(target, x_px, y_px, width_px, height_px, color or T.ACCENT)


# ─── Eyebrow — UPPERCASE 1.4px tracked, 700 weight (label voice) ──────────
def add_eyebrow(target, x_px, y_px, text, *, color=None, w_px=1600, h_px=30):
    """Eyebrow / Small Bold per Spotify DESIGN.md: 14px / 700 / 1.4px tracking,
    UPPERCASE, display sans (NOT mono — Spotify doesn't use mono in chrome)."""
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color or T.STEEL,
        uppercase=True,
        tracking_em=_CHIP_TRACKING,
    )


# ─── Slide title — 72px bold, sentence/lowercase ──────────────────────────
def add_slide_title(target, x_px, y_px, text, *, color=None, w_px=1720, h_px=120):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["slide_title"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color or T.BLACK,
        tracking_em=_DISPLAY_TRACKING,
        line_height=1.1,
    )


# ─── Display — 160px bold, sentence/lowercase ─────────────────────────────
def add_display(target, x_px, y_px, text, *, color=None, w_px=1720, h_px=320,
                size_px=None, align=PP_ALIGN.LEFT):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=size_px or T.SIZE_PX["display"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color or T.BLACK,
        tracking_em=_DISPLAY_TRACKING,
        line_height=1.05,
        align=align,
    )


# ─── Huge — 112px bold ────────────────────────────────────────────────────
def add_huge(target, x_px, y_px, text, *, color=None, w_px=1400, h_px=260, size_px=None):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=size_px or T.SIZE_PX["huge"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color or T.BLACK,
        tracking_em=_DISPLAY_TRACKING,
        line_height=1.05,
    )


# ─── Subtitle — 32px regular (the bold/regular counterpoint) ──────────────
def add_subtitle(target, x_px, y_px, text, *, color=None, w_px=1600, h_px=200):
    """Sub-headline runs 400 regular — the binary partner to 700 display."""
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["sub"],
        weight="regular",
        font=T.FONT_DISPLAY,
        color=color or T.STEEL,
        tracking_em=0,
        line_height=1.3,
    )


# ─── Body — 20px regular, silver default ──────────────────────────────────
def add_body(target, x_px, y_px, text, *, color=None, w_px=820, h_px=200):
    """Default body — Spotify 400 regular. Never bold body — the 700/400
    contrast IS the hierarchy."""
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=T.SIZE_PX["body"],
        weight="regular",
        font=T.FONT_DISPLAY,
        color=color or T.STEEL,
        line_height=1.5,
    )


# ─── Caption — 12px UPPERCASE 1.4px tracked (figure notes, source) ────────
# Renamed semantic: "caption" not "mono". Spotify chrome doesn't use mono;
# `add_mono_caption` keeps the name for backwards compatibility.
def add_mono_caption(target, x_px, y_px, text, *, color=None, w_px=1200, h_px=24, size_px=None):
    return add_text(
        target, x_px, y_px, w_px, h_px, text,
        size_px=size_px or T.SIZE_PX["footer"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color or T.STEEL,
        uppercase=True,
        tracking_em=_CHIP_TRACKING,
    )
