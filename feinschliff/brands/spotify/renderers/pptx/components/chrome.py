"""Slide chrome — logo, page-meta, footer, slide-number.

Chrome lives on the **master** so every layout / slide inherits it for free.
Only the pgmeta text and the slide-number value change per slide; those are
wired as placeholders.

Spotify's canvas is dark by default — `paint_chrome` keeps the existing
`variant="light" | "dark"` signature for parity with other brand packs, but
both variants render the chrome with light ink because the brand-defining
canvas (`T.HEX["white"]`) is the Spotify true-black surface.
"""
from __future__ import annotations

from pathlib import Path

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu
from pptx.dml.color import RGBColor
from lxml import etree
from pptx.oxml.ns import qn

import theme as T
from geometry import px, pt_from_px, LOGO_X_PX, LOGO_Y_PX, LOGO_H_PX
from components.primitives import add_text, _shapes

ASSETS = Path(__file__).resolve().parent.parent / "assets"

WORDMARK_TEXT = "Spotify"

# Generic equalizer glyph — three vertical rounded bars of varying heights,
# evenly spaced inside an implicit circle. Reads as "sound / audio waveform"
# at small sizes. NOT the licensed Spotify wordmark or the official three-arc
# sound-wave mark; this is a brand-neutral equalizer abstraction that evokes
# music playback the same way Spotify's iconography does.
#
# Geometry (viewBox 0..100, origin top-left):
#   3 bars, 14px wide, 8px gap, baseline-aligned at y=80. Heights vary to
#   suggest motion — short / tall / medium reads as a waveform snapshot.
_EQ_BARS = [
    # (x, y, w, h) within 100x100 viewBox
    (24, 38, 14, 42),  # left  bar
    (43, 22, 14, 58),  # mid   bar — tallest
    (62, 50, 14, 30),  # right bar — shortest
]
_EQ_VB_SIZE = 100
_EQ_PX = 26  # render size on the slide


def _sp_name(sp) -> str:
    nvSpPr = sp.find(qn("p:nvSpPr"))
    if nvSpPr is not None:
        cNvPr = nvSpPr.find(qn("p:cNvPr"))
        if cNvPr is not None:
            return cNvPr.get("name", "")
    return ""


def _add_equalizer(target, *, x_px: float, y_px: float, size_px: float, color: RGBColor):
    """Draw the generic equalizer glyph: three pill-shaped vertical bars.

    Each bar is a ROUNDED_RECTANGLE with the corner adjustment cranked to its
    max so the bar reads as a fully rounded pill — echoes Spotify's pill-button
    geometry without copying the licensed sound-wave mark.
    """
    s = size_px / _EQ_VB_SIZE
    for (bx, by, bw, bh) in _EQ_BARS:
        shape = _shapes(target).add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            px(x_px + bx * s),
            px(y_px + by * s),
            px(bw * s),
            px(bh * s),
        )
        # Crank the corner-radius adjustment to ~50% of half-width = pill.
        # python-pptx exposes adjustments as a sequence of floats 0..1.
        try:
            shape.adjustments[0] = 0.5
        except (IndexError, AttributeError):
            pass
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        shape.shadow.inherit = False


def add_logo(target, *, variant: str = "dark"):
    """Place the Spotify lockup (equalizer glyph + wordmark) at top-left.

    Variant 'dark' (default) = light ink on the dark Spotify canvas.
    Variant 'light' = same light ink, kept for API parity. Wordmark uses the
    geometric sans (Spotify Circular / Inter) at weight 700 with tight tracking
    — sentence-case, no uppercase.

    Spotify reads more naturally with `variant="dark"`; the brand pack defaults
    to it everywhere chrome is painted.
    """
    color = T.BLACK  # T.BLACK is the inverted "ink on canvas" colour = near-white
    _add_equalizer(target, x_px=LOGO_X_PX + 2, y_px=LOGO_Y_PX + 4, size_px=_EQ_PX, color=color)
    return add_text(
        target,
        LOGO_X_PX + _EQ_PX + 14, LOGO_Y_PX + 2,
        260, max(LOGO_H_PX, 28),
        WORDMARK_TEXT,
        size_px=24,
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color,
        tracking_em=-0.02,
    )


def add_pgmeta(master_or_slide, text: str = "Spotify · Showcase 2026", *, color=T.BLACK):
    """Page-meta stamp at top-right."""
    return add_text(
        master_or_slide, 1420, 70, 400, 30, text,
        size_px=T.SIZE_PX["pgmeta"], font=T.FONT_MONO,
        color=color, align=PP_ALIGN.RIGHT, tracking_em=0.05,
    )


def add_footer_left(master_or_slide, text: str = "Jan 2026 · Showcase", *, color=T.BLACK):
    """Footer-left — date / classification."""
    return add_text(
        master_or_slide, 100, 1030, 600, 24, text,
        size_px=T.SIZE_PX["footer"], font=T.FONT_MONO,
        color=color, uppercase=True, tracking_em=0.1,
    )


def add_footer_right(master_or_slide, text: str, *, color=T.BLACK):
    """Footer-right — slide number / total."""
    return add_text(
        master_or_slide, 1220, 1030, 600, 24, text,
        size_px=T.SIZE_PX["footer"], font=T.FONT_MONO,
        color=color, align=PP_ALIGN.RIGHT, uppercase=True, tracking_em=0.1,
    )


def paint_chrome(target, *, variant: str = "dark",
                 pgmeta: str = "Spotify · Showcase 2026",
                 footer_left: str = "Jan 2026 · Showcase",
                 total: int | None = None):
    """Paint full chrome (logo + pgmeta + footer) onto a layout or slide.

    The footer-right is a live slide-number field: PowerPoint auto-fills the
    current slide index. Pass `total` to render "Slide 1 / N" instead of
    "Slide 1". Spotify reads naturally with `variant="dark"` (the default) —
    the canvas is the brand-defining true-black surface.
    """
    text_color = T.BLACK  # both variants render light ink on the dark canvas
    add_logo(target, variant=variant)
    add_pgmeta(target, pgmeta, color=text_color)
    add_footer_left(target, footer_left, color=text_color)
    tb = add_footer_right(target, "Slide ", color=text_color)
    _append_slide_num_field(tb, total=total, color=text_color)


def _append_slide_num_field(tb, *, total: int | None, color):
    """Replace the text frame's runs with "Slide <fld> [/ N]" so PowerPoint
    renders the live slide number."""
    tf = tb.text_frame
    p = tf.paragraphs[0]
    for r in list(p._p):
        if r.tag in (qn("a:r"), qn("a:fld")):
            p._p.remove(r)

    def _rPr(el):
        rPr = etree.SubElement(el, qn("a:rPr"))
        rPr.set("lang", "en-US")
        rPr.set("dirty", "0")
        rPr.set("sz", str(int(T.SIZE_PX["footer"] * 0.5 * 100)))
        rPr.set("spc", str(int(T.SIZE_PX["footer"] * 0.5 * 0.1 * 100)))
        fill = etree.SubElement(rPr, qn("a:solidFill"))
        srgb = etree.SubElement(fill, qn("a:srgbClr"))
        srgb.set("val", "{:02X}{:02X}{:02X}".format(*color))
        latin = etree.SubElement(rPr, qn("a:latin"))
        latin.set("typeface", T.FONT_MONO)
        return rPr

    # "Slide "
    r1 = etree.SubElement(p._p, qn("a:r"))
    _rPr(r1)
    t1 = etree.SubElement(r1, qn("a:t"))
    t1.text = "SLIDE "

    # <fld type="slidenum">1</fld>
    fld = etree.SubElement(p._p, qn("a:fld"))
    fld.set("id", "{A1B2C3D4-E5F6-4890-ABCD-EF0123456789}")
    fld.set("type", "slidenum")
    _rPr(fld)
    tF = etree.SubElement(fld, qn("a:t"))
    tF.text = "1"

    if total is not None:
        r2 = etree.SubElement(p._p, qn("a:r"))
        _rPr(r2)
        t2 = etree.SubElement(r2, qn("a:t"))
        t2.text = f" / {total:02d}"
