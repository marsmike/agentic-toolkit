"""Feinschliff · Tech Radar · Full Bleed — full-bleed image of a tech-radar SVG/PNG.

The radar SVG already carries its own slide chrome (logo, eyebrow, title,
footer) — see ``tech-radar/engine/templates/radar.svg.j2``. This Feinschliff
layout therefore paints NOTHING beyond a single full-canvas image
placeholder. Generate the PNG first via ``radar-engine render --view <view>``
then drop it into the placeholder.
"""
from __future__ import annotations

import theme as T
from components import set_layout_background, set_layout_name
from components.media import add_image_placeholder

NAME = "Feinschliff · Tech Radar · Full Bleed"


def build(layout):
    set_layout_name(layout, NAME)
    set_layout_background(layout, T.HEX["white"])
    # Single full-bleed image placeholder. The radar SVG renders its own
    # logo/eyebrow/title/footer, so no chrome is painted here.
    add_image_placeholder(
        layout, 0, 0, 1920, 1080, label="Drop tech-radar PNG (radar-engine render)",
    )
