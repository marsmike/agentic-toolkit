"""Feinschliff · Waterfall — financial/metric bridge across positive/negative drivers.

Layout (1920 × 1080):
    y =   0..260  chrome (logo, pgmeta) painted by paint_chrome
    y = 260..440  content_header (eyebrow + title rule + slide title)
    y = 460..1020 chart area
    y =1030       footer (paint_chrome)

The chart geometry is baked in via a sample bars list so the layout
renders in PowerPoint without runtime data; per-bar text is overlaid as
editable placeholders so /deck can fill real values.

Idx allocation:
    0  title
    10 eyebrow
    20 + i*4 + 0  bars[i].value  (mono numeric, above bar)
    20 + i*4 + 1  bars[i].label  (mono uppercase, below baseline)
    20 + i*4 + 2  reserved (e.g. bars[i].kind helper, currently unused)
    20 + i*4 + 3  reserved
    60 source / caption  (moved from 40 to avoid collision with bar 6
                          at 20 + 5*4 = 40 in the 8-bar layout)
"""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)
from components.waterfall import add_waterfall
from layouts._shared import content_header

NAME = 'Feinschliff · Waterfall'
BG = 'white'
PGMETA = 'Waterfall'
EYEBROW_PROMPT = 'Revenue bridge · EUR bn'
TITLE_PROMPT = 'Revenue grows 5.1% YoY; platform and services offset a mild decline in legacy lines.'

# Chart canvas — below the content_header, above the footer.
CHART_X = 100
CHART_Y = 460
CHART_W = 1720
CHART_H = 540

# Sample bars — bake a realistic 7-bar bridge so the layout reads at a
# glance even before /deck fills it. Mirrors the HTML reference design.
SAMPLE_BARS = [
    {"label": "FY24 base",  "value": 13.4, "kind": "start"},
    {"label": "Consumer",   "value":  0.6, "kind": "up"},
    {"label": "Platform",   "value":  0.4, "kind": "up"},
    {"label": "Services",   "value":  0.3, "kind": "up"},
    {"label": "Legacy",     "value":  0.3, "kind": "down"},
    {"label": "FX",         "value":  0.2, "kind": "down"},
    {"label": "FY25 total", "value": 14.1, "kind": "total"},
]

# Schema preserved verbatim from the stub so the catalog stays valid.
SLOTS_SCHEMA = {
    "kicker": {
        "type": "string",
        "maxLength": 40,
        "optional": True
    },
    "action_title": {
        "type": "string",
        "maxLength": 180
    },
    "bars": {
        "type": "array",
        "minItems": 3,
        "maxItems": 9,
        "items": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "maxLength": 20
                },
                "value": {
                    "type": "number"
                },
                "kind": {
                    "type": "string",
                    "description": "total | up | down"
                }
            },
            "required": [
                "label",
                "value",
                "kind"
            ]
        }
    },
    "source": {
        "type": "string",
        "maxLength": 160,
        "optional": True
    }
}


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX[BG])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    content_header(
        layout,
        eyebrow=EYEBROW_PROMPT,
        title=TITLE_PROMPT,
    )

    # Draw the chart geometry (bars + baseline + dashed connectors).
    bboxes = add_waterfall(
        layout,
        CHART_X, CHART_Y, CHART_W, CHART_H,
        SAMPLE_BARS,
    )

    # Per-bar editable placeholders. One value above + one label below
    # each bar; each pair shares an idx range of 4 so /deck can wire by
    # array index without colliding with neighbours.
    for i, bar in enumerate(SAMPLE_BARS):
        bbox = bboxes[i]
        idx_base = 20 + i * 4

        # Value placeholder — mono numeric, sits above the bar.
        # Anchor bars (start/total) get a slightly larger/bolder value so
        # they read as the bridge endpoints.
        is_anchor = bar["kind"] in ("start", "total")
        value_size = T.SIZE_PX["bar_num"] if not is_anchor else 24
        sign_prefix = {"up": "+", "down": "−"}.get(bar["kind"], "")
        add_text_placeholder(
            layout, idx=idx_base + 0,
            name=f"Bar {i+1} Value", ph_type="body",
            x_px=bbox["x"] - 8, y_px=bbox["value_y"],
            w_px=bbox["w"] + 16, h_px=28,
            prompt_text=f"{sign_prefix}{bar['value']:g}",
            size_px=value_size, font=T.FONT_MONO,
            color=T.BLACK, align="c",
        )

        # Label placeholder — mono uppercase tracked, sits below baseline.
        add_text_placeholder(
            layout, idx=idx_base + 1,
            name=f"Bar {i+1} Label", ph_type="body",
            x_px=bbox["x"] - 12, y_px=bbox["label_y"] + 14,
            w_px=bbox["w"] + 24, h_px=44,
            prompt_text=bar["label"],
            size_px=16, font=T.FONT_MONO,
            color=T.GRAPHITE, uppercase=True, tracking_em=0.08,
            align="c",
        )

    # Trailing source caption — same style as the bar-chart layout.
    # idx=60 (not 40) to avoid colliding with bars[5].value in the per-bar
    # grid (20 + 5*4 = 40) when the layout is filled with up to 8 bars.
    add_text_placeholder(
        layout, idx=60, name="Source", ph_type="body",
        x_px=100, y_px=1000, w_px=1720, h_px=24,
        prompt_text="Source · Internal finance, preliminary FY25 · EUR bn · variances rounded to 0.1",
        size_px=14, font=T.FONT_MONO,
        color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
    )
