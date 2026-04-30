"""Data visualisation components — KPI cell + bar-chart row."""
from __future__ import annotations

from pptx.enum.text import PP_ALIGN

import theme as T
from geometry import px, pt_from_px
from components.primitives import add_rect, add_line, add_text


def add_kpi(
    target,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    *,
    value: str,
    unit: str | None = None,
    key: str,
    delta: str | None = None,
    color_value=T.BLACK,
    color_key=T.GRAPHITE,
    color_delta=T.ACCENT_HOVER,
    hairline_color=T.FOG,
):
    """KPI cell — stacked value/unit + key + delta, top & bottom hairlines.

    Coordinates match the HTML .kpi .v / .k / .delta spec exactly:
      - v   : 120px Light, letter-spacing -0.03em, line-height 0.95
      - unit: 40px, graphite, margin-left 8px
      - k   : 16px mono uppercase, tracking 0.1em
      - delta: 18px mono, orange-hover
    """
    add_line(target, x_px, y_px, w_px, 1, hairline_color)
    add_line(target, x_px, y_px + h_px - 1, w_px, 1, hairline_color)

    vbox = add_text(
        target, x_px + 40, y_px + 36, w_px - 80, 140, value,
        size_px=T.SIZE_PX["kpi_value"], weight="medium",
        color=color_value, tracking_em=-0.03, line_height=0.95,
    )
    if unit:
        p = vbox.text_frame.paragraphs[0]
        run = p.add_run()
        run.text = unit
        run.font.name = T.FONT_DISPLAY
        run.font.size = pt_from_px(T.SIZE_PX["kpi_unit"])
        run.font.color.rgb = color_key

    add_text(
        target, x_px + 40, y_px + 190, w_px - 80, 30, key,
        size_px=T.SIZE_PX["kpi_key"], weight="bold", font=T.FONT_DISPLAY,
        color=color_key, uppercase=True, tracking_em=0.1,
    )
    if delta:
        add_text(
            target, x_px + 40, y_px + 220, w_px - 80, 26, delta,
            size_px=T.SIZE_PX["kpi_delta"], weight="bold", font=T.FONT_DISPLAY,
            color=color_delta,
        )


def add_bar_row(
    target,
    y_px: float,
    *,
    label: str,
    value_pct: float,
    x_px: float = 100,
    width_px: float = 1720,
    accent: bool = False,
    label_w: float = 240,
    num_w: float = 120,
    track_color=T.FOG,
    fill_color=T.BLACK,
    accent_color=T.ACCENT,
    label_color=T.BLACK,
    num_color=T.BLACK,
):
    """Horizontal bar-chart row: label · track · num."""
    track_x = x_px + label_w + 24
    num_x = x_px + width_px - num_w
    track_w = num_x - track_x - 24

    add_text(
        target, x_px, y_px, label_w, 40, label,
        size_px=T.SIZE_PX["bar_label"], weight="medium", color=label_color,
    )
    add_rect(target, track_x, y_px + 8, track_w, 32, fill=track_color)
    fill_w = int(round(track_w * (value_pct / 100.0)))
    add_rect(
        target, track_x, y_px + 8, fill_w, 32,
        fill=(accent_color if accent else fill_color),
    )
    add_text(
        target, num_x, y_px + 6, num_w, 32, f"{value_pct:g}%",
        size_px=T.SIZE_PX["bar_num"], weight="bold", font=T.FONT_DISPLAY,
        color=num_color, align=PP_ALIGN.RIGHT,
    )
