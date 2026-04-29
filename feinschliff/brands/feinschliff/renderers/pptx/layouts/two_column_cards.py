"""Feinschliff · 2-Column Cards — two paper-filled cards, each a labelled column (HTML 08)."""
from __future__ import annotations

import theme as T
from components import (
    add_rect, paint_chrome,
    set_layout_background, set_layout_name,
)
from layouts._shared import content_header, column_placeholders

NAME = "Feinschliff · 2-Column Cards"

CARDS = [
    ("01 · Consumer",
     "Products designed around daily cooking, not corner-case specs.",
     "Ship features users actually touch — induction presets, one-pot modes, and a quieter dishwasher."),
    ("02 · Platform",
     "A shared software backbone across every product we build.",
     "One OS means one update path, one data contract, and one place to measure real-world usage."),
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])
    paint_chrome(layout, variant="light", pgmeta="Layout · 2 contents")

    content_header(layout, eyebrow="Two columns", title="Two halves, one frame.")

    # 2 columns, 1720 wide, gap 48 → 2W + 48 = 1720 → W = 836
    col_w = 836
    gap = 48
    x0 = 100
    y0 = 500
    h = 500

    for i, (num, t, body) in enumerate(CARDS):
        x = x0 + i * (col_w + gap)
        add_rect(layout, x, y0, col_w, h, fill=T.PAPER)
        column_placeholders(
            layout, idx_base=20 + i * 3, x=x + 40, y=y0 + 40,
            w=col_w - 80, prompt_num=num, prompt_title=t, prompt_body=body,
        )
