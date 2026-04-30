"""Feinschliff · Components Showcase — UI-kit reference slide (HTML 14).

Two paper-filled panels side by side:
  - Left: Buttons (primary, default, ghost) + Chips (4 tag variants)
  - Right: Rules (section, emphasis, hairline)

This slide is reference rather than content — the buttons / chips / rules
are fixed decoration showing the Feinschliff UI kit. Only the top eyebrow + title
are placeholders.
"""
from __future__ import annotations

import theme as T
from components import (
    add_rect, add_line, add_text, add_text_placeholder,
    add_button, add_chip, paint_chrome,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header

NAME = "Feinschliff · Components Showcase"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])
    paint_chrome(layout, variant="light", pgmeta="UI kit")

    content_header(
        layout,
        eyebrow="UI library preview",
        title="Flat, sharp, quiet components.",
    )

    # Two panels, 48px gap → col width = (1720 - 48) / 2 = 836
    panel_w = 836
    panel_h = 500
    gap = 48
    y0 = 500
    x_left = 100
    x_right = x_left + panel_w + gap

    _left_panel(layout, x_left, y0, panel_w, panel_h)
    _right_panel(layout, x_right, y0, panel_w, panel_h)


# ─── Left panel: Buttons + Chips ──────────────────────────────────────────
def _left_panel(layout, x: float, y: float, w: float, h: float):
    """Paper card with a row of buttons above a row of chips."""
    add_rect(layout, x, y, w, h, fill=T.PAPER)

    pad = 48
    inner_x = x + pad

    # "Buttons" eyebrow
    _panel_label(layout, inner_x, y + pad, "Buttons")

    # Three buttons — primary / default / ghost
    btn_y = y + pad + 60
    add_button(layout, inner_x,        btn_y, "Primary", variant="primary", w_px=200, h_px=64)
    add_button(layout, inner_x + 220,  btn_y, "Default", variant="dark",    w_px=200, h_px=64)
    add_button(layout, inner_x + 440,  btn_y, "Ghost",   variant="ghost",   w_px=170, h_px=64)

    # "Tags" eyebrow (second row)
    tags_label_y = y + pad + 180
    _panel_label(layout, inner_x, tags_label_y, "Tags")

    # Four chips
    chip_y = tags_label_y + 50
    add_chip(layout, inner_x,        chip_y, "Production", variant="ink",    w_px=175)
    add_chip(layout, inner_x + 190,  chip_y, "Featured",   variant="orange", w_px=140)
    add_chip(layout, inner_x + 345,  chip_y, "Beta",       variant="amber",  w_px=90)
    add_chip(layout, inner_x + 450,  chip_y, "Archived",   variant="ghost",  w_px=150)


# ─── Right panel: Rules ───────────────────────────────────────────────────
def _right_panel(layout, x: float, y: float, w: float, h: float):
    """Paper card with three rule variants + mono captions."""
    add_rect(layout, x, y, w, h, fill=T.PAPER)

    pad = 48
    inner_x = x + pad

    _panel_label(layout, inner_x, y + pad, "Rules")

    # Three rules, stacked vertically with mono captions
    rows = [
        (56,  1, T.INK,    "Section · 56 × 1 · ink"),
        (80,  4, T.ACCENT, "Emphasis · 80 × 4 · orange"),
        (w - 2 * pad, 1, T.FOG, "Hairline · width × 1 · fog"),
    ]
    row_y = y + pad + 80
    for rule_w, rule_h, rule_color, caption in rows:
        add_line(layout, inner_x, row_y, rule_w, rule_h, rule_color)
        add_text(
            layout, inner_x, row_y + 14, w - 2 * pad, 24, caption,
            size_px=14, weight="bold", font=T.FONT_DISPLAY,
            color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
        )
        row_y += 100


def _panel_label(layout, x: float, y: float, text: str):
    """Small mono uppercase label used above each component row."""
    add_text(
        layout, x, y, 400, 24, text,
        size_px=14, weight="bold", font=T.FONT_DISPLAY,
        color=T.BLACK, uppercase=True, tracking_em=0.1,
    )
