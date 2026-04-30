"""Shared helpers used by multiple layout files.

Kept small on purpose. If a pattern is used by 2+ layouts, it belongs here.
If it's only used by 1 layout, it should stay inline in that layout's file.
"""
from __future__ import annotations

import theme as T
from components import (
    add_section_marker, add_text_placeholder,
)


def content_header(layout, *, eyebrow: str, title: str, y_rule: float = 260):
    """Top-of-slide yellow ▌ section-marker + eyebrow + title stack.

    The yellow ▌ (8px wide × headline height) replaces BMW's M-stripe role
    and Spotify's equalizer-marker role on standard content layouts. Sits
    flush to the eyebrow + title stack so the headline reads as a "trading-
    pane active row" — Binance's product-DNA chrome.
    """
    # Marker spans both the eyebrow row and the title — total stack height
    # is approximately eyebrow(30) + gap(20) + title(80*1.1) ≈ 138px.
    marker_h = 138
    add_section_marker(layout, x_px=100, y_px=y_rule, h_px=marker_h)

    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=132, y_px=y_rule, w_px=1600, h_px=30, prompt_text=eyebrow,
        size_px=T.SIZE_PX["eyebrow"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.ACCENT, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=132, y_px=y_rule + 50, w_px=1720, h_px=100, prompt_text=title,
        size_px=T.SIZE_PX["slide_title"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.GRAPHITE, tracking_em=-0.015, line_height=1.1,
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

    Shared by every multi-column layout (2-col, 3-col, 4-col).
    """
    add_text_placeholder(
        layout, idx=idx_base, name=f"Col{idx_base} Number", ph_type="body",
        x_px=x, y_px=y, w_px=w, h_px=30, prompt_text=prompt_num,
        size_px=T.SIZE_PX["col_num"],
        weight="semibold", font=T.FONT_MONO,
        color=T.ACCENT, uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )
    add_text_placeholder(
        layout, idx=idx_base + 1, name=f"Col{idx_base} Title", ph_type="body",
        x_px=x, y_px=y + 44, w_px=w, h_px=160, prompt_text=prompt_title,
        size_px=title_size or T.SIZE_PX["col_title"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.GRAPHITE, tracking_em=-0.012, line_height=1.15,
    )
    add_text_placeholder(
        layout, idx=idx_base + 2, name=f"Col{idx_base} Body", ph_type="body",
        x_px=x, y_px=y + 220, w_px=w, h_px=260, prompt_text=prompt_body,
        size_px=T.SIZE_PX["col_body"],
        weight="regular", font=T.FONT_DISPLAY,
        color=T.OFF_WHITE, line_height=1.5,
    )
