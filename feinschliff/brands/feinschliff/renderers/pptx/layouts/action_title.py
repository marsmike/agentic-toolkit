"""Feinschliff · Action Title — McKinsey-style takeaway headline (HTML 16).

Reference: brands/feinschliff/claude-design/feinschliff-2026.html `MCK · Action Title`.

Composition:
  - Chrome (logo + pgmeta + footer) painted by `paint_chrome`. No separate
    eyebrow+rule stack — this layout pushes the headline high so the title
    itself carries the message.
  - Mono orange uppercase `kicker` sits in the top band.
  - Hero `action_title` occupies the upper content area at ~80px medium
    weight; the sentence IS the point.
  - Optional `supporting_body` sits left on a sub-column below the title,
    graphite body text.
  - Optional 0–2 `kpis` sit right of the supporting body, in a 2×1 grid,
    each with a display-weight value + unit, mono uppercase key,
    orange mono delta.
  - Mono uppercase `source` caption at the very bottom.

Placeholder map (idx → field):
    0      action_title            hero headline
    10     kicker                  mono orange eyebrow
    11     supporting_body         graphite narrative
    20     kpis[0].value
    21     kpis[0].unit
    22     kpis[0].key
    23     kpis[0].delta
    24     kpis[1].value
    25     kpis[1].unit
    26     kpis[1].key
    27     kpis[1].delta
    60     source
"""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)

NAME = "Feinschliff · Action Title"
BG = "white"
PGMETA = "MCK · Action title"
EYEBROW_PROMPT = "Action-title layout"
TITLE_PROMPT = (
    "Adopting the new platform will lift per-account active time "
    "by ~18% within two release cycles."
)

SLOTS_SCHEMA = {
    "kicker": {
        "type": "string",
        "maxLength": 40,
        "optional": True
    },
    "action_title": {
        "type": "string",
        "maxLength": 180,
        "description": "Full-sentence takeaway, 1–2 lines."
    },
    "supporting_body": {
        "type": "string",
        "maxLength": 320,
        "optional": True
    },
    "kpis": {
        "type": "array",
        "minItems": 0,
        "maxItems": 2,
        "optional": True,
        "items": {
            "type": "object",
            "properties": {
                "value": {
                    "type": "string"
                },
                "unit": {
                    "type": "string",
                    "optional": True
                },
                "key": {
                    "type": "string"
                },
                "delta": {
                    "type": "string",
                    "optional": True
                }
            },
            "required": [
                "value",
                "key"
            ]
        }
    },
    "source": {
        "type": "string",
        "maxLength": 160,
        "optional": True
    }
}

# ─── Geometry ────────────────────────────────────────────────────────────
# Canvas: 1920 × 1080. Headline pushed higher than standard content layouts
# (y=220 vs y=540) — the action title is the slide.
_CONTENT_X = 100
_CONTENT_W = 1720

# Top block — kicker + hero title
_KICKER_Y = 220
_KICKER_H = 30

_TITLE_Y = 270
_TITLE_H = 260            # room for 2–3 lines at ~80px with 1.1 line-height
_TITLE_SIZE = 80          # display-weight hero, medium bold

# Bottom block — supporting body on left, KPI strip on right
_BOTTOM_Y = 600
_BOTTOM_H = 340

# Two-column split: supporting body + KPI strip (1:1 via 80px gutter)
_BODY_X = _CONTENT_X
_BODY_W = 820
_KPI_X = _CONTENT_X + _BODY_W + 80    # = 1000
_KPI_W = _CONTENT_W - _BODY_W - 80    # = 820

# KPI cell geometry — two cells side-by-side inside the KPI strip
_KPI_GAP = 40
_KPI_CELL_W = (_KPI_W - _KPI_GAP) // 2  # 390
_KPI_VALUE_H = 140
_KPI_UNIT_W = 100

# Source caption at the very bottom
_SOURCE_Y = 990


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX[BG])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    # ── Kicker (mono orange uppercase, idx=10) ──────────────────────────
    add_text_placeholder(
        layout, idx=10, name="Kicker", ph_type="body",
        x_px=_CONTENT_X, y_px=_KICKER_Y, w_px=_CONTENT_W, h_px=_KICKER_H,
        prompt_text=EYEBROW_PROMPT,
        size_px=T.SIZE_PX["eyebrow"], font=T.FONT_MONO,
        color=T.ACCENT, uppercase=True, tracking_em=0.12,
    )

    # ── Action title (hero headline, idx=0) ─────────────────────────────
    add_text_placeholder(
        layout, idx=0, name="Action Title", ph_type="title",
        x_px=_CONTENT_X, y_px=_TITLE_Y, w_px=_CONTENT_W, h_px=_TITLE_H,
        prompt_text=TITLE_PROMPT,
        size_px=_TITLE_SIZE, weight="medium",
        color=T.BLACK, tracking_em=-0.02, line_height=1.1,
    )

    # ── Supporting body (left sub-column, idx=11) ───────────────────────
    add_text_placeholder(
        layout, idx=11, name="Supporting Body", ph_type="body",
        x_px=_BODY_X, y_px=_BOTTOM_Y, w_px=_BODY_W, h_px=_BOTTOM_H,
        prompt_text=(
            "In the regional pilot, accounts on the updated platform "
            "opened the app 2.3× more often and ran guided sessions 41% "
            "more per week."
        ),
        size_px=T.SIZE_PX["body"], color=T.GRAPHITE, line_height=1.5,
    )

    # ── KPIs (right strip, up to 2 cells) ───────────────────────────────
    kpi_samples = [
        ("+18", "%",  "Active time / week", "vs. prior platform"),
        ("2.3", "×",  "App open rate",      "trailing 30 days"),
    ]
    for i, (value, unit, key, delta) in enumerate(kpi_samples):
        cx = _KPI_X + i * (_KPI_CELL_W + _KPI_GAP)
        idx_base = 20 + i * 4

        # Value — right-aligned display light, bottom-anchored so the
        # baseline meets the unit no matter how many digits are typed.
        add_text_placeholder(
            layout, idx=idx_base, name=f"KPI {i+1} Value", ph_type="body",
            x_px=cx, y_px=_BOTTOM_Y, w_px=_KPI_CELL_W - _KPI_UNIT_W,
            h_px=_KPI_VALUE_H, prompt_text=value,
            size_px=T.SIZE_PX["kpi_value"], weight="light",
            font=T.FONT_DISPLAY, color=T.BLACK,
            tracking_em=-0.03, align="r", anchor="b",
        )
        # Unit — small graphite sitting flush after the value.
        add_text_placeholder(
            layout, idx=idx_base + 1, name=f"KPI {i+1} Unit", ph_type="body",
            x_px=cx + (_KPI_CELL_W - _KPI_UNIT_W), y_px=_BOTTOM_Y,
            w_px=_KPI_UNIT_W, h_px=_KPI_VALUE_H, prompt_text=unit,
            size_px=T.SIZE_PX["kpi_unit"], font=T.FONT_DISPLAY,
            color=T.GRAPHITE, align="l", anchor="b",
        )
        # Key — mono uppercase tracked, graphite, just below the value band.
        add_text_placeholder(
            layout, idx=idx_base + 2, name=f"KPI {i+1} Key", ph_type="body",
            x_px=cx, y_px=_BOTTOM_Y + _KPI_VALUE_H + 16,
            w_px=_KPI_CELL_W, h_px=30, prompt_text=key,
            size_px=T.SIZE_PX["kpi_key"], font=T.FONT_MONO,
            color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
        )
        # Delta — orange mono, trailing meta under the key.
        add_text_placeholder(
            layout, idx=idx_base + 3, name=f"KPI {i+1} Delta", ph_type="body",
            x_px=cx, y_px=_BOTTOM_Y + _KPI_VALUE_H + 48,
            w_px=_KPI_CELL_W, h_px=26, prompt_text=delta,
            size_px=T.SIZE_PX["kpi_delta"], font=T.FONT_MONO,
            color=T.ACCENT_HOVER,
        )

    # ── Source caption (mono uppercase, idx=60) ─────────────────────────
    add_text_placeholder(
        layout, idx=60, name="Source", ph_type="body",
        x_px=_CONTENT_X, y_px=_SOURCE_Y, w_px=_CONTENT_W, h_px=24,
        prompt_text=(
            "Source · Platform telemetry, Jun–Dec 2025 · "
            "N = 142k accounts"
        ),
        size_px=14, font=T.FONT_MONO,
        color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
    )
