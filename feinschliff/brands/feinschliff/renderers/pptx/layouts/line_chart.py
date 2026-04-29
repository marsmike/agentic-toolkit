"""Feinschliff · Line Chart — 1–3 polyline series with axes, gridlines, dots, legend.

Composes `add_line_chart` for the chart frame plus editable placeholders
for every label that managers will want to rewrite (kicker, action title,
x-category labels, series names, caption / source). The line geometry
itself uses fixed sample data — users edit the labels through PowerPoint;
re-shaping the curve requires another `/extend` pass.

Idx allocation (must be unique within the layout):
    0          : action_title (title placeholder)
    10         : kicker (eyebrow placeholder)
    20..27     : x-axis category labels (one per data point, up to 8)
    30..32     : series name labels (one per series, up to 3)
    40         : caption / source line (mono, bottom)

Spec carried `idx_base = 20 + i*4` for x-categories — that pattern fits
object-array slots (4 fields per item). x_labels is a string array, so
each category has exactly one placeholder; we use plain `20 + i` to keep
all slots unique with the series labels (30+i) and caption (40).
"""
from __future__ import annotations

import theme as T
from components import (
    add_line_chart, add_rect, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header

NAME = "Feinschliff · Line Chart"
BG = "white"
PGMETA = "Line Chart"
EYEBROW_PROMPT = "Per-account metrics, FY21–FY25"
TITLE_PROMPT = (
    "Per-account active time grew 43% while cloud cost per account "
    "declined — platform economics are turning."
)

# Public schema — unchanged from the stub. /deck consumers depend on it.
SLOTS_SCHEMA = {
    "kicker": {
        "type": "string",
        "maxLength": 40,
        "optional": True,
    },
    "action_title": {
        "type": "string",
        "maxLength": 180,
    },
    "x_labels": {
        "type": "array",
        "minItems": 3,
        "maxItems": 8,
        "items": {
            "type": "string",
            "maxLength": 8,
        },
    },
    "series": {
        "type": "array",
        "minItems": 1,
        "maxItems": 3,
        "items": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "maxLength": 40,
                },
                "values": {
                    "type": "array",
                    "items": {
                        "type": "number",
                    },
                },
                "accent": {
                    "type": "boolean",
                    "optional": True,
                },
            },
            "required": [
                "name",
                "values",
            ],
        },
    },
    "annotation": {
        "type": "string",
        "maxLength": 200,
        "optional": True,
    },
    "source": {
        "type": "string",
        "maxLength": 160,
        "optional": True,
    },
}

# ─── Demo data — mirrors HTML reference 27 (MCK · Line Chart) ─────────────
# 5 buckets × 2 series. Series A rises (active time), Series B falls
# (cloud cost). y_max = 200 chosen so both lines occupy the same band.
X_LABELS = ["FY21", "FY22", "FY23", "FY24", "FY25"]
SERIES = [
    {"name": "Active time per account", "values": [128, 138, 162, 175, 184]},
    {"name": "Cloud cost per account", "values": [180, 168, 140, 105, 70]},
]
Y_MAX = 200

# Legend swatch geometry (small filled bar + name).
LEGEND_SW_W = 18
LEGEND_SW_H = 6
LEGEND_GAP = 18
LEGEND_NAME_W = 320
LEGEND_ROW_H = 28


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    content_header(layout, eyebrow=EYEBROW_PROMPT, title=TITLE_PROMPT)

    # ─── Chart frame ───
    # Content area: x=100..1820, y=460..1020 per spec. Reserve the
    # right-most ~360 px for the legend stack so the chart breathes.
    chart_x = 100
    chart_y = 460
    chart_w = 1300
    chart_h = 520

    add_line_chart(
        layout, chart_x, chart_y, chart_w, chart_h,
        SERIES, x_labels=None, y_max=Y_MAX,
    )

    # ─── X-axis category labels (editable placeholders) ───
    # Re-render the x-axis text band as placeholders so a user can rewrite
    # FY21 → Q1 etc. without re-running the renderer. Mirrors the static
    # tick layout the component uses (chart_x + AXIS_LEFT_PX .. chart_x1 -
    # AXIS_RIGHT_PX, just below the x-axis line).
    from components.line_chart import (
        AXIS_LEFT_PX, AXIS_RIGHT_PX, AXIS_BOTTOM_PX,
    )
    inner_x0 = chart_x + AXIS_LEFT_PX
    inner_w = chart_w - AXIS_LEFT_PX - AXIS_RIGHT_PX
    label_y = chart_y + chart_h - AXIS_BOTTOM_PX + 14

    n_labels = len(X_LABELS)
    for i in range(n_labels):
        cx = inner_x0 + (i / (n_labels - 1)) * inner_w if n_labels > 1 \
            else inner_x0 + inner_w / 2
        tw = 100
        add_text_placeholder(
            layout, idx=20 + i, name=f"X label {i+1}", ph_type="body",
            x_px=cx - tw / 2, y_px=label_y, w_px=tw, h_px=24,
            prompt_text=X_LABELS[i],
            size_px=14, font=T.FONT_MONO, color=T.GRAPHITE,
            uppercase=True, tracking_em=0.08, align="c",
        )

    # ─── Legend (right column) ───
    # Series-name placeholders next to coloured swatches. Editable so the
    # user can rename the series; the swatch colours are baked in.
    legend_x = chart_x + chart_w + 40
    legend_y0 = chart_y + 40
    SERIES_COLORS = (T.ACCENT, T.INK, T.GRAPHITE)

    for i, s in enumerate(SERIES[:3]):
        ly = legend_y0 + i * (LEGEND_ROW_H + 12)
        # Swatch — a short coloured bar (matches HTML .legrow .sw 18×6).
        add_rect(
            layout, legend_x, ly + (LEGEND_ROW_H - LEGEND_SW_H) / 2,
            LEGEND_SW_W, LEGEND_SW_H,
            fill=SERIES_COLORS[i],
        )
        # Series name placeholder.
        add_text_placeholder(
            layout, idx=30 + i, name=f"Series {i+1} Name", ph_type="body",
            x_px=legend_x + LEGEND_SW_W + LEGEND_GAP,
            y_px=ly,
            w_px=LEGEND_NAME_W,
            h_px=LEGEND_ROW_H,
            prompt_text=s["name"],
            size_px=18, weight="medium", color=T.BLACK,
            line_height=1.2,
        )

    # ─── Caption / source line (mono, bottom) ───
    add_text_placeholder(
        layout, idx=40, name="Source / caption", ph_type="body",
        x_px=100, y_px=995, w_px=1720, h_px=24,
        prompt_text="Source · Feinschliff analytics, n = 2.4M accounts",
        size_px=14, font=T.FONT_MONO, color=T.GRAPHITE,
        uppercase=True, tracking_em=0.1,
    )
