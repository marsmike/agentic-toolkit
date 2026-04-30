"""Feinschliff · KPI Grid — 3 KPI cells with hairlines (HTML 07 adaption).

The PPTX renderer ships 4 cells. For the SVG proof-of-concept we fill the
demo with a 3-KPI variant to exercise unit/delta runs without committing
to 4-column geometry. Layout logic still handles N cells.
"""
from __future__ import annotations

from xml.etree.ElementTree import Element

import theme as T
from components import (
    canvas_background,
    kpi_delta,
    kpi_key,
    kpi_value_unit,
)
from layouts._shared import content_header, paint_chrome
from primitives import rect

NAME = "Feinschliff · KPI Grid"
ID = "kpi_grid"

EYEBROW = "KPI · Q1 2026"
TITLE = "Performance at a glance."

KPIS = [
    ("62",  "k",  "METRIC ONE",   "+3% YoY"),
    ("100", "%",  "METRIC TWO",   "+2pp"),
    ("4.8", "★",  "METRIC THREE", "stable"),
]


def build(root: Element) -> None:
    canvas_background(root, fill=T.HEX["white"])
    paint_chrome(
        root,
        variant="light",
        pgmeta="KPI · 07/16",
        slide_num="07",
    )

    content_header(root, eyebrow=EYEBROW, title=TITLE)

    # 1720 wide / 3 cells. Cells cover the content span, with 1-px hairlines
    # top and bottom of every cell and between adjacent cells.
    total_w = 1720
    n = len(KPIS)
    kpi_w = total_w // n  # integer division is fine; remainder goes to gutter
    x0, y0, kpi_h = 100, 540, 260

    # Leftmost hairline
    rect(root, x0, y0, 1, kpi_h, fill=T.HEX["fog"])

    for i, (value, unit, key, delta) in enumerate(KPIS):
        x = x0 + i * kpi_w
        # Top + bottom hairlines on the cell span.
        rect(root, x, y0, kpi_w, 1, fill=T.HEX["fog"])
        rect(root, x, y0 + kpi_h - 1, kpi_w, 1, fill=T.HEX["fog"])
        # Right hairline (closes each cell; final one closes the grid).
        rect(root, x + kpi_w, y0, 1, kpi_h, fill=T.HEX["fog"])

        # Value + unit in one text run (value-light + unit-graphite).
        kpi_value_unit(root, x + 40, y0 + 36, value, unit)

        # Key (mono uppercase graphite) + delta (mono accent-hover).
        kpi_key(root, x + 40, y0 + 190, key)
        kpi_delta(root, x + 40, y0 + 220, delta)
