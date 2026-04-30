"""Image / media components.

`add_image_placeholder` draws a 45° striped pattern fill with a centered
uppercase label — mirrors the HTML `.pic` class
(`repeating-linear-gradient(45deg, FOG 0 14px, PAPER 14px 28px)`).
Users can right-click → Format Shape → Fill → Picture to replace.
"""
from __future__ import annotations

from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn

import theme as T
from geometry import px, pt_from_px
from components.primitives import add_rect, add_text


def add_image_placeholder(
    target,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    *,
    label: str = "Image",
    dark: bool = False,
):
    """Diagonally-striped placeholder with centered caption."""
    fg_hex = "1A1A1A" if dark else T.HEX["fog"]
    bg_hex = "222222" if dark else T.HEX["paper"]
    label_color = T.STEEL if dark else T.GRAPHITE

    rect = add_rect(target, x_px, y_px, w_px, h_px, fill=T.FOG)
    _set_diag_pattern_fill(rect, fg_hex=fg_hex, bg_hex=bg_hex)

    return add_text(
        target, x_px, y_px, w_px, h_px, label.upper(),
        size_px=T.SIZE_PX["eyebrow"], weight="bold", font=T.FONT_DISPLAY,
        color=label_color, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
        tracking_em=0.1,
    )


def _set_diag_pattern_fill(shape, *, fg_hex: str, bg_hex: str):
    """Replace a shape's fill with a preset `wdDnDiag` pattern.

    OOXML presets approximate the HTML's 14px stripes; `wdDnDiag` (wide
    downward-diagonal) matches the stripe density of the HTML's
    `repeating-linear-gradient(45deg, FOG 0 14px, PAPER 14px 28px)` at
    slide scale better than denser presets like `dkDnDiag`.
    """
    spPr = shape._element.find(qn("p:spPr"))
    if spPr is None:
        spPr = shape._element.find(qn("{http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing}spPr"))
    if spPr is None:
        # Try the alternate namespace on autoshapes
        from pptx.oxml.ns import nsmap
        spPr = shape._element.spPr
    # Remove existing fill
    for tag in ("solidFill", "gradFill", "blipFill", "noFill", "pattFill"):
        el = spPr.find(qn(f"a:{tag}"))
        if el is not None:
            spPr.remove(el)
    # Insert <a:pattFill prst="dkDnDiag">
    pattFill = etree.SubElement(spPr, qn("a:pattFill"))
    pattFill.set("prst", "wdDnDiag")
    fg = etree.SubElement(pattFill, qn("a:fgClr"))
    etree.SubElement(fg, qn("a:srgbClr")).set("val", fg_hex)
    bg = etree.SubElement(pattFill, qn("a:bgClr"))
    etree.SubElement(bg, qn("a:srgbClr")).set("val", bg_hex)
    # Move fill BEFORE line element (schema order)
    ln = spPr.find(qn("a:ln"))
    if ln is not None:
        spPr.remove(pattFill)
        ln.addprevious(pattFill)
