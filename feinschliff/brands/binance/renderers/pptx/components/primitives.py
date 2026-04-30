"""Low-level shape primitives.

Every builder here takes a `target` (a Slide, SlideLayout, or SlideMaster's
shape tree) + coordinates in CSS pixels and returns the native PowerPoint
shape it produced. Components in higher files compose these primitives.
"""
from __future__ import annotations

from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.shapes.shapetree import SlideShapes
from pptx.util import Emu, Pt

import theme as T
from geometry import px, pt_from_px


# ─── Shapes collection resolver ───────────────────────────────────────────
def _shapes(target):
    """Return a shape tree that supports add_shape / add_textbox / add_picture.

    `SlideShapes` is the richest shape-tree class in python-pptx. `MasterShapes`
    and `LayoutShapes` don't expose `add_*` methods, but the underlying XML
    operations work identically — so we wrap any shape tree in `SlideShapes`.
    """
    if hasattr(target, "add_shape"):
        return target  # already a shape tree
    if hasattr(target, "shapes"):
        st = target.shapes
        if hasattr(st, "add_shape"):
            return st
        return SlideShapes(st.element, target)
    # A bare lxml element?
    return target


# ─── Rectangle (filled / outlined) ────────────────────────────────────────
def add_rect(
    target,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    *,
    fill: RGBColor | None = None,
    line: RGBColor | None = None,
    line_weight_px: float = 0,
):
    """Add a sharp-cornered rectangle. Used for cards, swatches, rules, tracks."""
    shape = _shapes(target).add_shape(
        MSO_SHAPE.RECTANGLE, px(x_px), px(y_px), px(w_px), px(h_px)
    )
    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill

    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = px(line_weight_px) if line_weight_px else Pt(0.75)

    shape.shadow.inherit = False
    return shape


def add_line(target, x_px, y_px, w_px, h_px, color: RGBColor):
    """A filled rectangle used as a divider/rule line (Feinschliff uses filled rects)."""
    return add_rect(target, x_px, y_px, w_px, h_px, fill=color)


# ─── Rounded rectangle (radius-policy-aware) ───────────────────────────────
def add_rounded_rect(
    target,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    *,
    radius_px: float = 0,
    fill: RGBColor | None = None,
    line: RGBColor | None = None,
    line_weight_px: float = 0,
    shadow: str | None = None,
):
    """Rectangle whose corners are read from brand-pack policy.

    Corner geometry (`radius_px`) is read from `tokens.json` via
    `theme.RADIUS["btn"]` / `["card"]` / `["pill"]`. Binance sets these to
    6 / 12 / 9999 so primary CTAs become sharp-but-not-zero, content cards
    get the soft 12px corner, and the lone pill geometry is reserved for
    the top-of-page signup CTA. The same code path that produces BMW's
    rectangles (0) and Spotify's pills (9999) produces Binance's 6/12.

    `radius_px <= 0` falls through to `add_rect` for byte-identical OOXML.

    `shadow` is currently a no-op for Binance — `tokens.json` policy block
    `shadow.elevated = "none"` confirms the brand is shadow-free. The
    parameter is kept for parity with the Spotify primitive signature so
    layouts can be ported across brand packs without diff churn.
    """
    if radius_px <= 0:
        return add_rect(
            target, x_px, y_px, w_px, h_px,
            fill=fill, line=line, line_weight_px=line_weight_px,
        )

    shape = _shapes(target).add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE, px(x_px), px(y_px), px(w_px), px(h_px)
    )

    half_min = min(w_px, h_px) / 2
    if half_min > 0:
        adjustment = min(0.5, max(0.0, radius_px / half_min))
        shape.adjustments[0] = adjustment

    if fill is None:
        shape.fill.background()
    else:
        shape.fill.solid()
        shape.fill.fore_color.rgb = fill

    if line is None:
        shape.line.fill.background()
    else:
        shape.line.color.rgb = line
        shape.line.width = px(line_weight_px) if line_weight_px else Pt(0.75)

    # Binance is shadow-free per tokens.json `shadow.elevated = "none"`.
    shape.shadow.inherit = False
    return shape


# ─── Text ─────────────────────────────────────────────────────────────────
def add_text(
    target,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    text: str,
    *,
    size_px: float,
    weight: str = "regular",
    color: RGBColor = T.BLACK,
    font: str | None = None,
    align: PP_ALIGN = PP_ALIGN.LEFT,
    anchor: MSO_ANCHOR = MSO_ANCHOR.TOP,
    tracking_em: float = 0,
    line_height: float = 1.0,
    uppercase: bool = False,
):
    """Place an editable text box with Feinschliff-correct typography."""
    tb = _shapes(target).add_textbox(px(x_px), px(y_px), px(w_px), px(h_px))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor

    lines = text.split("\n")
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if line_height != 1.0:
            p.line_spacing = line_height
        run = p.add_run()
        run.text = (line.upper() if uppercase else line)
        _apply_run_style(
            run,
            size_px=size_px,
            weight=weight,
            color=color,
            font=font or T.FONT_DISPLAY,
            tracking_em=tracking_em,
        )
    return tb


def _apply_run_style(run, *, size_px, weight, color, font, tracking_em):
    f = run.font
    f.name = font
    f.size = pt_from_px(size_px)
    f.color.rgb = color
    if weight == "bold":
        f.bold = True

    rPr = run._r.get_or_add_rPr()

    # Letter-spacing — python-pptx doesn't expose it.
    if tracking_em:
        spc_val = int(round(tracking_em * (size_px * 0.5) * 100))
        rPr.set("spc", str(spc_val))

    # Weight variants — macOS resolves on typeface name suffix. Binance uses
    # `semibold` (600) as the DEFAULT display weight, so it must be handled
    # alongside `light` / `medium`. `bold` already sets the OOXML b=1 flag
    # above and resolves to the heavier glyph via that path.
    if weight in ("light", "medium", "semibold"):
        rPr.set("b", "0")
        latin = rPr.find(qn("a:latin"))
        if latin is None:
            latin = etree.SubElement(rPr, qn("a:latin"))
        suffix = {
            "light":    " Light",
            "medium":   " Medium",
            "semibold": " SemiBold",
        }[weight]
        latin.set("typeface", font + suffix)


def set_solid_fill(shape, color: RGBColor):
    """Convenience: replace a shape's fill with a solid colour."""
    shape.fill.solid()
    shape.fill.fore_color.rgb = color
