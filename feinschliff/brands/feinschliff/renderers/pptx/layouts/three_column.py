"""Feinschliff · 3-Column — three side-by-side labelled columns, no card fills (HTML 09)."""
from __future__ import annotations

import theme as T
from components import paint_chrome, set_layout_background, set_layout_name
from layouts._shared import content_header, column_placeholders

NAME = "Feinschliff · 3-Column"

CARDS = [
    ("01", "Consumer.",
     "Brand A, Brand B, Brand C, Brand D — placeholder column copy."),
    ("02", "Commercial.",
     "Products engineered for the commercial sector — hotels, kitchens, laundries, retail."),
    ("03", "Platform.",
     "Platform — the software layer shared across all of it."),
]


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])
    paint_chrome(layout, variant="light", pgmeta="Layout · 3 contents")

    content_header(layout, eyebrow="Three pillars", title="Consumer, commercial, platform.")

    # 3W + 2*48 = 1720 → W = 541
    col_w = 541
    gap = 48
    x0 = 100
    y0 = 500
    for i, (num, t, body) in enumerate(CARDS):
        x = x0 + i * (col_w + gap)
        column_placeholders(
            layout, idx_base=20 + i * 3, x=x, y=y0,
            w=col_w, prompt_num=num, prompt_title=t, prompt_body=body,
        )
