"""Feinschliff · Funnel — vertical trapezoidal funnel + side dropoff column.

A multi-stage conversion view: 4 stacked trapezoidal slices (wide → narrow,
top → bottom) with name + detail + volume + rate labels to the right of
each slice; up to 3 dropoff explainers to the right of the funnel.

Schema is preserved from the original stub (3–6 stages allowed); the
template renders the canonical 4-stage layout — extra stages can be added
by users at slide-edit time.
"""
from __future__ import annotations

import theme as T
from components import (
    add_funnel, add_rect, add_text_placeholder, funnel_geometry,
    paint_chrome, set_layout_background, set_layout_name,
)
from layouts._shared import content_header


NAME = "Feinschliff · Funnel"
BG = "white"
PGMETA = "Funnel"
EYEBROW_PROMPT = "App activation funnel · Q4 FY25"
TITLE_PROMPT = (
    "One in three buyers never pairs their product — first-run setup "
    "is the largest and most fixable drop-off."
)

# Canvas geometry (CSS px). Header occupies y < 460; funnel + side live below.
FUNNEL_X = 100
FUNNEL_Y = 480
FUNNEL_W = 480
FUNNEL_H = 500
FUNNEL_TOP_W = 480
FUNNEL_BOT_W = 140

# Stage label band sits to the right of the funnel.
LABEL_X = 620
LABEL_W = 320
VOL_X = LABEL_X + LABEL_W + 20  # 960
VOL_W = 140

# Side column for dropoffs — clearly separated from the volume column.
SIDE_X = 1180
SIDE_Y = 480
SIDE_W = 640

# Per-stage idx offsets. idx_base = 20 + i*4. Order matches placeholder_map.
STAGE_FIELDS = ("name", "detail", "volume", "rate")  # offsets 0,1,2,3
N_STAGES = 4

# Per-dropoff idx offsets. idx_base = 50 + i*4. Order: pct, label, body.
DROPOFF_FIELDS = ("pct", "label", "body")
N_DROPOFFS = 3

# Schema preserved from stub — do not edit shape; only build() changes.
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
    "stages": {
        "type": "array",
        "minItems": 3,
        "maxItems": 6,
        "items": {
            "type": "object",
            "properties": {
                "name":   {"type": "string", "maxLength": 40},
                "detail": {"type": "string", "maxLength": 60, "optional": True},
                "volume": {"type": "string", "maxLength": 12},
                "rate":   {"type": "string", "maxLength": 12, "optional": True},
                "accent": {"type": "boolean", "optional": True},
            },
            "required": ["name", "volume"],
        },
    },
    "dropoffs": {
        "type": "array",
        "optional": True,
        "minItems": 0,
        "maxItems": 3,
        "items": {
            "type": "object",
            "properties": {
                "pct":   {"type": "string"},
                "label": {"type": "string", "maxLength": 40},
                "body":  {"type": "string", "maxLength": 160},
            },
            "required": ["pct", "label"],
        },
    },
}


# ─── Sample content used to prime the layout's placeholders ──────────────
# Mirrors the HTML reference (slide 30 · MCK · Funnel) so the demo deck
# reads correctly. Users editing the layout see these as prompt text.
SAMPLE_STAGES = [
    {"name": "Product sold",    "detail": "Shipment, any SKU",                "volume": "2.4 M",  "rate": "100%"},
    {"name": "App installed",     "detail": "Within 30 days of purchase",       "volume": "2.0 M",  "rate": "84%"},
    {"name": "Product paired",  "detail": "First-run setup completed",        "volume": "1.5 M",  "rate": "62%", "accent": True},
    {"name": "Active at 90 days", "detail": "≥4 cycles in last month",          "volume": "870 K",  "rate": "36%"},
]

SAMPLE_DROPOFFS = [
    {"pct": "−22 pt", "label": "Trial → activate",
     "body": "Activation fails on mixed-SSID routers and Wi-Fi 6 backward compatibility. Fix is scoped for Q1."},
    {"pct": "−14 pt", "label": "Feature → 90d active",
     "body": "Users try one session then default to the panel. Cadence nudges in-app are live in Q2."},
    {"pct": "",       "label": "",
     "body": ""},
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX[BG])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    # Header (eyebrow + title).
    content_header(layout, eyebrow=EYEBROW_PROMPT, title=TITLE_PROMPT)

    # Find the accent stage (first one flagged in the sample, else None).
    accent_index: int | None = None
    for i, s in enumerate(SAMPLE_STAGES[:N_STAGES]):
        if s.get("accent"):
            accent_index = i
            break

    # Draw the trapezoid stack.
    add_funnel(
        layout,
        x_px=FUNNEL_X, y_px=FUNNEL_Y, w_px=FUNNEL_W, h_px=FUNNEL_H,
        stages=SAMPLE_STAGES[:N_STAGES],
        top_w_px=FUNNEL_TOP_W,
        bottom_w_px=FUNNEL_BOT_W,
        accent_index=accent_index,
        fill_color=T.INK,
        accent_color=T.ACCENT,
        gap_px=4,
    )

    # Per-slice geometry — used to align the right-side label band.
    geom = funnel_geometry(
        FUNNEL_X, FUNNEL_Y, FUNNEL_W, FUNNEL_H, N_STAGES,
        top_w_px=FUNNEL_TOP_W, bottom_w_px=FUNNEL_BOT_W, gap_px=4,
    )

    # Per-stage label placeholders — vol on the right edge, name/detail flush left.
    for i in range(N_STAGES):
        sample = SAMPLE_STAGES[i]
        slice_y = geom[i]["y"]
        slice_h = geom[i]["h"]
        idx_base = 20 + i * 4

        # Top hairline above each label band — mirrors HTML .funnel .label border-top.
        add_rect(layout, LABEL_X, slice_y, LABEL_W + VOL_W + 20, 1, fill=T.FOG)

        # Stage NAME — display weight, slightly tighter tracking.
        add_text_placeholder(
            layout, idx=idx_base, name=f"Stage {i+1} Name", ph_type="body",
            x_px=LABEL_X, y_px=slice_y + 12, w_px=LABEL_W, h_px=36,
            prompt_text=sample["name"],
            size_px=26, weight="medium", color=T.INK,
            tracking_em=-0.012, line_height=1.1,
        )

        # Stage DETAIL — small graphite caption.
        add_text_placeholder(
            layout, idx=idx_base + 1, name=f"Stage {i+1} Detail", ph_type="body",
            x_px=LABEL_X, y_px=slice_y + 50, w_px=LABEL_W, h_px=24,
            prompt_text=sample.get("detail", ""),
            size_px=14, color=T.GRAPHITE, line_height=1.3,
        )

        # Stage VOLUME — large display number, right-aligned in its own band.
        add_text_placeholder(
            layout, idx=idx_base + 2, name=f"Stage {i+1} Volume", ph_type="body",
            x_px=VOL_X, y_px=slice_y + 12, w_px=VOL_W, h_px=44,
            prompt_text=sample["volume"],
            size_px=34, weight="bold", color=T.INK,
            tracking_em=-0.02, line_height=1.0, align="r",
        )

        # Stage RATE — mono uppercase under the volume.
        add_text_placeholder(
            layout, idx=idx_base + 3, name=f"Stage {i+1} Rate", ph_type="body",
            x_px=VOL_X, y_px=slice_y + 60, w_px=VOL_W, h_px=20,
            prompt_text=sample.get("rate", ""),
            size_px=13, font=T.FONT_MONO, color=T.GRAPHITE,
            uppercase=True, tracking_em=0.1, align="r",
        )

    # Side dropoffs column — 3 stacked cards with hairline + orange pct + label + body.
    side_card_h = (FUNNEL_H - 16 * (N_DROPOFFS - 1)) // N_DROPOFFS

    for i in range(N_DROPOFFS):
        sample = SAMPLE_DROPOFFS[i]
        card_y = SIDE_Y + i * (side_card_h + 16)
        idx_base = 50 + i * 4

        # Hairline above each card — mirrors HTML .funnel-side .drop border-top.
        add_rect(layout, SIDE_X, card_y, SIDE_W, 1, fill=T.FOG)

        # PCT — large orange display.
        add_text_placeholder(
            layout, idx=idx_base, name=f"Dropoff {i+1} Pct", ph_type="body",
            x_px=SIDE_X, y_px=card_y + 16, w_px=SIDE_W, h_px=56,
            prompt_text=sample["pct"],
            size_px=46, weight="bold", color=T.ACCENT,
            tracking_em=-0.02, line_height=1.0,
        )

        # LABEL — mono uppercase caption.
        add_text_placeholder(
            layout, idx=idx_base + 1, name=f"Dropoff {i+1} Label", ph_type="body",
            x_px=SIDE_X, y_px=card_y + 76, w_px=SIDE_W, h_px=22,
            prompt_text=sample["label"],
            size_px=14, font=T.FONT_MONO, color=T.GRAPHITE,
            uppercase=True, tracking_em=0.1,
        )

        # BODY — graphite explainer.
        add_text_placeholder(
            layout, idx=idx_base + 2, name=f"Dropoff {i+1} Body", ph_type="body",
            x_px=SIDE_X, y_px=card_y + 108, w_px=SIDE_W, h_px=side_card_h - 116,
            prompt_text=sample["body"],
            size_px=16, color=T.GRAPHITE, line_height=1.5,
        )
