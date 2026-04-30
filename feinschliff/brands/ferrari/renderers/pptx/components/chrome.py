"""Ferrari slide chrome — logo, page-meta, footer, slide-number, livery band, hairline link.

Per Ferrari DESIGN.md, the canvas is near-black (`#181818`, never pure black)
and the chrome is achromatic: pure-white display type on the cinema floor,
with Rosso Corsa reserved for primary CTAs and the heraldic-shield mark.
Both `variant="light"` and `variant="dark"` render light ink — the brand-
defining surface IS the dark canvas. The heraldic shield stands in for the
Cavallino Rampante (a famously protected Ferrari trademark); "Ferrari" is
set UPPERCASE per the brand's classical lockup register with open tracking.

Three Ferrari-specific primitives live here:

  * `add_livery_band`    — full-width Rosso Corsa accent band, the
                           replacement for BMW's M-stripe role at chapter
                           dividers / major editorial breaks. Per
                           DESIGN.md `livery-band` component: 96px padding,
                           display-lg 500 -0.36px headline in white.
                           Reserved meaning — never decoration.
  * `add_uppercase_link` — UPPERCASE label-tracked button-voice link.
                           Ferrari's button typography (14px / 700 / 1.4px
                           tracking @ web → 0.1em in deck), used as inline
                           CTA. The Ferrari analog of BMW's `add_chevron_link`
                           and Spotify's `add_pill_link` — but without the
                           › terminator (DESIGN.md doesn't terminate buttons
                           with a chevron — they end at the last letter).
  * `add_hairline`       — 1px brightness-step divider on dark or light.
                           DESIGN.md `hairline` (#303030) — same hex as
                           canvas-elevated, reads as a tone-step.

Heraldic-shield glyph: a 7-point freeform polygon in Modena yellow with a
Rosso Corsa hairline border. Generic abstraction — does NOT reproduce the
licensed Cavallino Rampante (prancing horse).
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
from components.primitives import add_text, add_rect, _shapes

ASSETS = Path(__file__).resolve().parent.parent / "assets"

WORDMARK_TEXT = "FERRARI"

# Heraldic-shield glyph, viewBox 0..100. Generic shield silhouette: a rounded-top
# rectangle that tapers to a V at the bottom. Drawn as a 7-point freeform polygon
# (top-left, top-right, mid-right, bottom-right-corner, bottom-tip-V,
# bottom-left-corner, mid-left). Filled in Modena yellow with a Rosso Corsa stroke.
#
# This is purposefully a GENERIC heraldic shield abstraction — it does NOT
# reproduce the Cavallino Rampante (prancing horse), which is a famously
# protected Ferrari trademark. No interior glyph beyond the silhouette is
# drawn. If callers want a richer mark they can replace this glyph; the
# public chrome surface stays the same.
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
    shape.shadow.inherit = False
    return shape


# ─── Ferrari-signature primitives (per DESIGN.md) ──────────────────────────

def add_livery_band(target, *, x_px: float, y_px: float, w_px: float,
                    h_px: float | None = None, headline: str | None = None):
    """Full-width Rosso Corsa livery band — Ferrari DESIGN.md `livery-band`
    component. Replaces BMW's `add_m_stripe` role: a brand-signature visual at
    chapter dividers and major editorial breaks. The Rosso Corsa fill is the
    only place the brand voltage runs full-bleed; reserve for chapter
    dividers and standout livery callouts between dark editorial bands.

    `headline`, if passed, is rendered in display-lg 500 -0.36px white,
    centered in the band per DESIGN.md `livery-band` typography
    (display-lg, 96px padding).
    """
    h = h_px if h_px is not None else 8  # 8px chapter rule when no headline
    band = add_rect(target, x_px, y_px, w_px, h, fill=T.ACCENT)
    if headline:
        pad = int(T.LAYOUT.get("livery-band-pad", 96))
        add_text(
            target,
            x_px + pad, y_px + pad // 2,
            w_px - 2 * pad, h - pad,
            headline,
            size_px=T.SIZE_PX["sub"],
            weight="medium",
            font=T.FONT_DISPLAY,
            color=T.INK,
            tracking_em=-0.01,
            line_height=1.2,
            align=PP_ALIGN.LEFT,
        )
    return band


def add_uppercase_link(target, x_px: float, y_px: float, w_px: float, h_px: float,
                       text: str = "DISCOVER", *, color: RGBColor | None = None):
    """UPPERCASE button-voice inline link — Ferrari DESIGN.md `button` typography
    at link-density. 14px / 700 / 1.4px tracking (~0.1em), no terminator.

    Ferrari's button never carries a chevron-/-arrow terminator (DESIGN.md is
    explicit: CTA labels end at the last letter). Use this for tertiary
    inline links that should still read in the brand's CTA voice.
    """
    color = color if color is not None else T.INK
    return add_text(
        target, x_px, y_px, w_px, h_px,
        text.upper(),
        size_px=T.SIZE_PX["chip"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color,
        uppercase=False,  # already uppercased above
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )


def add_hairline(target, x_px: float, y_px: float, w_px: float, *,
                 color: RGBColor | None = None, weight_px: int = 1):
    """1px brightness-step divider — Ferrari DESIGN.md `hairline` (#303030 on
    dark, #d2d2d2 on light editorial bands). Used above footers, between
    table rows, around driver / preowned tiles. Brightness-step + hairline
    carries the depth — Ferrari has no shadow tiers."""
    return add_rect(
        target, x_px, y_px, w_px, weight_px,
        fill=color if color is not None else T.FOG,
    )


# ─── Logo + chrome ─────────────────────────────────────────────────────────

def add_logo(target, *, variant: str = "dark"):
    """Place the Ferrari lockup (heraldic-shield glyph + wordmark) at top-left.

    Variant 'dark' is the default — DESIGN.md positions the near-black canvas
    as the dominant page surface. 'light' is reserved for the white editorial
    bands (preowned listings, pricing). The shield always renders in Modena
    yellow with a Rosso Corsa hairline border — high recognition on either
    canvas. Wordmark is FerrariSans 700 UPPERCASE with open tracking
    (0.05em) — Ferrari's classical lockup register / nav-link voice.
    """
    text_color = T.INK_ON_LIGHT if variant == "light" else T.INK
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
        size_px=18,
        weight="bold",
        font=T.FONT_DISPLAY,
        color=text_color,
        uppercase=True,
        tracking_em=0.1,
    )


def add_pgmeta(master_or_slide, text: str = "Ferrari · 2026", *, color=None):
    """Page-meta stamp at top-right. Ferrari nav-link voice — UPPERCASE,
    weight 600, 0.05em (~0.65px) tracking per DESIGN.md `nav-link`."""
    color = color if color is not None else T.STEEL
    return add_text(
        master_or_slide, 1420, 78, 420, 28, text,
        size_px=T.SIZE_PX["pgmeta"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color, align=PP_ALIGN.RIGHT,
        uppercase=True,
        tracking_em=0.05,
    )


def add_footer_left(master_or_slide, text: str = "JAN 2026 · SHOWCASE",
                    *, color=None):
    """Footer-left — date / classification. Ferrari nav-link voice."""
    color = color if color is not None else T.STEEL
    return add_text(
        master_or_slide, 96, 1030, 720, 24, text,
        size_px=T.SIZE_PX["footer"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color,
        uppercase=True,
        tracking_em=0.05,
    )


def add_footer_right(master_or_slide, text: str, *, color=None):
    """Footer-right — slide number, nav-link voice."""
    color = color if color is not None else T.STEEL
    return add_text(
        master_or_slide, 1100, 1030, 724, 24, text,
        size_px=T.SIZE_PX["footer"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color, align=PP_ALIGN.RIGHT,
        uppercase=True,
        tracking_em=0.05,
    )


def paint_chrome(target, *, variant: str = "dark",
                 pgmeta: str = "Ferrari · 2026",
                 footer_left: str = "JAN 2026 · SHOWCASE",
                 total: int | None = None):
    """Paint full chrome onto a layout or slide.

    Default variant is 'dark' — Ferrari DESIGN.md positions the near-black
    canvas as the dominant page surface, with white editorial bands reserved
    for preowned / pricing contexts only. Layouts that paint a full-bleed
    white editorial band must opt into variant='light'.
    """
    chrome_color = T.SILVER if variant == "light" else T.STEEL
    add_logo(target, variant=variant)
    add_pgmeta(target, pgmeta, color=chrome_color)
    # Footer hairline — brightness-step divider on every slide
    rule_color = T.FOG_STRONG if variant == "light" else T.FOG
    add_hairline(target, 96, 1018, 1728, color=rule_color)
    add_footer_left(target, footer_left, color=chrome_color)
    tb = add_footer_right(target, "SLIDE ", color=chrome_color)
    _append_slide_num_field(tb, total=total, color=chrome_color)


def _append_slide_num_field(tb, *, total: int | None, color):
    """Replace the text frame's runs with "SLIDE <fld> [/ N]" so PowerPoint
    renders the live slide number — display sans, UPPERCASE, nav-link voice."""
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
        # 0.05em tracking per CHIP_RULE.tracking-nav-em — pptx spc unit = 1/100 of a point.
        spc_val = int(round(0.05 * (T.SIZE_PX["footer"] * 0.5) * 100))
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
