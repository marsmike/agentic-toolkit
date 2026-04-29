"""Geometry helpers — convert the HTML deck's pixel coordinates to PowerPoint EMUs.

The Feinschliff showcase deck is authored at 1920 × 1080 CSS pixels.
PowerPoint widescreen slides are 13.333" × 7.5" (16:9).
At 144 DPI: 1920 px / 144 = 13.333", 1080 px / 144 = 7.5".
So 1 CSS pixel = 1/144 inch = 6 350 EMU (English Metric Units).
"""
from pptx.util import Emu, Pt

EMU_PER_PX = 6350  # 1/144 inch in EMU
SLIDE_W_PX = 1920
SLIDE_H_PX = 1080


def px(n: float) -> Emu:
    """Convert CSS pixels to EMU."""
    return Emu(int(round(n * EMU_PER_PX)))


def pt_from_px(n: float) -> Pt:
    """Convert HTML-deck pixels to typographic points.

    The HTML deck is authored at 1920×1080 CSS px mapped to 13.333"×7.5".
    At this mapping, 1 CSS px = 1/144 inch, and 1 pt = 1/72 inch, so:
        1 CSS px = 0.5 pt.

    (This is NOT the standard CSS 96-DPI conversion — it matches the deck's
    actual physical mapping so 160 CSS px renders at the same inch-height in
    PowerPoint as it does in the browser at 1920-wide viewport.)
    """
    return Pt(n * 0.5)


# Named positions mirroring the HTML CSS
PAD_X_PX = 100
PAD_Y_TOP_PX = 100
PAD_Y_BOTTOM_PX = 80

LOGO_X_PX = 100
LOGO_Y_PX = 60
LOGO_H_PX = 40  # Matches the 40px logo height in the deck

PGMETA_X_PX = 100  # right-anchored, computed from right edge
PGMETA_Y_PX = 70

FOOTER_Y_PX = 1030  # bottom: 50, so y = 1080 - 50
