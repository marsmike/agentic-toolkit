"""Feinschliff · Key Takeaways — dark-ink closer with 2–4 numbered takeaway columns (HTML 25)."""
from __future__ import annotations

import theme as T
from components import (
    add_rule, add_text_placeholder,
    paint_chrome, set_layout_background, set_layout_name,
)

NAME = 'Feinschliff · Key Takeaways'
BG = 'ink'
PGMETA = 'Key Takeaways'
EYEBROW_PROMPT = 'Key Takeaways'
TITLE_PROMPT = 'End-of-section summary of 3 most important points, each with.'

# SLOTS_SCHEMA preserved verbatim from the stub (drives catalog + drift check).
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
    "cards": {
        "type": "array",
        "minItems": 2,
        "maxItems": 4,
        "items": {
            "type": "object",
            "properties": {
                "counter": {
                    "type": "string",
                    "maxLength": 6
                },
                "heading": {
                    "type": "string",
                    "maxLength": 40
                },
                "body": {
                    "type": "string",
                    "maxLength": 200
                },
                "owner": {
                    "type": "string",
                    "maxLength": 40,
                    "optional": True
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


# Sample content shown as placeholder prompts (mirrors HTML ref § 25).
_CARDS = [
    ("01", "Platform first.",
     "Every new SKU ships on the unified OS core from the first production run. No line-specific forks after Q2.",
     "Owner · Platform VP"),
    ("02", "Measure the home.",
     "Telemetry is the product, not an add-on. Every feature must ship with the metric that proves it worked.",
     "Owner · Data lead"),
    ("03", "Write plainly.",
     "Release notes, app copy, service sheets — all authored in the Feinschliff voice. Short sentences. Concrete nouns.",
     "Owner · Content lead"),
    ("04", "Ship weekly.",
     "Every squad cuts a release every week; anything that can't be weekly is a platform bug to be retired.",
     "Owner · Eng director"),
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["ink"])
    paint_chrome(layout, variant="dark", pgmeta=PGMETA)

    # ─── Act-head: kicker + action_title, top-left ───
    # Matches the HTML's `.act-head` block positioned around y=140-400.
    add_rule(layout, 100, 180, width_px=80, height_px=4, color=T.ACCENT)
    add_text_placeholder(
        layout, idx=10, name="Kicker", ph_type="body",
        x_px=100, y_px=224, w_px=1720, h_px=30,
        prompt_text=EYEBROW_PROMPT,
        size_px=T.SIZE_PX["eyebrow"], font=T.FONT_MONO,
        color=T.ACCENT, uppercase=True, tracking_em=0.12,
    )
    add_text_placeholder(
        layout, idx=0, name="Action Title", ph_type="title",
        x_px=100, y_px=272, w_px=1720, h_px=160,
        prompt_text="Three things to remember: platform first, measure the home, write plainly.",
        size_px=T.SIZE_PX["slide_title"], weight="bold",
        color=T.WHITE, tracking_em=-0.015, line_height=1.15,
    )

    # ─── Takeaway columns: 4W + 3*gap = 1720 → col_w = 412 ───
    # We always emit all 4 slots (matches catalog placeholder_map idx 20–35).
    # Users fill 2–4; unfilled columns stay as prompt text in the layout
    # and are simply not instantiated on slides that use fewer cards.
    col_w = 412
    gap = 24
    x0 = 100
    y0 = 500

    for i, (num, head, body, owner) in enumerate(_CARDS):
        x = x0 + i * (col_w + gap)
        idx_base = 20 + i * 4

        # Subtle orange rule above each column header.
        add_rule(layout, x, y0, width_px=48, height_px=3, color=T.ACCENT)

        # Counter — mono orange, e.g. "01".
        add_text_placeholder(
            layout, idx=idx_base, name=f"Card {i+1} Counter", ph_type="body",
            x_px=x, y_px=y0 + 20, w_px=col_w, h_px=30,
            prompt_text=num,
            size_px=T.SIZE_PX["col_num"], font=T.FONT_MONO,
            color=T.ACCENT, uppercase=True, tracking_em=0.12,
        )
        # Heading — white medium, up to 2 lines.
        add_text_placeholder(
            layout, idx=idx_base + 1, name=f"Card {i+1} Heading", ph_type="body",
            x_px=x, y_px=y0 + 64, w_px=col_w, h_px=100,
            prompt_text=head,
            size_px=T.SIZE_PX["col_title"], weight="medium",
            color=T.WHITE, tracking_em=-0.012, line_height=1.15,
        )
        # Body — silver, larger block.
        add_text_placeholder(
            layout, idx=idx_base + 2, name=f"Card {i+1} Body", ph_type="body",
            x_px=x, y_px=y0 + 180, w_px=col_w, h_px=280,
            prompt_text=body,
            size_px=T.SIZE_PX["col_body"],
            color=T.SILVER, line_height=1.5,
        )
        # Owner — optional mono caption, bottom of column.
        add_text_placeholder(
            layout, idx=idx_base + 3, name=f"Card {i+1} Owner", ph_type="body",
            x_px=x, y_px=y0 + 480, w_px=col_w, h_px=24,
            prompt_text=owner,
            size_px=14, font=T.FONT_MONO,
            color=T.STEEL, uppercase=True, tracking_em=0.12,
        )
