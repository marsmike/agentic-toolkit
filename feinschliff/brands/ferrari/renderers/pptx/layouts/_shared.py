"""Shared helpers used by multiple layout files.

Per Ferrari DESIGN.md the system runs a single sans family at modest
weights — display 500, body 400, button 700. Caption-uppercase / nav-link
voice is the only place UPPERCASE tracked text is used. The eyebrow + title
helpers projected here apply that policy across every content layout.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rule, add_rect, add_text_placeholder,
)


def content_header(layout, *, eyebrow: str, title: str, y_rule: float = 260):
    """Top-of-slide rule + eyebrow + title stack used by content layouts.

    Ferrari typography:
      * 4px Rosso Corsa rule (the brand's accent voltage at the top of every
        editorial section) — short, 80px wide, signature 'engineered touch'.
      * Eyebrow: caption-uppercase voice — display sans, 600/700, 0.1em
        tracked, UPPERCASE, accent-colored to read against the dark canvas.
      * Title: display sans 500 (medium) with mild negative tracking
        (-0.02em). NEVER bold on display — DESIGN.md is explicit.
    """
    add_rule(layout, 96, y_rule, width_px=80, height_px=4, color=T.ACCENT)
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=96, y_px=y_rule + 40, w_px=1600, h_px=28, prompt_text=eyebrow,
        size_px=T.SIZE_PX["eyebrow"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True, tracking_em=0.1,
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=96, y_px=y_rule + 80, w_px=1728, h_px=100, prompt_text=title,
        size_px=T.SIZE_PX["slide_title"],
        weight="medium",
        font=T.FONT_DISPLAY,
        color=T.BLACK,
        tracking_em=-0.02,
        line_height=1.1,
    )


def column_placeholders(
    layout,
    *,
    idx_base: int,
    x: float,
    y: float,
    w: float,
    prompt_num: str,
    prompt_title: str,
    prompt_body: str,
    title_size: float | None = None,
):
    """3 placeholders stacked vertically: number · title · body.

    Shared by every multi-column layout (2-col, 3-col, 4-col). The number
    runs in caption-uppercase voice (Rosso Corsa); title in display 500
    -0.02em; body in regular running text.
    """
    add_text_placeholder(
        layout, idx=idx_base, name=f"Col{idx_base} Number", ph_type="body",
        x_px=x, y_px=y, w_px=w, h_px=30, prompt_text=prompt_num,
        size_px=T.SIZE_PX["col_num"],
        weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True, tracking_em=0.1,
    )
    add_text_placeholder(
        layout, idx=idx_base + 1, name=f"Col{idx_base} Title", ph_type="body",
        x_px=x, y_px=y + 44, w_px=w, h_px=160, prompt_text=prompt_title,
        size_px=title_size or T.SIZE_PX["col_title"],
        weight="medium",
        font=T.FONT_DISPLAY,
        color=T.BLACK, tracking_em=-0.02, line_height=1.15,
    )
    add_text_placeholder(
        layout, idx=idx_base + 2, name=f"Col{idx_base} Body", ph_type="body",
        x_px=x, y_px=y + 220, w_px=w, h_px=260, prompt_text=prompt_body,
        size_px=T.SIZE_PX["col_body"],
        color=T.GRAPHITE, line_height=1.5,
    )
