"""Feinschliff · Vertical Bullets — McKinsey stacked-list pattern.

A vertical sequence of 3–6 labelled rows. Each row spans the full content
width: mono orange counter on the left, display-medium heading in the
middle, graphite body fills the rest. Rows are separated by thin T.FOG
hairlines. Optional lede sits under the header; optional supporting_note
is a mono caption near the bottom.

Idx allocation:
    0         action_title
    10        kicker
    11        lede             (prose lede under header)
    12        supporting_note  (mono caption bottom)
    20 + i*3  row i counter   (i in 0..5)
    21 + i*3  row i heading
    22 + i*3  row i body
"""
from __future__ import annotations

import theme as T
from components import (
    add_line, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header

NAME = 'Feinschliff · Vertical Bullets'
BG = 'white'
PGMETA = 'Vertical Bullets'
EYEBROW_PROMPT = 'Plan of record'
TITLE_PROMPT = 'Five moves define the first half: consolidate, instrument, retire, pilot, publish.'

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
    "lede": {
        "type": "string",
        "maxLength": 280
    },
    "supporting_note": {
        "type": "string",
        "maxLength": 160,
        "optional": True
    },
    "items": {
        "type": "array",
        "minItems": 3,
        "maxItems": 6,
        "items": {
            "type": "object",
            "properties": {
                "counter": {
                    "type": "string",
                    "maxLength": 6
                },
                "heading": {
                    "type": "string",
                    "maxLength": 60
                },
                "body": {
                    "type": "string",
                    "maxLength": 180
                }
            },
            "required": [
                "counter",
                "heading",
                "body"
            ]
        }
    }
}

# Sample rows — populate the layout preview in PowerPoint's New Slide menu.
SAMPLE_ITEMS = [
    ("01 / 06", "Consolidate the firmware stack.",
     "Move the remaining three product lines onto the unified OS core by end of Q2."),
    ("02 / 06", "Instrument every SKU.",
     "Every production unit leaving the factory reports health and usage by default."),
    ("03 / 06", "Retire the legacy app.",
     "Archive the legacy companion app once the new platform reaches 70% coverage."),
    ("04 / 06", "Pilot guided sessions.",
     "Run a two-thousand-customer test of the adaptive programme across three regions."),
    ("05 / 06", "Publish the API.",
     "Open the developer preview to partners at the end of H1."),
    ("06 / 06", "Review monthly.",
     "Each move is owned by one VP and reviewed at the monthly operating meeting."),
]

# Row geometry — full content width, 3-column split per row.
ROW_X = 100
ROW_W = 1720
COUNTER_W = 140
HEADING_W = 420
GAP = 24


def _add_vertical_row(layout, *, idx_base: int, y_px: int, row_h: int, sample):
    """Emit one stacked bullet row: hairline + counter + heading + body placeholders."""
    counter, heading, body = sample

    add_line(layout, ROW_X, y_px, ROW_W, 1, T.FOG)

    # Vertically centre text within the row (row_h ~ 85, text block ~ 40).
    text_y = y_px + (row_h - 40) // 2

    # Counter — mono orange, left.
    add_text_placeholder(
        layout, idx=idx_base, name=f"Row {(idx_base - 20) // 3 + 1} Counter",
        ph_type="body",
        x_px=ROW_X, y_px=text_y + 6, w_px=COUNTER_W, h_px=30,
        prompt_text=counter,
        size_px=T.SIZE_PX["agenda_num"], weight="bold", font=T.FONT_DISPLAY,
        color=T.ACCENT, tracking_em=0.1,
    )

    # Heading — display medium, ink.
    heading_x = ROW_X + COUNTER_W + GAP
    add_text_placeholder(
        layout, idx=idx_base + 1, name=f"Row {(idx_base - 20) // 3 + 1} Heading",
        ph_type="body",
        x_px=heading_x, y_px=text_y, w_px=HEADING_W, h_px=48,
        prompt_text=heading,
        size_px=T.SIZE_PX["agenda_t"], weight="bold",
        color=T.BLACK, tracking_em=0, line_height=1.15,
    )

    # Body — graphite, fills the rest.
    body_x = heading_x + HEADING_W + GAP
    body_w = ROW_X + ROW_W - body_x
    add_text_placeholder(
        layout, idx=idx_base + 2, name=f"Row {(idx_base - 20) // 3 + 1} Body",
        ph_type="body",
        x_px=body_x, y_px=text_y + 4, w_px=body_w, h_px=row_h - 16,
        prompt_text=body,
        size_px=T.SIZE_PX["agenda_d"],
        color=T.GRAPHITE, line_height=1.4,
    )


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX[BG])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    # Header — rule at y=140 so rows fit below.
    content_header(
        layout,
        eyebrow=EYEBROW_PROMPT,
        title=TITLE_PROMPT,
        y_rule=140,
    )

    # Lede — prose paragraph under the title, full content width.
    add_text_placeholder(
        layout, idx=11, name="Lede", ph_type="body",
        x_px=ROW_X, y_px=360, w_px=ROW_W, h_px=80,
        prompt_text=(
            "Each move is owned by a single VP and reviewed at the monthly "
            "operating meeting — progress is measured against a metric, not "
            "an output."
        ),
        size_px=T.SIZE_PX["body"], color=T.GRAPHITE, line_height=1.4,
    )

    # Vertical list — 6 full-width rows, stacked.
    rows_y0 = 470
    row_h = 85
    for i, sample in enumerate(SAMPLE_ITEMS):
        idx_base = 20 + i * 3
        y = rows_y0 + i * row_h
        _add_vertical_row(layout, idx_base=idx_base, y_px=y, row_h=row_h,
                          sample=sample)

    # Final hairline under the last row.
    add_line(layout, ROW_X, rows_y0 + len(SAMPLE_ITEMS) * row_h, ROW_W, 1, T.FOG)

    # Supporting note — mono caption near the bottom.
    add_text_placeholder(
        layout, idx=12, name="Supporting Note", ph_type="body",
        x_px=ROW_X, y_px=1010, w_px=ROW_W, h_px=30,
        prompt_text="Work that does not support one of these moves is explicitly descoped, not paused.",
        size_px=14, weight="bold", font=T.FONT_DISPLAY, color=T.GRAPHITE,
        uppercase=True, tracking_em=0.1,
    )
