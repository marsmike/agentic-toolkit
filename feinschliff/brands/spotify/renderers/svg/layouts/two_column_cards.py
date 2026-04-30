"""Feinschliff · 2-Column Cards — two paper-filled cards, each a labelled column (HTML 08)."""
from __future__ import annotations

from xml.etree.ElementTree import Element

import theme as T
from components import canvas_background, column_label_stack
from layouts._shared import content_header, paint_chrome
from primitives import rect

NAME = "Feinschliff · 2-Column Cards"
ID = "two_column_cards"

EYEBROW = "COMPARISON"
TITLE = "Two lenses on the same data."

CARDS = [
    (
        "01 · COLUMN ONE",
        "First lens label",
        "Body copy describing the first column,\nover two or three short lines.",
    ),
    (
        "02 · COLUMN TWO",
        "Second lens label",
        "Body copy describing the second column,\nover two or three short lines\nfor balance.",
    ),
]


def build(root: Element) -> None:
    canvas_background(root, fill=T.HEX["white"])
    paint_chrome(
        root,
        variant="light",
        pgmeta="Layout · 08/16",
        slide_num="08",
    )

    content_header(root, eyebrow=EYEBROW, title=TITLE)

    # 2 columns, 1720 content wide, gap 48 → W = (1720 - 48) / 2 = 836
    col_w = 836
    gap = 48
    x0 = 100
    y0 = 500
    h = 500

    for i, (num, t, body) in enumerate(CARDS):
        x = x0 + i * (col_w + gap)
        rect(root, x, y0, col_w, h, fill=T.HEX["paper"])
        column_label_stack(
            root, x + 40, y0 + 40,
            number=num,
            title_text=t,
            body_text=body,
        )
