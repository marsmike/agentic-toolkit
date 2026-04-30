"""Slide chrome — logo, page-meta, footer, slide-number.

Chrome lives on the **master** so every layout / slide inherits it for free.
Only the pgmeta text and the slide-number value change per slide; those are
wired as placeholders.
"""
from __future__ import annotations

from pathlib import Path

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu
from pptx.dml.color import RGBColor
from lxml import etree
from pptx.oxml.ns import qn

import theme as T
from geometry import px, pt_from_px, LOGO_X_PX, LOGO_Y_PX, LOGO_H_PX
from components.primitives import add_text, _shapes

ASSETS = Path(__file__).resolve().parent.parent / "assets"

WORDMARK_TEXT = "BINANCE"

# Generic 4-segment diamond/pinwheel abstraction of the Binance brand mark —
# four right-angle triangles arranged around a hollow centre to read as a
# rotated square / 4-pointed pinwheel. Drawn as four independent triangles
# (not one freeform) so each segment renders as a crisp filled wedge.
#
# Coordinates are in a 0..100 viewBox, centred on (50, 50). The triangles
# point outward (N / E / S / W) and stop short of the centre to leave the
# characteristic hollow square.
#
# This is a brand-evoking abstraction, NOT the licensed Binance asset.
_DIAMOND_TRIANGLES = [
    [(50,  6), (78, 34), (50, 34)],   # N wedge
    [(94, 50), (66, 22), (66, 50)],   # E wedge
    [(50, 94), (22, 66), (50, 66)],   # S wedge
    [( 6, 50), (34, 78), (34, 50)],   # W wedge
]
_DIAMOND_VB_SIZE = 100
_DIAMOND_PX = 28  # Render size on the slide.


def _sp_name(sp) -> str:
    nvSpPr = sp.find(qn("p:nvSpPr"))
    if nvSpPr is not None:
        cNvPr = nvSpPr.find(qn("p:cNvPr"))
        if cNvPr is not None:
            return cNvPr.get("name", "")
    return ""


def _add_diamond(target, *, x_px: float, y_px: float, size_px: float, color: RGBColor):
    """Draw the Binance-evoking diamond glyph as four filled triangles.

    Generic 4-segment pinwheel/diamond — abstracts the four-rhombus Binance
    mark without copying the licensed geometry. Each wedge is its own shape
    so the hollow centre stays crisp at all render sizes.
    """
    s = size_px / _DIAMOND_VB_SIZE
    last_shape = None
    for tri in _DIAMOND_TRIANGLES:
        pts = [(x_px + p[0] * s, y_px + p[1] * s) for p in tri]
        head, *tail = pts
        builder = _shapes(target).build_freeform(px(head[0]), px(head[1]), scale=1)
        builder.add_line_segments([(px(x), px(y)) for x, y in tail], close=True)
        shape = builder.convert_to_shape()
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        last_shape = shape
    return last_shape


def add_logo(target, *, variant: str = "dark"):
    """Place the Binance lockup (diamond glyph + wordmark) at top-left.

    Binance reads as a dark-first brand: the canvas across the deck is the
    deep crypto-black surface, so the wordmark always renders in the
    inverted "ink-on-canvas" colour (T.BLACK = light cool white in this
    brand pack — see the inverted-palette note in tokens.json).

    The diamond glyph stays in Binance Yellow on dark variants — that's the
    brand mark. On the title-accent layout (yellow canvas) the glyph uses
    pure-black (T.INK) for contrast.

    NOTE: Binance reads most naturally with `variant='dark'`. The function
    signature is kept for parity with other brand packs.
    """
    # Wordmark text: always the inverted body-ink colour (T.BLACK = light
    # cool white in this brand pack). Spotify pattern — both variants
    # render light-on-canvas because Binance is dark-first.
    text_color = T.BLACK
    # Glyph: always Binance Yellow — that IS the brand mark. The single
    # yellow-canvas layout (title-accent) overrides this by passing
    # variant="accent" so the glyph flips to pure black for contrast.
    glyph_color = T.INK if variant == "accent" else T.ACCENT
    _add_diamond(target, x_px=LOGO_X_PX, y_px=LOGO_Y_PX + 4, size_px=_DIAMOND_PX, color=glyph_color)
    return add_text(
        target,
        LOGO_X_PX + _DIAMOND_PX + 14, LOGO_Y_PX + 4,
        320, max(LOGO_H_PX, 28),
        WORDMARK_TEXT,
        size_px=22,
        weight="medium",
        font=T.FONT_DISPLAY,
        color=text_color,
        tracking_em=0.18,
        uppercase=True,
    )


def add_pgmeta(master_or_slide, text: str = "Binance · Showcase 2026", *, color=T.BLACK):
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
                 pgmeta: str = "Binance · Showcase 2026",
                 footer_left: str = "Jan 2026 · Showcase",
                 total: int | None = None):
    """Paint full chrome (logo + pgmeta + footer) onto a layout or slide.

    The footer-right is a live slide-number field: PowerPoint auto-fills the
    current slide index. Pass `total` to render "Slide 1 / N" instead of
    "Slide 1".

    Binance reads naturally on dark canvas — `variant='dark'` is the
    primary. `variant='light'` is also dark-canvas in this brand pack
    (T.HEX['white'] is the inverted near-black canvas — Spotify pattern).
    Pass `variant='accent'` only on the yellow title-accent layout so the
    diamond glyph flips to pure black for contrast.
    """
    # Both variants render the inverted ink (T.BLACK = near-white in this
    # brand pack); Spotify pattern. The yellow title-accent canvas reads
    # white-on-yellow which mirrors Spotify's white-on-green.
    text_color = T.BLACK
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
