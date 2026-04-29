"""Slide chrome — logo, page-meta, footer, slide-number.

Chrome lives on the **master** so every layout / slide inherits it for free.
Only the pgmeta text and the slide-number value change per slide; those are
wired as placeholders.
"""
from __future__ import annotations

from pathlib import Path

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu
from lxml import etree
from pptx.oxml.ns import qn

import theme as T
from geometry import px, pt_from_px, LOGO_X_PX, LOGO_Y_PX, LOGO_H_PX
from components.primitives import add_text, _shapes

ASSETS = Path(__file__).resolve().parent.parent / "assets"

WORDMARK_TEXT = "Feinschliff"


def _sp_name(sp) -> str:
    nvSpPr = sp.find(qn("p:nvSpPr"))
    if nvSpPr is not None:
        cNvPr = nvSpPr.find(qn("p:cNvPr"))
        if cNvPr is not None:
            return cNvPr.get("name", "")
    return ""


def add_logo(target, *, variant: str = "light"):
    """Place the Feinschliff wordmark (text) at top-left.

    Variant 'light' = ink wordmark on light bg, 'dark' = white wordmark on
    dark bg. Feinschliff ships without raster logos — the wordmark is rendered
    in the display font directly so the brand pack stays OSS-only.
    """
    color = T.WHITE if variant == "dark" else T.INK
    return add_text(
        target,
        LOGO_X_PX, LOGO_Y_PX,
        # Generous width — wordmark is short, the box is just a layout slot.
        220, max(LOGO_H_PX, 28),
        WORDMARK_TEXT,
        size_px=22,
        font=T.FONT_DISPLAY + " Medium",
        color=color,
        tracking_em=-0.01,
    )


def add_pgmeta(master_or_slide, text: str = "Feinschliff Design System · 2026", *, color=T.BLACK):
    """Page-meta stamp at top-right."""
    return add_text(
        master_or_slide, 1420, 70, 400, 30, text,
        size_px=T.SIZE_PX["pgmeta"], font=T.FONT_MONO,
        color=color, align=PP_ALIGN.RIGHT, uppercase=True, tracking_em=0.1,
    )


def add_footer_left(master_or_slide, text: str = "Jan 2026 · Internal", *, color=T.BLACK):
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


def paint_chrome(target, *, variant: str = "light",
                 pgmeta: str = "Feinschliff Design System · 2026",
                 footer_left: str = "Jan 2026 · Internal",
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


