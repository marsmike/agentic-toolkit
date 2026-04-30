"""BMW slide chrome — logo, page-meta, footer, slide-number, M-stripe, chevron-link.

Chrome lives on the **master** so every layout / slide inherits it for free.
Only the pgmeta text and the slide-number value change per slide; those are
wired as placeholders.

Three primitives in this module are BMW-specific brand signatures (DESIGN.md):

  * `add_m_stripe`     — the 4px tricolor (M Blue Light → M Blue Dark → M Red).
                         Reserved meaning: chapter dividers / motorsport
                         contexts only. Not decoration.
  * `add_chevron_link` — "LEARN MORE ›"-style inline CTA. UPPERCASE 700 weight,
                         label-uppercase tracking, › terminator.
  * `_add_quartered_disc` — generic pie-chart abstraction of a quartered
                         roundel. NOT the licensed BMW roundel.
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
from components.primitives import add_text, add_rect, _shapes

ASSETS = Path(__file__).resolve().parent.parent / "assets"

WORDMARK_TEXT = "BMW"

# Quartered-disc glyph — generic pie-chart geometry, four equal pie wedges with
# two opposite quadrants filled in the brand accent and two left in the
# canvas/paper colour. Abstraction of a quartered roundel, NOT the licensed
# BMW mark.
_GLYPH_PX = 28


def _sp_name(sp) -> str:
    nvSpPr = sp.find(qn("p:nvSpPr"))
    if nvSpPr is not None:
        cNvPr = nvSpPr.find(qn("p:cNvPr"))
        if cNvPr is not None:
            return cNvPr.get("name", "")
    return ""


def _set_pie_rotation(shape, rotation_deg: float):
    """Rotate a shape via spPr/xfrm/@rot (60000ths of a degree)."""
    spPr = shape._element.spPr
    xfrm = spPr.find(qn("a:xfrm"))
    if xfrm is None:
        shape.left = shape.left
        xfrm = spPr.find(qn("a:xfrm"))
    if xfrm is not None:
        xfrm.set("rot", str(int(rotation_deg * 60000) % (360 * 60000)))


def _add_quartered_disc(target, *, x_px: float, y_px: float, size_px: float,
                        accent: RGBColor, paper: RGBColor, ring: RGBColor | None = None):
    """Generic pie-chart roundel — four 90° wedges in alternating 2×2 colour pattern.

    NOT the licensed BMW roundel. Wedges:
      * NW + SE → accent (brand blue)
      * NE + SW → paper (white)
    Optional outer ring gives the disc a defined edge.
    """
    s = _shapes(target)
    quadrants = [
        (270, accent),   # NW
        (0,   paper),    # NE
        (90,  accent),   # SE
        (180, paper),    # SW
    ]
    for rot, fill in quadrants:
        shape = s.add_shape(
            MSO_SHAPE.PIE,
            px(x_px), px(y_px), px(size_px), px(size_px),
        )
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill
        shape.line.fill.background()
        shape.shadow.inherit = False
        _set_pie_rotation(shape, rot)

    if ring is not None:
        outline = s.add_shape(
            MSO_SHAPE.OVAL,
            px(x_px), px(y_px), px(size_px), px(size_px),
        )
        outline.fill.background()
        outline.line.color.rgb = ring
        outline.line.width = px(1)
        outline.shadow.inherit = False


# ─── BMW-signature primitives (per DESIGN.md) ──────────────────────────────

def add_m_stripe(target, *, x_px: float, y_px: float, w_px: float,
                 h_px: float | None = None):
    """Draw the M tricolor stripe — three equal-width segments stacked
    horizontally: M Blue Light → M Blue Dark → M Red.

    Per BMW DESIGN.md: 4px tall, fixed across breakpoints, reserved for
    chapter dividers / motorsport contexts. Don't use as decoration.
    """
    h = h_px or T.SECTION_MARKER.get("height-px", 4)
    seg_w = w_px / 3
    stops = (T.M_BLUE_LIGHT, T.M_BLUE_DARK, T.M_RED)
    for i, color in enumerate(stops):
        add_rect(
            target,
            x_px + i * seg_w, y_px,
            seg_w, h,
            fill=color,
        )


def add_chevron_link(target, x_px: float, y_px: float, w_px: float, h_px: float,
                     text: str = "LEARN MORE", *, color: RGBColor | None = None):
    """LEARN MORE ›-style inline CTA. UPPERCASE 13px / 700 / 1.5px tracking,
    › terminator. Iconic BMW corporate inline-link treatment per DESIGN.md.
    """
    color = color if color is not None else T.INK
    label = f"{text.upper()} ›"
    return add_text(
        target, x_px, y_px, w_px, h_px,
        label,
        size_px=T.SIZE_PX["chip"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color,
        uppercase=False,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.115)),
    )


def add_hairline(target, x_px: float, y_px: float, w_px: float, *,
                 color: RGBColor | None = None, weight_px: int = 1):
    """1px hairline divider — BMW DESIGN.md `hairline` (#E6E6E6).
    Used above footers, between table rows, around configurator tiles."""
    return add_rect(
        target, x_px, y_px, w_px, weight_px,
        fill=color if color is not None else T.FOG,
    )


# ─── Logo + chrome ─────────────────────────────────────────────────────────

def add_logo(target, *, variant: str = "light"):
    """BMW lockup (quartered-disc + wordmark) at top-left.

    'light' = ink mark on white canvas (default — BMW DESIGN.md says canvas
    is the dominant page surface). 'dark' = white-keyed mark on surface-dark
    hero band.
    """
    if variant == "dark":
        text_color = T.WHITE
        accent = T.WHITE
        paper = T.SURFACE_DARK
        ring = T.WHITE
    else:
        text_color = T.INK
        accent = T.ACCENT
        paper = T.WHITE
        ring = T.INK

    _add_quartered_disc(
        target,
        x_px=LOGO_X_PX,
        y_px=LOGO_Y_PX + 2,
        size_px=_GLYPH_PX,
        accent=accent,
        paper=paper,
        ring=ring,
    )
    return add_text(
        target,
        LOGO_X_PX + _GLYPH_PX + 14, LOGO_Y_PX + 4,
        260, max(LOGO_H_PX, 28),
        WORDMARK_TEXT,
        size_px=22,
        weight="bold",
        font=T.FONT_DISPLAY,
        color=text_color,
        uppercase=True,
        tracking_em=0.05,
    )


def add_pgmeta(master_or_slide, text: str = "BMW · 2026", *, color=None):
    """Page-meta stamp at top-right. UPPERCASE 1.5px tracked label-uppercase
    style — never the mono cribbed from Claude."""
    color = color if color is not None else T.SILVER
    return add_text(
        master_or_slide, 1420, 78, 420, 28, text,
        size_px=T.SIZE_PX["pgmeta"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color, align=PP_ALIGN.RIGHT,
        uppercase=True,
        tracking_em=0.115,
    )


def add_footer_left(master_or_slide, text: str = "JAN 2026 · SHOWCASE",
                    *, color=None):
    """Footer-left — date / classification, UPPERCASE label-uppercase."""
    color = color if color is not None else T.SILVER
    return add_text(
        master_or_slide, 120, 1030, 720, 24, text,
        size_px=T.SIZE_PX["footer"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color,
        uppercase=True,
        tracking_em=0.115,
    )


def add_footer_right(master_or_slide, text: str, *, color=None):
    """Footer-right — slide number, UPPERCASE label-uppercase."""
    color = color if color is not None else T.SILVER
    return add_text(
        master_or_slide, 1100, 1030, 700, 24, text,
        size_px=T.SIZE_PX["footer"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color, align=PP_ALIGN.RIGHT,
        uppercase=True,
        tracking_em=0.115,
    )


def paint_chrome(target, *, variant: str = "light",
                 pgmeta: str = "BMW · 2026",
                 footer_left: str = "JAN 2026 · SHOWCASE",
                 total: int | None = None):
    """Paint full chrome onto a layout or slide.

    Default variant is 'light' — BMW DESIGN.md positions the white canvas as
    the dominant page surface, with dark navy hero bands as treatment.
    Layouts that paint a full-bleed dark band must opt into variant='dark'.
    """
    chrome_color = T.OFF_WHITE if variant == "dark" else T.SILVER
    add_logo(target, variant=variant)
    add_pgmeta(target, pgmeta, color=chrome_color)
    # Footer hairline — only on light chrome (dark hero bands have their own rhythm)
    if variant != "dark":
        add_hairline(target, 120, 1018, 1680, color=T.FOG)
    add_footer_left(target, footer_left, color=chrome_color)
    tb = add_footer_right(target, "SLIDE ", color=chrome_color)
    _append_slide_num_field(tb, total=total, color=chrome_color)


def _append_slide_num_field(tb, *, total: int | None, color):
    """Replace the text frame's runs with "SLIDE <fld> [/ N]" so PowerPoint
    renders the live slide number — display sans, UPPERCASE, label-uppercase."""
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
        rPr.set("b",  "1")
        # 0.115em tracking per CHIP_RULE — pptx spc unit = 1/100 of a point.
        spc_val = int(round(0.115 * (T.SIZE_PX["footer"] * 0.5) * 100))
        rPr.set("spc", str(spc_val))
        fill = etree.SubElement(rPr, qn("a:solidFill"))
        srgb = etree.SubElement(fill, qn("a:srgbClr"))
        srgb.set("val", "{:02X}{:02X}{:02X}".format(*color))
        latin = etree.SubElement(rPr, qn("a:latin"))
        latin.set("typeface", T.FONT_DISPLAY)
        return rPr

    r1 = etree.SubElement(p._p, qn("a:r"))
    _rPr(r1)
    t1 = etree.SubElement(r1, qn("a:t"))
    t1.text = "SLIDE "

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
