"""Spotify · KPI Grid — 4-up rounded cards on dark canvas.

Spotify's app analog of the spec-cell pattern. Each KPI sits inside an
8px-rounded card on `paper` (#181818) with the elevated shadow.
Big bold value + UPPERCASE 1.4px tracked label + Spotify Green delta.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rounded_rect, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header


NAME = "Feinschliff · KPI Grid"

SAMPLES = [
    ("574",  "M",   "Monthly listeners",   "+12% YoY"),
    ("100",  "M",   "Premium subscribers", "+9% YoY"),
    ("8.5",  "B",   "Tracks streamed",     "DAILY"),
    ("184",  "",    "Markets",             "GLOBAL"),
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["surface_dark"])
    paint_chrome(layout, variant="dark", pgmeta="2026 · BY THE NUMBERS")

    content_header(layout, eyebrow="At a glance", title="By the numbers.")

    # 4-up rounded card grid
    kpi_w = 400
    gap = 24
    x0 = 120
    y0 = 540
    kpi_h = 320
    card_radius = T.RADIUS.get("card", 8)

    value_w = 240
    unit_w = (kpi_w - 64) - value_w

    for i, (value, unit, key, delta) in enumerate(SAMPLES):
        x = x0 + i * (kpi_w + gap)

        # Rounded card with elevated shadow
        add_rounded_rect(
            layout, x, y0, kpi_w, kpi_h,
            radius_px=card_radius,
            fill=T.PAPER,
            shadow="elevated",
        )

        # Value 700 bold
        add_text_placeholder(
            layout, idx=30 + i * 2, name=f"KPI {i+1} Value", ph_type="body",
            x_px=x + 32, y_px=y0 + 60, w_px=value_w, h_px=140,
            prompt_text=value,
            size_px=T.SIZE_PX["kpi_value"],
            weight="bold", font=T.FONT_DISPLAY,
            color=T.BLACK,
            tracking_em=0, line_height=1.0,
            align="l", anchor="b",
        )
        # Unit
        add_text_placeholder(
            layout, idx=31 + i * 2, name=f"KPI {i+1} Unit", ph_type="body",
            x_px=x + 32 + value_w, y_px=y0 + 60, w_px=unit_w, h_px=140,
            prompt_text=unit,
            size_px=T.SIZE_PX["kpi_unit"],
            weight="bold", font=T.FONT_DISPLAY,
            color=T.STEEL,
            tracking_em=0,
            align="l", anchor="b",
        )
        # Key — UPPERCASE 1.4px tracked
        add_text_placeholder(
            layout, idx=20 + i * 2, name=f"KPI {i+1} Key", ph_type="body",
            x_px=x + 32, y_px=y0 + 220, w_px=kpi_w - 64, h_px=28,
            prompt_text=key,
            size_px=T.SIZE_PX["kpi_key"],
            weight="bold", font=T.FONT_DISPLAY,
            color=T.BLACK, uppercase=True, tracking_em=0.1,
        )
        # Delta — Spotify Green
        add_text_placeholder(
            layout, idx=21 + i * 2, name=f"KPI {i+1} Delta", ph_type="body",
            x_px=x + 32, y_px=y0 + 260, w_px=kpi_w - 64, h_px=24,
            prompt_text=delta,
            size_px=T.SIZE_PX["kpi_delta"],
            weight="regular", font=T.FONT_DISPLAY,
            color=T.ACCENT,
            uppercase=True, tracking_em=0.05,
        )
