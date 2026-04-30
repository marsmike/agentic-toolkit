"""Feinschliff · Gantt — programme timeline across parallel workstream lanes.

Layout (1920 × 1080):
    y =   0..260  chrome (logo, pgmeta) painted by paint_chrome
    y = 260..440  content_header (eyebrow + title rule + slide title)
    y = 460..1020 Gantt chart (time-axis header + lane rows)
    y =1000       footer / source caption (mono)

Schema (preserved verbatim from the stub) permits very rich nested
structure — up to 189 slot paths for `lanes[].bars[]` and `lanes[]
.milestones[]` over a custom axis. This layout implements a practical
visual subset matching the HTML reference (section `MCK · Gantt`):

    4 periods · 4 lanes · 2–3 bars per lane · up to 1 milestone per lane

Idx allocation:
    0               action_title (title)
    10              kicker (eyebrow)
    20..23          period labels (up to 4)
    30..33          lane name labels (up to 4)
    40 + l*3 + b    bar label within lane `l`, bar `b`   (up to 4×3 = 12, so 40..51)
    60              source / caption
"""
from __future__ import annotations

import theme as T
from components import (
    add_gantt, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header


NAME = "Feinschliff · Gantt"
BG = "white"
PGMETA = "Gantt"
EYEBROW_PROMPT = "Workstreams — FY25 delivery plan"
TITLE_PROMPT = (
    "Firmware consolidation lands in Q2; the developer API goes GA in Q4, "
    "dependent on telemetry rollout."
)

# Chart canvas — below the content_header, above the footer caption.
CHART_X = 100
CHART_Y = 460
CHART_W = 1720
# Header (48) + 4 × 80-px lane rows = 368. Leave ~190 px gap for the caption.
CHART_H = 48 + 4 * 80

# Demo content — mirrors HTML reference `MCK · Gantt` (section 29).
# "period" is a 0-based column index; "span" counts columns the bar covers.
SAMPLE_PERIODS = ["Q1 · Plan", "Q2 · Build", "Q3 · Pilot", "Q4 · Scale"]

SAMPLE_LANES = [
    {
        "name":  "Firmware consolidation",
        "owner": "Owner · Platform",
        "bars": [
            {"period": 0, "span": 2, "style": "accent", "label": "Cutover · all SKUs"},
        ],
        "milestones": [
            {"period": 1, "offset_frac": 0.9},
        ],
    },
    {
        "name":  "Default-on telemetry",
        "owner": "Owner · Data",
        "bars": [
            {"period": 0, "span": 3, "style": "default", "label": "Factory rollout"},
        ],
        "milestones": [
            {"period": 2, "offset_frac": 0.8},
        ],
    },
    {
        "name":  "Regional pilot · 2,000 customers",
        "owner": "Owner · Consumer",
        "bars": [
            {"period": 1, "span": 1, "style": "ghost",  "label": ""},
            {"period": 2, "span": 2, "style": "accent", "label": "Instrumented study"},
        ],
    },
    {
        "name":  "Developer API",
        "owner": "Owner · Platform",
        "bars": [
            {"period": 1, "span": 1, "style": "ghost",  "label": ""},
            {"period": 2, "span": 1, "style": "default", "label": "Preview"},
            {"period": 3, "span": 1, "style": "accent",  "label": "GA"},
        ],
        "milestones": [
            {"period": 3, "offset_frac": 0.9},
        ],
    },
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
    "period_labels": {
        "type": "array",
        "minItems": 3,
        "maxItems": 8,
        "items": {
            "type": "string",
            "maxLength": 12
        },
        "description": "e.g. Q1 FY25..Q4 FY25"
    },
    "lanes": {
        "type": "array",
        "minItems": 3,
        "maxItems": 8,
        "items": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "maxLength": 40
                },
                "owner": {
                    "type": "string",
                    "maxLength": 40,
                    "optional": True
                },
                "bars": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "start_pct": {
                                "type": "number"
                            },
                            "end_pct": {
                                "type": "number"
                            },
                            "style": {
                                "type": "string",
                                "description": "default | accent | ghost"
                            },
                            "label": {
                                "type": "string",
                                "maxLength": 40,
                                "optional": True
                            }
                        },
                        "required": [
                            "start_pct",
                            "end_pct"
                        ]
                    }
                },
                "milestones": {
                    "type": "array",
                    "optional": True,
                    "items": {
                        "type": "object",
                        "properties": {
                            "pct": {
                                "type": "number"
                            }
                        },
                        "required": [
                            "pct"
                        ]
                    }
                }
            },
            "required": [
                "name",
                "bars"
            ]
        }
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

    # ─── Draw Gantt geometry (header, lanes, bars, milestones) ───────────
    geom = add_gantt(
        layout,
        CHART_X, CHART_Y, CHART_W, CHART_H,
        SAMPLE_LANES, SAMPLE_PERIODS,
    )

    # ─── Period header placeholders (idx 20..23) ─────────────────────────
    # Each period sits left-aligned inside its column — mono uppercase with
    # a little tracking, matching the HTML `.qh` styling.
    for i, label in enumerate(SAMPLE_PERIODS[:4]):
        col = geom["header"]["cols"][i]
        add_text_placeholder(
            layout, idx=20 + i,
            name=f"Period {i+1}", ph_type="body",
            x_px=col["x"] + 10, y_px=col["y"] + 14,
            w_px=col["w"] - 20, h_px=col["h"] - 14,
            prompt_text=label,
            size_px=14, weight="bold", font=T.FONT_DISPLAY,
            color=T.BLACK, uppercase=True, tracking_em=0.1,
            align="l",
        )

    # ─── Lane label placeholders (idx 30..33) ────────────────────────────
    # Lane name is mono uppercase orange accent; owner hint is a small
    # graphite mono line beneath it. One combined placeholder per lane so
    # /deck can wire a single string per lane.
    for li, lane in enumerate(SAMPLE_LANES[:4]):
        label_bbox = geom["lanes"][li]["label"]
        prompt = lane["name"]
        if lane.get("owner"):
            prompt = f"{lane['name']}\n{lane['owner']}"
        add_text_placeholder(
            layout, idx=30 + li,
            name=f"Lane {li+1} Label", ph_type="body",
            x_px=label_bbox["x"] + 10,
            y_px=label_bbox["y"] + 10,
            w_px=label_bbox["w"] - 20,
            h_px=label_bbox["h"] - 20,
            prompt_text=prompt,
            size_px=14, weight="bold", font=T.FONT_DISPLAY,
            color=T.ACCENT, uppercase=True, tracking_em=0.1,
            line_height=1.5,
            align="l", anchor="m",
        )

    # ─── Bar label placeholders (idx 40 + l*3 + b, up to 4×3 = 40..51) ───
    # One placeholder per bar — sits centred inside the bar rect. Skips
    # "ghost" bars (dependency windows have no label).
    for li, lane in enumerate(SAMPLE_LANES[:4]):
        bar_bboxes = geom["lanes"][li]["bars"]
        for bi, (bbox, bar_def) in enumerate(zip(bar_bboxes, lane.get("bars", []))):
            if bi >= 3:
                break  # cap at 3 bars per lane (idx budget)
            style = bbox.get("style", "default")
            if style == "ghost":
                continue  # dependency hairline: no label
            idx = 40 + li * 3 + bi
            # Text colour that contrasts with the bar fill.
            text_color = T.BLACK if style == "accent" else T.INK
            add_text_placeholder(
                layout, idx=idx,
                name=f"Lane {li+1} Bar {bi+1} Label", ph_type="body",
                x_px=bbox["x"] + 8, y_px=bbox["y"],
                w_px=bbox["w"] - 16, h_px=bbox["h"],
                prompt_text=bar_def.get("label", "") or "",
                size_px=13, weight="bold", font=T.FONT_DISPLAY,
                color=text_color, uppercase=True, tracking_em=0.08,
                align="l", anchor="m",
            )

    # ─── Trailing source / caption (idx 60, mono mid-grey) ───────────────
    add_text_placeholder(
        layout, idx=60, name="Source / caption", ph_type="body",
        x_px=100, y_px=1000, w_px=1720, h_px=24,
        prompt_text="Committed · Critical path · Dependency window · Milestone",
        size_px=14, weight="bold", font=T.FONT_DISPLAY,
        color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
    )
