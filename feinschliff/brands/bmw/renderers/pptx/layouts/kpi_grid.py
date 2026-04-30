"""BMW · KPI Grid — spec-cell pattern (4-up).

Per BMW DESIGN.md `spec-cell` recipe: large value on top in display weight
700 (NOT light — the BMW signature is 700/300 contrast), UPPERCASE
label-uppercase below in 1.5px tracked. Hairline dividers between cells
(1px `colors.hairline` #E6E6E6). NO drop shadows — depth comes from
hairlines + color-block contrast.

slides.py supplies 2 fields per KPI (`_2N`=key, `_2N+1`=delta). Value
and unit fall back to layout defaults from SAMPLES.
"""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, paint_chrome, add_hairline,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header

NAME = "Feinschliff · KPI Grid"

# 4 KPIs — value, unit, key, delta. Key + delta come from slides.py at runtime;
# value + unit use these defaults.
SAMPLES = [
    ("462",  " kW",  "Peak output",       "+19% YoY"),
    ("3.0",  " s",   "0–100 km/h",        "Best in class"),
    ("750",  " km",  "WLTP range",        "8 regions"),
    ("100",  "%",    "Green electricity", "since 2020"),
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["paper"])
    paint_chrome(layout, variant="light", pgmeta="SPECIFICATIONS · 2026")

    content_header(layout, eyebrow="At a glance", title="Performance figures.")

    # 4-up grid, full content width 1680px
    kpi_w = 1680 // 4   # 420
    x0, y0, kpi_h = 120, 540, 320

    # Top + bottom hairlines bracket the row.
    add_hairline(layout, x0, y0,         1680, color=T.FOG)
    add_hairline(layout, x0, y0 + kpi_h, 1680, color=T.FOG)

    # Value placeholder is wide; unit sits flush after — bottom-anchored so
    # baselines align (value 88px, unit 28px both anchor "b").
    value_w = 220
    unit_w = (kpi_w - 64) - value_w

    for i, (value, unit, key, delta) in enumerate(SAMPLES):
        x = x0 + i * kpi_w

        # Inner vertical hairline (between cells, not at outer edges)
        if i > 0:
            from components import add_rect
            add_rect(layout, x, y0 + 32, 1, kpi_h - 64, fill=T.FOG)

        # ── Value (700 bold, baseline-aligned bottom) ─────────────────────
        add_text_placeholder(
            layout, idx=30 + i * 2, name=f"KPI {i+1} Value", ph_type="body",
            x_px=x + 32, y_px=y0 + 60, w_px=value_w, h_px=140,
            prompt_text=value,
            size_px=T.SIZE_PX["kpi_value"],
            weight="bold",
            font=T.FONT_DISPLAY,
            color=T.INK,
            tracking_em=0,
            line_height=1.0,
            align="l", anchor="b",
        )
        # ── Unit (700, smaller, baseline aligned with value) ──────────────
        add_text_placeholder(
            layout, idx=31 + i * 2, name=f"KPI {i+1} Unit", ph_type="body",
            x_px=x + 32 + value_w, y_px=y0 + 60, w_px=unit_w, h_px=140,
            prompt_text=unit,
            size_px=T.SIZE_PX["kpi_unit"],
            weight="bold",
            font=T.FONT_DISPLAY,
            color=T.STEEL,
            tracking_em=0,
            align="l", anchor="b",
        )
        # ── Key (label-uppercase 1.5px tracked) ───────────────────────────
        add_text_placeholder(
            layout, idx=20 + i * 2, name=f"KPI {i+1} Key", ph_type="body",
            x_px=x + 32, y_px=y0 + 220, w_px=kpi_w - 64, h_px=28,
            prompt_text=key,
            size_px=T.SIZE_PX["kpi_key"],
            weight="bold",
            font=T.FONT_DISPLAY,
            color=T.INK, uppercase=True,
            tracking_em=0.115,
        )
        # ── Delta (small, BMW Blue, semantic positive/neutral) ────────────
        add_text_placeholder(
            layout, idx=21 + i * 2, name=f"KPI {i+1} Delta", ph_type="body",
            x_px=x + 32, y_px=y0 + 260, w_px=kpi_w - 64, h_px=24,
            prompt_text=delta,
            size_px=T.SIZE_PX["kpi_delta"],
            weight="light",
            font=T.FONT_DISPLAY,
            color=T.ACCENT,
        )
