"""Ferrari · KPI Grid — spec-cell + race-position pattern (4-up).

Per Ferrari DESIGN.md the canonical numbers display is the `spec-cell`:

  * `number-display` — 80px / 700 / -1.6px tracking. WHITE on dark canvas.
  * caption-uppercase label below — 11px / 600 / 1.1px tracked UPPERCASE.

The fourth cell uses the `race-position-cell` variant — same number geometry
but rendered in Rosso Corsa, the brand's racing-identity highlight. This
keeps the brand voltage scarce (one cell out of four) while making the KPI
grid recognisably Ferrari rather than generic editorial.

Hairline brightness-step dividers between cells (1px #303030 — same hex
as canvas-elevated; reads as a tone-step). NO drop shadows — depth comes
from hairlines + brightness-step ONLY (DESIGN.md elevation table).

slides.py supplies 2 fields per KPI (`_2N`=key, `_2N+1`=delta). Value and
unit fall back to layout defaults from SAMPLES.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_text_placeholder, paint_chrome, add_hairline,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header

NAME = "Feinschliff · KPI Grid"

SAMPLES = [
    ("296",  " km/h",  "Top speed",         "458 Italia"),
    ("2.9",  " s",     "0–100 km/h",        "Best in class"),
    ("670",  " hp",    "V8 peak output",    "+9% YoY"),
    ("1",    "st",     "Constructors '23",  "F1 ANNIVERSARY"),  # race-position cell
]
RACE_POSITION_INDEX = 3


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="SPECIFICATIONS · 2026")

    content_header(layout, eyebrow="At a glance", title="Performance figures.")

    # 4-up grid, full content width 1728px (96 + 1728 + 96 = 1920)
    kpi_w = 1728 // 4   # 432
    x0, y0, kpi_h = 96, 540, 320

    # Top + bottom hairlines bracket the row.
    add_hairline(layout, x0, y0,         1728, color=T.FOG)
    add_hairline(layout, x0, y0 + kpi_h, 1728, color=T.FOG)

    # Value placeholder is wide; unit sits flush after — bottom-anchored so
    # baselines align (value 120px, unit 32px both anchor "b").
    value_w = 280
    unit_w = (kpi_w - 64) - value_w

    for i, (value, unit, key, delta) in enumerate(SAMPLES):
        x = x0 + i * kpi_w
        is_race = i == RACE_POSITION_INDEX
        value_color = T.ACCENT if is_race else T.INK
        delta_color = T.ACCENT if is_race else T.STEEL

        # Inner vertical hairline (between cells, not at outer edges)
        if i > 0:
            add_rect(layout, x, y0 + 32, 1, kpi_h - 64, fill=T.FOG)

        # ── Value (700 bold, baseline-aligned bottom) ─────────────────────
        add_text_placeholder(
            layout, idx=30 + i * 2, name=f"KPI {i+1} Value", ph_type="body",
            x_px=x + 24, y_px=y0 + 50, w_px=value_w, h_px=160,
            prompt_text=value,
            size_px=T.SIZE_PX["kpi_value"],
            weight="bold",
            font=T.FONT_DISPLAY,
            color=value_color,
            tracking_em=-0.02,
            line_height=1.0,
            align="l", anchor="b",
        )
        # ── Unit (700 small, baseline aligned with value) ─────────────────
        add_text_placeholder(
            layout, idx=31 + i * 2, name=f"KPI {i+1} Unit", ph_type="body",
            x_px=x + 24 + value_w, y_px=y0 + 50, w_px=unit_w, h_px=160,
            prompt_text=unit,
            size_px=T.SIZE_PX["kpi_unit"],
            weight="bold",
            font=T.FONT_DISPLAY,
            color=value_color if is_race else T.STEEL,
            tracking_em=0,
            align="l", anchor="b",
        )
        # ── Key (caption-uppercase voice) ─────────────────────────────────
        add_text_placeholder(
            layout, idx=20 + i * 2, name=f"KPI {i+1} Key", ph_type="body",
            x_px=x + 24, y_px=y0 + 230, w_px=kpi_w - 48, h_px=28,
            prompt_text=key,
            size_px=T.SIZE_PX["kpi_key"],
            weight="bold",
            font=T.FONT_DISPLAY,
            color=T.INK, uppercase=True,
            tracking_em=0.1,
        )
        # ── Delta (small, regular, accent on race-position cell) ──────────
        add_text_placeholder(
            layout, idx=21 + i * 2, name=f"KPI {i+1} Delta", ph_type="body",
            x_px=x + 24, y_px=y0 + 268, w_px=kpi_w - 48, h_px=24,
            prompt_text=delta,
            size_px=T.SIZE_PX["kpi_delta"],
            weight="regular",
            font=T.FONT_DISPLAY,
            color=delta_color,
            tracking_em=0,
        )
