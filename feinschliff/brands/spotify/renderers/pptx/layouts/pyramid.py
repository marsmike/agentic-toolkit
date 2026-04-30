"""Feinschliff · Pyramid — stacked tier hierarchy with side key.

A 3-4 tier value hierarchy shown as stacked trapezoids (apex = triangle).
The pyramid occupies the left half; a side key on the right carries the
counter + label + body for each tier, aligned vertically with the tier
it describes.

Schema is preserved from the original stub (3-4 tiers, apex-first); the
template renders a canonical 3-tier layout matching the HTML reference.
"""
from __future__ import annotations

import theme as T
from components import (
    add_pyramid, add_rect, add_text_placeholder, pyramid_geometry,
    paint_chrome, set_layout_background, set_layout_name,
)
from layouts._shared import content_header


NAME = "Feinschliff · Pyramid"
BG = "white"
PGMETA = "Pyramid"
EYEBROW_PROMPT = "Customer value"
TITLE_PROMPT = (
    "Three tiers of value: a solid product, an honest relationship, "
    "a measured experience."
)

# ─── Canvas geometry (CSS px) ────────────────────────────────────────────
# Content area y=460..1020, x=100..1820. Pyramid on the left, key on right.
PYRAMID_X = 140
PYRAMID_Y = 480
PYRAMID_W = 760
PYRAMID_H = 520
APEX_W = 0        # pure triangle apex
BASE_W = 760      # matches PYRAMID_W
GAP_PX = 4

# Side key column.
SIDE_X = 1000
SIDE_Y = 480
SIDE_W = 820

# Per-tier idx offsets. idx_base = 20 + i*4.
#   +0 tier label       (short name shown on the tier shape)
#   +1 tier body        (side-key explainer)
#   +2 tier counter     (side-key mono tag, e.g. "Tier 03 · Meaning")
N_TIERS = 3

# Schema preserved from stub — do not alter shape; only build() changes.
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
    "tiers": {
        "type": "array",
        "minItems": 3,
        "maxItems": 4,
        "description": "Ordered top-tier-first.",
        "items": {
            "type": "object",
            "properties": {
                "counter": {"type": "string", "maxLength": 20},
                "label":   {"type": "string", "maxLength": 40},
                "body":    {"type": "string", "maxLength": 160},
            },
            "required": ["counter", "label"],
        },
    },
}


# ─── Sample content (apex-first, matches the HTML reference deck) ───────
SAMPLE_TIERS = [
    {
        "counter": "Tier 03 · Meaning",
        "label": "A measured experience.",
        "body": "Time given back; one less thing to think about.",
    },
    {
        "counter": "Tier 02 · Trust",
        "label": "An honest relationship.",
        "body": "The product tells you the truth about itself — status, usage, when to act.",
    },
    {
        "counter": "Tier 01 · Foundation",
        "label": "A solid product.",
        "body": "Things that work, for years, in any context — solid, reliable, supportable.",
    },
]


# Tier fills are resolved inside add_pyramid() — for the canonical 3-tier
# banding (apex=GRAPHITE, middle=ORANGE, base=INK) white labels read on every
# band. For 4 tiers the apex flips to FOG and needs an ink-on-light label.
def _label_color_on_tier(i: int, n: int):
    if n == 4 and i == 0:
        return T.INK
    return T.BLACK


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX[BG])
    paint_chrome(layout, variant="light", pgmeta=PGMETA)

    # Header (eyebrow + title).
    content_header(layout, eyebrow=EYEBROW_PROMPT, title=TITLE_PROMPT)

    # Draw the pyramid stack (apex-first data).
    add_pyramid(
        layout,
        x_px=PYRAMID_X, y_px=PYRAMID_Y, w_px=PYRAMID_W, h_px=PYRAMID_H,
        tiers=SAMPLE_TIERS[:N_TIERS],
        apex_w_px=APEX_W,
        base_w_px=BASE_W,
        gap_px=GAP_PX,
    )

    # Per-tier geometry — used to align on-shape labels + side-key rows.
    geom = pyramid_geometry(
        PYRAMID_X, PYRAMID_Y, PYRAMID_W, PYRAMID_H, N_TIERS,
        apex_w_px=APEX_W, base_w_px=BASE_W, gap_px=GAP_PX,
    )

    # Per-tier placeholders.
    narrow_threshold = 260  # tiers narrower than this get a right-side label
    for i in range(N_TIERS):
        sample = SAMPLE_TIERS[i]
        g = geom[i]
        idx_base = 20 + i * 4

        tier_y = g["y"]
        tier_h = g["h"]
        tier_cx = g["cx"]
        tier_top_w = g["top_w"]
        tier_bot_w = g["bot_w"]

        # ─── Tier LABEL — centered on the tier if wide enough, else to the right.
        label_color = _label_color_on_tier(i, N_TIERS)
        if tier_bot_w >= narrow_threshold:
            lbl_x = tier_cx - tier_bot_w / 2 + 16
            lbl_w = tier_bot_w - 32
            add_text_placeholder(
                layout, idx=idx_base, name=f"Tier {i+1} Label", ph_type="body",
                x_px=lbl_x, y_px=tier_y + tier_h / 2 - 22,
                w_px=lbl_w, h_px=44,
                prompt_text=sample["label"],
                size_px=28, weight="medium", color=label_color,
                tracking_em=-0.012, line_height=1.15, align="c",
            )
        else:
            # Narrow apex — label floats out to the right of the tier.
            lbl_x = tier_cx + max(tier_top_w, tier_bot_w) / 2 + 16
            add_text_placeholder(
                layout, idx=idx_base, name=f"Tier {i+1} Label", ph_type="body",
                x_px=lbl_x, y_px=tier_y + tier_h / 2 - 22,
                w_px=340, h_px=44,
                prompt_text=sample["label"],
                size_px=24, weight="medium", color=T.INK,
                tracking_em=-0.012, line_height=1.15, align="l",
            )

        # ─── Side-key row — hairline + counter (mono) + body, aligned with this tier.
        card_y = tier_y
        card_h = tier_h

        add_rect(layout, SIDE_X, card_y, SIDE_W, 1, fill=T.FOG)

        # COUNTER — mono uppercase tag (e.g. "Tier 03 · Meaning").
        add_text_placeholder(
            layout, idx=idx_base + 2, name=f"Tier {i+1} Counter", ph_type="body",
            x_px=SIDE_X, y_px=card_y + 16, w_px=SIDE_W, h_px=22,
            prompt_text=sample["counter"],
            size_px=14, font=T.FONT_MONO, color=T.ACCENT,
            uppercase=True, tracking_em=0.12,
        )

        # BODY — graphite explainer.
        add_text_placeholder(
            layout, idx=idx_base + 1, name=f"Tier {i+1} Body", ph_type="body",
            x_px=SIDE_X, y_px=card_y + 48, w_px=SIDE_W, h_px=card_h - 56,
            prompt_text=sample["body"],
            size_px=20, color=T.GRAPHITE, line_height=1.5,
        )
