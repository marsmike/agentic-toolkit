"""Feinschliff · Title · Accent — accent-bg title slide (HTML ref: slide 01).

Bottom-left stacked rule, eyebrow, big Noto Sans Light display title.
"""
from __future__ import annotations

from xml.etree.ElementTree import Element

import theme as T
from components import canvas_background, rule, eyebrow, title
from layouts._shared import paint_chrome

NAME = "Feinschliff · Title · Accent"
ID = "title_orange"

# Demo content.
EYEBROW = "LAYOUT 01 · TITLE"
TITLE = "Feinschliff\nshowcase deck."


def build(root: Element) -> None:
    canvas_background(root, fill=T.HEX["accent"])
    paint_chrome(
        root,
        variant="dark",                       # white chrome on accent
        pgmeta="Title · 01/16",
        slide_num="01",
    )

    # HTML opener-stack maths (mirrors PPTX title_orange.py):
    #   display = 160 px × 2 lines × 0.95 lh = 304 → top = 1080 - 180 - 304 = 596
    #   eyebrow gap 32 → eyebrow top = 542
    #   rule gap 40, rule 4 → rule top = 498
    rule(root, 100, 498, width=80, height=4, color=T.HEX["black"])
    eyebrow(root, 100, 542, EYEBROW)
    title(
        root, 100, 596, TITLE,
        size_px=T.SIZE_PX["display"], weight="light",
        tracking_em=-0.035, line_height=0.95,
    )
