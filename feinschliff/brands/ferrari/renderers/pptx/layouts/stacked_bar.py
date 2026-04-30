"""Feinschliff · Stacked Bar — vertical stacked-bar chart with side legend (HTML 22).

Reference: brands/feinschliff/claude-design/feinschliff-2026.html `MCK · Stacked Bar`.

Composition:
  - Standard content header (eyebrow + title) painted by `content_header`.
  - Chart area on the left: 5 stacked vertical bars built from coloured
    segments via `add_stacked_bar`. Bar totals + category labels are
    editable placeholders so users can rewrite numbers without touching
    the renderer.
  - Side legend on the right: one row per segment colour with a swatch,
    a name placeholder, and an optional change placeholder.
  - Mono source caption at the bottom.

Placeholder map (idx → field):
    0          action_title
    10         kicker (eyebrow)
    20 + i     categories[i].label    (i = 0..4)
    30 + i     categories[i].total    (i = 0..4)
    40 + i*2   legend[i].name         (i = 0..3)
    41 + i*2   legend[i].change       (i = 0..3)
    60         source / figure caption
"""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_stacked_bar, add_text_placeholder, paint_chrome,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header

NAME = "Feinschliff · Stacked Bar"
BG = "white"
PGMETA = "Data · Revenue mix"
EYEBROW_PROMPT = "Mix · FY21–FY25"
TITLE_PROMPT = (
    "Platform revenue is the fastest-growing share; "
    "legacy hardware is flat in absolute terms."
)

# Reference data taken from feinschliff-2026.html section 22 so the demo slide
# reads out the same story as the HTML showcase. Heights are in CSS px;
# the chart area is 280 px tall so the tallest stack (FY25 ≈ 358 px) fits
# after the heights are normalised below.
_CATEGORIES = [
    ("FY21", "11.9", [(160, "6.8"), (80, "3.2"), (40, "1.6"), (10, "0.3")]),
    ("FY22", "12.4", [(158, "6.7"), (88, "3.5"), (42, "1.7"), (16, "0.5")]),
    ("FY23", "12.9", [(156, "6.6"), (92, "3.7"), (46, "1.8"), (24, "0.8")]),
    ("FY24", "13.4", [(154, "6.5"), (98, "3.9"), (48, "1.9"), (38, "1.1")]),
    ("FY25", "14.1", [(150, "6.4"), (104, "4.2"), (52, "2.1"), (52, "1.4")]),
]

_LEGEND = [
    ("Legacy hardware",     "−6% · 5y",   T.BLACK),
    ("Consumer products", "+31% · 5y",  T.INK),
    ("Commercial",          "+31% · 5y",  T.GRAPHITE),
    ("Platform & services", "+367% · 5y", T.ACCENT),
]

# Geometry — content area is x=100..1820, y=460..1020 per the canvas spec.
_CHART_X = 100
_CHART_Y = 540
_CHART_W = 1320          # leaves a 60 px gutter before the legend
_CHART_H = 360           # vertical room for the tallest stack + a bit of air
_LABEL_Y = _CHART_Y + _CHART_H + 16
_TOTAL_BAND_H = 36       # mono band above each bar showing the total

_LEGEND_X = 1500
_LEGEND_Y = 540
_LEGEND_W = 320
_LEGEND_ROW_H = 56

_SOURCE_Y = 990


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX[BG])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    content_header(layout, eyebrow=EYEBROW_PROMPT, title=TITLE_PROMPT)

    # ── Chart ────────────────────────────────────────────────────────────
    # Figure out per-bar geometry up front so the total + label placeholders
    # line up with the bars the component paints.
    n = len(_CATEGORIES)
    bar_w = max(80, min(150, int((_CHART_W - 40 * (n - 1)) / n)))
    gap = int((_CHART_W - bar_w * n) / max(1, n - 1)) if n > 1 else 0

    # Component paints the bars + segment values from the same data we use
    # below for placeholder positioning.
    bars_data = [
        {"segments": [{"value": v, "height_px": h} for h, v in segs]}
        for _, _, segs in _CATEGORIES
    ]
    add_stacked_bar(
        layout,
        x_px=_CHART_X,
        y_px=_CHART_Y,
        w_px=_CHART_W,
        h_px=_CHART_H,
        bars=bars_data,
    )

    # Per-bar editable placeholders — total above, label below.
    for i, (label, total, _segs) in enumerate(_CATEGORIES):
        bar_x = _CHART_X + i * (bar_w + gap)

        # Total above the bar — mono, right-weight readable, sits in a
        # fixed band so users get consistent typography across all bars.
        add_text_placeholder(
            layout, idx=30 + i, name=f"Bar {i+1} Total", ph_type="body",
            x_px=bar_x, y_px=_CHART_Y - _TOTAL_BAND_H,
            w_px=bar_w, h_px=_TOTAL_BAND_H - 4,
            prompt_text=total,
            size_px=T.SIZE_PX["bar_label"], weight="medium",
            color=T.BLACK, align="c",
        )

        # Category label below the bar.
        add_text_placeholder(
            layout, idx=20 + i, name=f"Bar {i+1} Label", ph_type="body",
            x_px=bar_x, y_px=_LABEL_Y, w_px=bar_w, h_px=30,
            prompt_text=label,
            size_px=T.SIZE_PX["bar_num"], weight="bold", font=T.FONT_DISPLAY,
            color=T.GRAPHITE, uppercase=True, tracking_em=0.1, align="c",
        )

    # ── Legend ───────────────────────────────────────────────────────────
    # Mono caption sets the legend group title (matches HTML reference).
    add_text_placeholder(
        layout, idx=39, name="Legend Title", ph_type="body",
        x_px=_LEGEND_X, y_px=_LEGEND_Y - 30, w_px=_LEGEND_W, h_px=24,
        prompt_text="Segment",
        size_px=14, weight="bold", font=T.FONT_DISPLAY,
        color=T.BLACK, uppercase=True, tracking_em=0.14,
    )

    for i, (name, change, color) in enumerate(_LEGEND):
        ly = _LEGEND_Y + i * _LEGEND_ROW_H

        # Colour swatch — matches the segment fill so users can read the
        # chart without a key.
        add_rect(layout, _LEGEND_X, ly + 8, 18, 18, fill=color)

        add_text_placeholder(
            layout, idx=40 + i * 2, name=f"Legend {i+1} Name", ph_type="body",
            x_px=_LEGEND_X + 32, y_px=ly + 4, w_px=_LEGEND_W - 32, h_px=26,
            prompt_text=name,
            size_px=T.SIZE_PX["bar_num"], weight="medium",
            color=T.BLACK, line_height=1.2,
        )
        add_text_placeholder(
            layout, idx=41 + i * 2, name=f"Legend {i+1} Change", ph_type="body",
            x_px=_LEGEND_X + 32, y_px=ly + 28, w_px=_LEGEND_W - 32, h_px=24,
            prompt_text=change,
            size_px=14, weight="bold", font=T.FONT_DISPLAY,
            color=T.GRAPHITE, tracking_em=0.05,
        )

    # ── Source caption ───────────────────────────────────────────────────
    add_text_placeholder(
        layout, idx=60, name="Source", ph_type="body",
        x_px=_CHART_X, y_px=_SOURCE_Y, w_px=_CHART_W, h_px=24,
        prompt_text="Source · Sample data · EUR bn",
        size_px=14, weight="bold", font=T.FONT_DISPLAY,
        color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
    )
