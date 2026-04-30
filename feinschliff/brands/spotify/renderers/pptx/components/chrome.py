"""Spotify chrome — equalizer glyph, lowercase wordmark, label-uppercase chrome.

Per Spotify DESIGN.md, the canvas is dark by default (`#121212`) and the
chrome is achromatic (white ink on near-black). Both `variant="light"`
and `variant="dark"` render light ink — the brand-defining surface IS
the dark canvas. The equalizer glyph stands in for the licensed Spotify
sound-wave mark; "spotify" is set lowercase per the brand's lowercase
wordmark register.

Three Spotify-specific primitives live here:

  * `add_equalizer_marker` — three vertical pill-bars in Spotify Green,
                             section divider analog of BMW's M-stripe.
  * `add_pill_link`        — UPPERCASE 1.4px tracked label, optional
                             "▸ PLAY" terminator. Spotify's pill button
                             at link-density.
  * `_add_equalizer`       — chrome-scale logo glyph (3 rounded bars).
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
from components.primitives import add_text, add_rounded_rect, _shapes

ASSETS = Path(__file__).resolve().parent.parent / "assets"

WORDMARK_TEXT = "spotify"

# Generic equalizer glyph — three vertical rounded bars of varying heights,
# evenly spaced inside an implicit circle. Reads as "sound / audio waveform"
# at small sizes. NOT the licensed Spotify wordmark or the official three-arc
# sound-wave mark; this is a brand-neutral equalizer abstraction that evokes
# music playback the same way Spotify's iconography does.
_EQ_BARS = [
    # (x, y, w, h) within 100x100 viewBox — short / tall / medium reads as a waveform snapshot
    (24, 38, 14, 42),
    (43, 22, 14, 58),
    (62, 50, 14, 30),
]
_EQ_VB_SIZE = 100
_EQ_PX = 28


def _sp_name(sp) -> str:
    nvSpPr = sp.find(qn("p:nvSpPr"))
    if nvSpPr is not None:
        cNvPr = nvSpPr.find(qn("p:cNvPr"))
        if cNvPr is not None:
            return cNvPr.get("name", "")
    return ""


def _add_equalizer(target, *, x_px: float, y_px: float, size_px: float, color: RGBColor):
    """Three pill-shaped vertical bars — chrome-scale equalizer glyph."""
    s = size_px / _EQ_VB_SIZE
    for (bx, by, bw, bh) in _EQ_BARS:
        shape = _shapes(target).add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            px(x_px + bx * s),
            px(y_px + by * s),
            px(bw * s),
            px(bh * s),
        )
        try:
            shape.adjustments[0] = 0.5
        except (IndexError, AttributeError):
            pass
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        shape.shadow.inherit = False


# ─── Spotify-signature primitives (per DESIGN.md) ──────────────────────────

def add_equalizer_marker(target, *, x_px: float, y_px: float,
                         w_px: float = 120, h_px: float = 36, bars: int = 3):
    """Section-divider equalizer — `bars` pill-shaped vertical bars in Spotify
    Green, varying heights, sitting on a baseline.

    Replaces BMW's `add_m_stripe` role: a brand-signature visual at chapter
    dividers and major editorial breaks. Heights are deterministic so multiple
    markers across the deck stay consistent.
    """
    if bars < 2:
        bars = 3

    bar_w_pct  = 0.16
    gap_pct    = 0.10
    n          = bars
    total_w    = n * bar_w_pct + (n - 1) * gap_pct
    scale      = w_px / (total_w + 0.05)  # small left-pad
    bar_w      = bar_w_pct * scale
    gap        = gap_pct * scale
    base_y     = y_px + h_px

    # Cycle of varying heights — reads as motion across the divider
    heights = [0.55, 0.95, 0.40, 0.85, 0.70, 0.50][:n] if n <= 6 else [0.55, 0.95, 0.40] * ((n // 3) + 1)
    for i in range(n):
        bh = h_px * heights[i]
        bx = x_px + i * (bar_w + gap)
        by = base_y - bh
        shape = _shapes(target).add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            px(bx), px(by), px(bar_w), px(bh),
        )
        try:
            shape.adjustments[0] = 0.5
        except (IndexError, AttributeError):
            pass
        shape.fill.solid()
        shape.fill.fore_color.rgb = T.ACCENT
        shape.line.fill.background()
        shape.shadow.inherit = False


def add_pill_link(target, x_px: float, y_px: float, w_px: float, h_px: float,
                  text: str = "PLAY", *, color: RGBColor | None = None):
    """Spotify pill-link label — UPPERCASE 14px / 700 / 1.4px tracking.

    Used wherever BMW would emit a "LEARN MORE ›" chevron-link. The pill
    button itself is `add_button(variant='primary')`; this is the typographic
    counterpart for inline density (tabs, breadcrumbs, secondary actions).
    """
    color = color if color is not None else T.ACCENT
    return add_text(
        target, x_px, y_px, w_px, h_px,
        text,
        size_px=T.SIZE_PX["chip"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color,
        uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )


def add_logo(target, *, variant: str = "dark"):
    """Spotify lockup — equalizer glyph + lowercase 'spotify' wordmark.

    Spotify is dark-canvas-first. Both `variant="dark"` (default) and
    `variant="light"` render light ink on the canvas — the brand-defining
    surface (`paper`/`white` token) is the near-black `#121212`.
    Wordmark is lowercase per Spotify's wordmark register, weight 700,
    near-tight tracking.
    """
    color = T.BLACK if variant != "accent" else T.ACCENT
    _add_equalizer(target, x_px=LOGO_X_PX + 2, y_px=LOGO_Y_PX + 4, size_px=_EQ_PX, color=T.ACCENT)
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


def add_pgmeta(master_or_slide, text: str = "SPOTIFY · 2026", *, color=None):
    """Page-meta stamp top-right — UPPERCASE 1.4px tracked label voice."""
    color = color if color is not None else T.STEEL
    return add_text(
        master_or_slide, 1420, 80, 420, 28, text,
        size_px=T.SIZE_PX["pgmeta"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color, align=PP_ALIGN.RIGHT,
        uppercase=True, tracking_em=0.1,
    )


def add_footer_left(master_or_slide, text: str = "JAN 2026 · SHOWCASE",
                    *, color=None):
    color = color if color is not None else T.STEEL
    return add_text(
        master_or_slide, 120, 1030, 700, 24, text,
        size_px=T.SIZE_PX["footer"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color,
        uppercase=True, tracking_em=0.1,
    )


def add_footer_right(master_or_slide, text: str, *, color=None):
    color = color if color is not None else T.STEEL
    return add_text(
        master_or_slide, 1100, 1030, 700, 24, text,
        size_px=T.SIZE_PX["footer"],
        weight="bold",
        font=T.FONT_DISPLAY,
        color=color, align=PP_ALIGN.RIGHT,
        uppercase=True, tracking_em=0.1,
    )


def paint_chrome(target, *, variant: str = "dark",
                 pgmeta: str = "SPOTIFY · 2026",
                 footer_left: str = "JAN 2026 · SHOWCASE",
                 total: int | None = None):
    """Paint full chrome onto a layout/slide.

    Spotify defaults to `variant="dark"` — the brand-defining surface is
    the near-black `#121212` canvas. Chrome ink reads silver `#B3B3B3`
    (Spotify's secondary-text color) so it sits behind content without
    competing.
    """
    chrome_color = T.STEEL  # silver — DESIGN.md secondary text role
    add_logo(target, variant=variant)
    add_pgmeta(target, pgmeta, color=chrome_color)
    add_footer_left(target, footer_left, color=chrome_color)
    tb = add_footer_right(target, "SLIDE ", color=chrome_color)
    _append_slide_num_field(tb, total=total, color=chrome_color)


def _append_slide_num_field(tb, *, total: int | None, color):
    """Replace text frame runs with "SLIDE <fld> [/ N]" so PowerPoint
    auto-fills the slide number."""
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
        spc_val = int(round(0.1 * (T.SIZE_PX["footer"] * 0.5) * 100))
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
