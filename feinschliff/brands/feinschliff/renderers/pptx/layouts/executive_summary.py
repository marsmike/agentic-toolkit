"""Feinschliff · Executive Summary — one-page board-pack opener.

Opening slide for a board-pack deck: a prose lede under the action title,
two parallel labelled bullet lists (Insights vs Next steps) below, and a
small KPI ribbon at the bottom. Each list item is a disc-bulleted entry
with a display-medium heading and a graphite body.

Idx allocation:
    0         action_title           (display bold title)
    10        kicker                 (mono orange eyebrow)
    11        lede                   (prose paragraph under header)

    20        insights column heading label
    21 + i*2  insight i heading       (i in 0..3)
    22 + i*2  insight i body

    30        next_steps column heading label
    31 + i*2  next_step i heading     (i in 0..3)
    32 + i*2  next_step i body

    50 + k*3  kpi k value             (k in 0..2)
    51 + k*3  kpi k unit
    52 + k*3  kpi k key

    60        source (mono footer caption)
"""
from __future__ import annotations

import theme as T
from components import (
    add_line, add_rect, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header

NAME = 'Feinschliff · Executive Summary'
BG = 'white'
PGMETA = 'Executive Summary'
EYEBROW_PROMPT = 'Executive summary'
TITLE_PROMPT = 'Four insights, three next steps — the 2026 plan on one page.'

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
    "lede": {
        "type": "string",
        "maxLength": 280,
    },
    "insights": {
        "type": "array",
        "minItems": 2,
        "maxItems": 5,
        "items": {
            "type": "object",
            "properties": {
                "heading": {"type": "string", "maxLength": 60},
                "body": {"type": "string", "maxLength": 180},
            },
            "required": ["heading", "body"],
        },
    },
    "next_steps": {
        "type": "array",
        "minItems": 2,
        "maxItems": 5,
        "items": {
            "type": "object",
            "properties": {
                "heading": {"type": "string", "maxLength": 60},
                "body": {"type": "string", "maxLength": 180},
            },
            "required": ["heading", "body"],
        },
    },
    "kpis": {
        "type": "array",
        "minItems": 0,
        "maxItems": 3,
        "optional": True,
        "items": {
            "type": "object",
            "properties": {
                "value": {"type": "string", "maxLength": 20},
                "unit": {"type": "string", "maxLength": 10},
                "key": {"type": "string", "maxLength": 40},
            },
            "required": ["value", "key"],
        },
    },
    "source": {
        "type": "string",
        "maxLength": 160,
        "optional": True,
    },
}

# Prompt samples — populate the layout preview in PowerPoint's New Slide menu.
SAMPLE_LEDE = (
    "Platform economics turned in FY25 — active use per household grew while "
    "cloud cost fell. Convert that signal into the 2026 commitments below."
)

SAMPLE_INSIGHTS = [
    ("Platform share is compounding.",
     "Platform and services are the fastest-growing revenue line; legacy hardware is flat in absolute terms."),
    ("First-run pairing is the biggest leak.",
     "One in three buyers never pairs the product — fixable in firmware and the quickest lift to 90-day activation."),
    ("Telemetry is now default-on.",
     "Every production unit reports usage and health from day one; the data contract is locked and versioned."),
    ("Hybrid platform beats build-vs-buy.",
     "Core in-house, cloud and ML partner-operated — wins on speed and control without the full build-out."),
]

SAMPLE_NEXT_STEPS = [
    ("Consolidate firmware across SKUs.",
     "Retire the last two forks; every line onto the shared OS core by end of Q2."),
    ("Ship the pairing-flow fix.",
     "Firmware patch for mixed-SSID routers lands in the Q1 release, with instrumentation on first-try success."),
    ("Open the developer API preview.",
     "Partner preview end of H1, GA at year-end — 30 design partners already signed."),
    ("Lock the hybrid platform deal.",
     "Finalise cloud and ML vendor terms; platform group staffed and chartered for a Q2 kick-off."),
]

SAMPLE_KPIS = [
    ("+43", "%",   "Active time · 5y"),
    ("14",  " bn", "Revenue · EUR"),
    ("95",  "%",   "Telemetry opt-in"),
]

SAMPLE_SOURCE = "Source · Internal finance + connected-home analytics, preliminary FY25"

# Layout geometry — canvas 1920 × 1080, content area x=100..1820 (1720 wide).
CONTENT_X = 100
CONTENT_W = 1720
HEADER_RULE_Y = 140
LEDE_Y = 360
LEDE_H = 80

COLS_Y = 500
COLS_LABEL_H = 28
COLS_ITEMS_Y0 = 548
COLS_H = 340
COL_GAP = 80
COL_W = (CONTENT_W - COL_GAP) // 2   # 820

# Item row geometry (per-column).
ITEM_H = 80
BULLET_OFFSET_X = 0
BULLET_SIZE = 8
BULLET_INDENT = 24   # text starts this many px right of the column left edge
ITEM_TEXT_W = COL_W - BULLET_INDENT
HEADING_H = 32
BODY_H = 44

# KPI ribbon — sits below the two columns, above the source line.
KPI_Y = 910
KPI_H = 80
SOURCE_Y = 1020


def _add_column(
    layout, *,
    col_idx: int,
    x: int,
    label_idx: int,
    label_text: str,
    heading_idx_base: int,
    samples: list[tuple[str, str]],
) -> None:
    """Emit a column: uppercase mono-orange label, thin rule, four bullet items."""
    # Column label — mono orange caps, editable placeholder so users can
    # retitle ("Findings", "Risks", etc.) without leaving the layout.
    add_text_placeholder(
        layout, idx=label_idx, name=f"Col{col_idx} Label", ph_type="body",
        x_px=x, y_px=COLS_Y, w_px=COL_W, h_px=COLS_LABEL_H,
        prompt_text=label_text,
        size_px=14, font=T.FONT_MONO, color=T.ACCENT,
        uppercase=True, tracking_em=0.16,
    )
    # Thin hairline under the label.
    add_line(layout, x, COLS_Y + COLS_LABEL_H + 4, COL_W, 1, T.FOG)

    # Four item placeholders, stacked.
    for i in range(4):
        item_y = COLS_ITEMS_Y0 + i * ITEM_H
        # Disc bullet — orange, static primitive (decorative).
        add_rect(
            layout, x, item_y + 10, BULLET_SIZE, BULLET_SIZE,
            fill=T.ACCENT,
        )
        # Heading — display medium, ink.
        heading_text, body_text = (
            samples[i] if i < len(samples) else ("", "")
        )
        add_text_placeholder(
            layout,
            idx=heading_idx_base + 1 + i * 2,
            name=f"Col{col_idx} Item{i+1} Heading",
            ph_type="body",
            x_px=x + BULLET_INDENT,
            y_px=item_y,
            w_px=ITEM_TEXT_W,
            h_px=HEADING_H,
            prompt_text=heading_text,
            size_px=T.SIZE_PX["agenda_t"],
            weight="medium",
            color=T.BLACK,
            tracking_em=-0.01,
            line_height=1.15,
        )
        # Body — graphite, smaller, fills rest of the item band.
        add_text_placeholder(
            layout,
            idx=heading_idx_base + 2 + i * 2,
            name=f"Col{col_idx} Item{i+1} Body",
            ph_type="body",
            x_px=x + BULLET_INDENT,
            y_px=item_y + HEADING_H + 2,
            w_px=ITEM_TEXT_W,
            h_px=BODY_H,
            prompt_text=body_text,
            size_px=T.SIZE_PX["agenda_d"],
            color=T.GRAPHITE,
            line_height=1.4,
        )


def _add_kpi_ribbon(layout) -> None:
    """Three KPI cells on a single row, separated by thin FOG hairlines.

    Each KPI has value (right-aligned display light), unit (flush-right
    small graphite), and key (mono caps caption).
    """
    n = 3
    kpi_w = CONTENT_W // n   # ~573
    value_w = 160
    unit_w = 60

    # Top + bottom hairlines framing the ribbon.
    add_line(layout, CONTENT_X, KPI_Y, CONTENT_W, 1, T.FOG)
    add_line(layout, CONTENT_X, KPI_Y + KPI_H, CONTENT_W, 1, T.FOG)

    for k in range(n):
        kx = CONTENT_X + k * kpi_w
        # Separator between cells.
        if k > 0:
            add_rect(layout, kx, KPI_Y + 8, 1, KPI_H - 16, fill=T.FOG)

        value_sample, unit_sample, key_sample = (
            SAMPLE_KPIS[k] if k < len(SAMPLE_KPIS) else ("", "", "")
        )

        # Value — display light, right-aligned, bottom-anchored.
        add_text_placeholder(
            layout,
            idx=50 + k * 3,
            name=f"KPI {k+1} Value",
            ph_type="body",
            x_px=kx + 24,
            y_px=KPI_Y + 10,
            w_px=value_w,
            h_px=KPI_H - 20,
            prompt_text=value_sample,
            size_px=56, weight="light", font=T.FONT_DISPLAY,
            color=T.BLACK, tracking_em=-0.02, align="r", anchor="b",
        )
        # Unit — small, bottom-anchored flush with value baseline.
        add_text_placeholder(
            layout,
            idx=51 + k * 3,
            name=f"KPI {k+1} Unit",
            ph_type="body",
            x_px=kx + 24 + value_w,
            y_px=KPI_Y + 10,
            w_px=unit_w,
            h_px=KPI_H - 20,
            prompt_text=unit_sample,
            size_px=22, font=T.FONT_DISPLAY,
            color=T.GRAPHITE, align="l", anchor="b",
        )
        # Key — mono caps caption, right side of the cell.
        key_x = kx + 24 + value_w + unit_w + 16
        key_w = kpi_w - (key_x - kx) - 24
        add_text_placeholder(
            layout,
            idx=52 + k * 3,
            name=f"KPI {k+1} Key",
            ph_type="body",
            x_px=key_x,
            y_px=KPI_Y + 32,
            w_px=max(120, key_w),
            h_px=26,
            prompt_text=key_sample,
            size_px=T.SIZE_PX["kpi_key"], font=T.FONT_MONO,
            color=T.GRAPHITE, uppercase=True, tracking_em=0.12, anchor="b",
        )


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX[BG])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    # Header — rule + eyebrow (idx 10) + action title (idx 0).
    content_header(
        layout,
        eyebrow=EYEBROW_PROMPT,
        title=TITLE_PROMPT,
        y_rule=HEADER_RULE_Y,
    )

    # Lede — prose paragraph, full content width, under the header stack.
    add_text_placeholder(
        layout, idx=11, name="Lede", ph_type="body",
        x_px=CONTENT_X, y_px=LEDE_Y, w_px=CONTENT_W, h_px=LEDE_H,
        prompt_text=SAMPLE_LEDE,
        size_px=T.SIZE_PX["body"], color=T.GRAPHITE, line_height=1.4,
    )

    # Two columns — Insights (left) / Next steps (right).
    left_x = CONTENT_X
    right_x = CONTENT_X + COL_W + COL_GAP
    _add_column(
        layout, col_idx=1, x=left_x,
        label_idx=20, label_text="Insights",
        heading_idx_base=20,
        samples=SAMPLE_INSIGHTS,
    )
    _add_column(
        layout, col_idx=2, x=right_x,
        label_idx=30, label_text="Next steps",
        heading_idx_base=30,
        samples=SAMPLE_NEXT_STEPS,
    )

    # KPI ribbon — three cells.
    _add_kpi_ribbon(layout)

    # Source — mono caps footer line.
    add_text_placeholder(
        layout, idx=60, name="Source", ph_type="body",
        x_px=CONTENT_X, y_px=SOURCE_Y, w_px=CONTENT_W, h_px=24,
        prompt_text=SAMPLE_SOURCE,
        size_px=14, font=T.FONT_MONO, color=T.GRAPHITE,
        uppercase=True, tracking_em=0.12,
    )
