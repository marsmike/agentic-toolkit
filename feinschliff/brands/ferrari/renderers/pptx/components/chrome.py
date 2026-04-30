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

WORDMARK_TEXT = "FERRARI"

# Heraldic-shield glyph, viewBox 0..100. Generic shield silhouette: a rounded-top
# rectangle that tapers to a V at the bottom. Drawn as a 7-point freeform polygon
# (top-left, top-right, mid-right, bottom-right-corner, bottom-tip-V,
# bottom-left-corner, mid-left). Filled in Modena yellow with a Rosso Corsa stroke.
#
# This is purposefully a GENERIC heraldic shield abstraction — it does NOT
# reproduce the Cavallino Rampante (prancing horse), which is a famously
# protected Ferrari trademark. No interior glyph beyond an optional thin
# vertical bar / "F" hint is drawn. If callers want a richer mark they can
# replace this glyph; the public chrome surface stays the same.
_SHIELD_POINTS = [
    (12, 8),   # top-left (just below the rounded corner)
    (88, 8),   # top-right
    (92, 32),  # mid-right (widest point of the shield)
    (88, 62),  # right-bottom shoulder
    (50, 96),  # bottom-tip V
    (12, 62),  # left-bottom shoulder
    (8,  32),  # mid-left
]
_SHIELD_VB_SIZE = 100
_SHIELD_PX = 22  # Render size on the slide.


def _sp_name(sp) -> str:
    nvSpPr = sp.find(qn("p:nvSpPr"))
    if nvSpPr is not None:
        cNvPr = nvSpPr.find(qn("p:cNvPr"))
        if cNvPr is not None:
            return cNvPr.get("name", "")
    return ""


def _add_shield(target, *, x_px: float, y_px: float, size_px: float,
                fill_color: RGBColor, stroke_color: RGBColor):
    """Draw the heraldic-shield glyph as a vector freeform shape.

    The shield is a 7-point polygon — rounded-top rectangle tapering to a V at
    the bottom — filled in `fill_color` with a thin `stroke_color` border. It
    is a generic heraldic abstraction, not the Cavallino Rampante.
    """
    s = size_px / _SHIELD_VB_SIZE
    pts = [(x_px + p[0] * s, y_px + p[1] * s) for p in _SHIELD_POINTS]
    head, *tail = pts
    builder = _shapes(target).build_freeform(px(head[0]), px(head[1]), scale=1)
    builder.add_line_segments([(px(x), px(y)) for x, y in tail], close=True)
    shape = builder.convert_to_shape()
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill_color
    shape.line.color.rgb = stroke_color
    shape.line.width = Emu(int(0.75 * 12700))  # ~0.75pt hairline border
    return shape


def add_logo(target, *, variant: str = "light"):
    """Place the Ferrari lockup (heraldic-shield glyph + wordmark) at top-left.

    Variant 'light' = dark ink wordmark on cream canvas; 'dark' = warm cream
    wordmark on the cinematic black canvas. The shield always renders in
    Modena yellow with a Rosso Corsa hairline border — high recognition on
    either canvas. Wordmark uses the display serif at weight bold, uppercase
    with open tracking — Ferrari's classical lockup register.
    """
    text_color = T.WHITE if variant == "dark" else T.INK
    _add_shield(
        target,
        x_px=LOGO_X_PX + 2, y_px=LOGO_Y_PX + 6,
        size_px=_SHIELD_PX,
        fill_color=T.HIGHLIGHT,      # Modena yellow
        stroke_color=T.ACCENT,       # Rosso Corsa border
    )
    return add_text(
        target,
        LOGO_X_PX + _SHIELD_PX + 14, LOGO_Y_PX + 4,
        320, max(LOGO_H_PX, 28),
        WORDMARK_TEXT,
        size_px=22,
        weight="bold",
        font=T.FONT_DISPLAY,
        color=text_color,
        uppercase=True,
        tracking_em=0.15,
    )


def add_pgmeta(master_or_slide, text: str = "Ferrari · Showcase 2026", *, color=T.BLACK):
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
                 pgmeta: str = "Ferrari · Showcase 2026",
                 footer_left: str = "Jan 2026 · Showcase",
                 total: int | None = None):
    """Paint full chrome (logo + pgmeta + footer) onto a layout or slide.

    The footer-right is a live slide-number field: PowerPoint auto-fills the
    current slide index. Pass `total` to render "Slide 1 / N" instead of
    "Slide 1".
    """
    text_color = T.WHITE if variant == "dark" else T.BLACK
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


