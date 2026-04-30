"""Feinschliff · KPI Grid — 4 KPI cells with hairlines (HTML 07).

All four fields per KPI (value, unit, key, delta) are editable placeholders.
Value is right-aligned big text (Noto Sans Light); unit is small graphite
sitting flush against it. Together they share a baseline via bottom-anchoring.
"""
from __future__ import annotations

import theme as T
from components import (
    add_line, add_rect, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header

NAME = "Feinschliff · KPI Grid"

SAMPLES = [
    ("62",  "k",    "Employees",           "+3% YoY"),
    ("14",  " bn",  "Revenue · EUR",       "+5.1% YoY"),
    ("40",  "",     "Factories worldwide", "8 regions"),
    ("100", "%",    "Green electricity",   "since 2020"),
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])
    paint_chrome(layout, variant="light", pgmeta="Company · 2025")

    content_header(layout, eyebrow="Figures at a glance", title="Feinschliff in numbers.")

    # 1720 / 4 = 430 per KPI
    kpi_w = 430
    x0, y0, kpi_h = 100, 540, 260

    # Value fills most of its half, right-aligned; unit starts flush after.
    value_w = 190
    unit_w = (kpi_w - 80) - value_w  # 160

    # Left hairline
    add_rect(layout, x0, y0, 1, kpi_h, fill=T.FOG)

    for i, (value, unit, key, delta) in enumerate(SAMPLES):
        x = x0 + i * kpi_w
        add_line(layout, x, y0, kpi_w, 1, T.FOG)
        add_line(layout, x, y0 + kpi_h - 1, kpi_w, 1, T.FOG)
        add_rect(layout, x + kpi_w, y0, 1, kpi_h, fill=T.FOG)

        idx_base = 20 + i * 2
        add_text_placeholder(
            layout, idx=idx_base, name=f"KPI {i+1} Key", ph_type="body",
            x_px=x + 40, y_px=y0 + 190, w_px=kpi_w - 80, h_px=30, prompt_text=key,
            size_px=T.SIZE_PX["kpi_key"], font=T.FONT_MONO,
            color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
        )
        add_text_placeholder(
            layout, idx=idx_base + 1, name=f"KPI {i+1} Delta", ph_type="body",
            x_px=x + 40, y_px=y0 + 220, w_px=kpi_w - 80, h_px=26, prompt_text=delta,
            size_px=T.SIZE_PX["kpi_delta"], font=T.FONT_MONO,
            color=T.ACCENT_HOVER,
        )

        # Value + unit as two placeholders, bottom-anchored so baselines align.
        add_text_placeholder(
            layout, idx=30 + i * 2, name=f"KPI {i+1} Value", ph_type="body",
            x_px=x + 40, y_px=y0 + 36, w_px=value_w, h_px=140, prompt_text=value,
            size_px=T.SIZE_PX["kpi_value"], weight="light", font=T.FONT_DISPLAY,
            color=T.BLACK, tracking_em=-0.03, align="r", anchor="b",
        )
        add_text_placeholder(
            layout, idx=31 + i * 2, name=f"KPI {i+1} Unit", ph_type="body",
            x_px=x + 40 + value_w, y_px=y0 + 36, w_px=unit_w, h_px=140,
            prompt_text=unit, size_px=T.SIZE_PX["kpi_unit"], font=T.FONT_DISPLAY,
            color=T.GRAPHITE, align="l", anchor="b",
        )
