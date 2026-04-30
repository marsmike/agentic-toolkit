"""Canvas geometry — 1920 × 1080 CSS px.

SVG uses CSS px natively, so there's no EMU conversion layer. This module
exists so layouts can import named anchor positions (logo, pgmeta, footer)
symbolically rather than by magic numbers, mirroring the PPTX renderer's
`geometry.py` module structure.
"""
from __future__ import annotations

CANVAS_W = 1920
CANVAS_H = 1080

# Named positions mirroring the HTML CSS and the PPTX renderer.
PAD_X = 100
PAD_Y_TOP = 100
PAD_Y_BOTTOM = 80

LOGO_X = 100
LOGO_Y = 60
LOGO_H = 40  # matches the 40 px logo height in the deck

PGMETA_X = 1820  # right-anchored (right edge at 1820 = 1920 - 100)
PGMETA_Y = 70

FOOTER_Y = 1030  # bottom: 50, so y = 1080 - 50

VIEWBOX = f"0 0 {CANVAS_W} {CANVAS_H}"
