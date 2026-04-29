"""Shared helpers used by multiple layout files.

Kept small on purpose. If a pattern is used by 2+ layouts, it belongs here.
If it's only used by 1 layout, it should stay inline in that layout's file.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rule, add_rect, add_text_placeholder,
)


def content_header(layout, *, eyebrow: str, title: str, y_rule: float = 260):
    """Top-of-slide rule + eyebrow + title stack used by content layouts
    (KPI Grid, columns, bar chart, components)."""
    add_rule(layout, 100, y_rule, width_px=80, height_px=4)
    add_text_placeholder(
        layout, idx=10, name="Eyebrow", ph_type="body",
        x_px=100, y_px=y_rule + 40, w_px=1600, h_px=30, prompt_text=eyebrow,
        size_px=T.SIZE_PX["eyebrow"], font=T.FONT_MONO,
        color=T.BLACK, uppercase=True, tracking_em=0.12,
    )
    add_text_placeholder(
        layout, idx=0, name="Title", ph_type="title",
        x_px=100, y_px=y_rule + 80, w_px=1720, h_px=100, prompt_text=title,
        size_px=T.SIZE_PX["slide_title"], weight="bold",
        color=T.BLACK, tracking_em=-0.015, line_height=1.1,
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
        size_px=T.SIZE_PX["col_num"], font=T.FONT_MONO,
        color=T.ACCENT, uppercase=True, tracking_em=0.12,
    )
    add_text_placeholder(
        layout, idx=idx_base + 1, name=f"Col{idx_base} Title", ph_type="body",
        x_px=x, y_px=y + 44, w_px=w, h_px=160, prompt_text=prompt_title,
        size_px=title_size or T.SIZE_PX["col_title"], weight="medium",
        color=T.BLACK, tracking_em=-0.012, line_height=1.15,
    )
    add_text_placeholder(
        layout, idx=idx_base + 2, name=f"Col{idx_base} Body", ph_type="body",
        x_px=x, y_px=y + 220, w_px=w, h_px=260, prompt_text=prompt_body,
        size_px=T.SIZE_PX["col_body"],
        color=T.GRAPHITE, line_height=1.5,
    )
