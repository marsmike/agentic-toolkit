"""Feinschliff · Process Flow — horizontal chain of chevron stages.

Layout for 3-6 sequential steps. The `active` flag on a stage reverses the
fill/text pairing (dark fill, light text) so a manager can highlight the
current phase. Text is editable via placeholders; chevron geometry is
baked in at layout-build time.
"""
from __future__ import annotations

import theme as T
from components import (
    add_process_flow, add_text_placeholder,
    paint_chrome, set_layout_background, set_layout_name,
)
from layouts._shared import content_header

NAME = "Feinschliff · Process Flow"

# Sample drives chevron geometry + active flag. Text lives in placeholders;
# this sample only populates the Slide Master preview.
SAMPLE_STEPS = [
    {"counter": "01", "heading": "Frame",     "body": "Clarify the problem and the one outcome that matters."},
    {"counter": "02", "heading": "Prototype", "body": "Build the thin vertical slice end-to-end."},
    {"counter": "03", "heading": "Pilot",     "body": "Run it with real users on real data.", "active": True},
    {"counter": "04", "heading": "Harden",    "body": "Fix what the pilot surfaces; add observability."},
    {"counter": "05", "heading": "Scale",     "body": "Roll out to remaining regions and SKUs."},
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])
    paint_chrome(layout, variant="light", pgmeta="Process Flow")
    content_header(
        layout,
        eyebrow="Delivery sequence",
        title="Five stages · pilot highlights the current phase.",
    )

    chain_x, chain_y, chain_w, chain_h = 100, 540, 1720, 380
    # Active stages use Feinschliff accent as the highlight colour so that the
    # previous chevron's tucked-in grey tip doesn't collide with white
    # text on black (unreadable) — black text on orange reads on both
    # the body AND the previous-stage tip, so the notch overlap stops
    # mattering visually.
    bboxes = add_process_flow(
        layout, chain_x, chain_y, chain_w, chain_h, SAMPLE_STEPS,
        fill_active=T.ACCENT,
    )

    for i, (stage, bbox) in enumerate(zip(SAMPLE_STEPS, bboxes)):
        idx_base = 20 + i * 4
        is_active = bool(stage.get("active"))
        num_color = T.BLACK if is_active else T.ACCENT_HOVER
        title_color = T.BLACK if is_active else T.INK
        body_color = T.INK if is_active else T.GRAPHITE

        # Extra left inset on active stages so text clears the preceding
        # chevron's notch comfortably.
        inset_bonus = 30 if is_active else 0
        tx = bbox["text_x"] + inset_bonus
        tw = bbox["text_w"] - inset_bonus

        add_text_placeholder(
            layout, idx=idx_base, name=f"Stage {i+1} Counter", ph_type="body",
            x_px=tx, y_px=chain_y + 40, w_px=tw, h_px=30,
            prompt_text=stage["counter"],
            size_px=14, font=T.FONT_MONO, color=num_color,
            uppercase=True, tracking_em=0.12,
        )
        add_text_placeholder(
            layout, idx=idx_base + 1, name=f"Stage {i+1} Heading", ph_type="body",
            x_px=tx, y_px=chain_y + 92, w_px=tw, h_px=60,
            prompt_text=stage["heading"],
            size_px=T.SIZE_PX.get("col_title", 36), weight="medium",
            color=title_color, tracking_em=-0.012, line_height=1.15,
        )
        add_text_placeholder(
            layout, idx=idx_base + 2, name=f"Stage {i+1} Body", ph_type="body",
            x_px=tx, y_px=chain_y + 170, w_px=tw, h_px=180,
            prompt_text=stage["body"],
            size_px=T.SIZE_PX.get("col_body", 20),
            color=body_color, line_height=1.5,
        )

    add_text_placeholder(
        layout, idx=60, name="Source", ph_type="body",
        x_px=100, y_px=1000, w_px=1720, h_px=30,
        prompt_text="Source · Delivery plan · Wk 1–18 · Pilot currently in flight",
        size_px=14, font=T.FONT_MONO, color=T.GRAPHITE,
        uppercase=True, tracking_em=0.12,
    )
