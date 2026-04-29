"""Helpers for creating typed PowerPoint placeholders on SlideLayouts.

python-pptx doesn't expose placeholder-creation as a public API, so we emit
the `<p:sp>` XML directly. Users see these placeholders as editable fields
when they insert a new slide from the layout.

Placeholder types we use:
  - "title"   — main heading
  - "body"    — free text body (can have >1 on a layout via idx)
  - "pic"     — picture placeholder
  - custom idx values for eyebrow, KPI values, chapter numbers, etc.
"""
from __future__ import annotations

from lxml import etree
from pptx.oxml.ns import qn
from pptx.util import Emu

import theme as T
from geometry import px, pt_from_px


NSMAP = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}


def _next_shape_id(spTree) -> int:
    """Return the next free shape id in a spTree."""
    max_id = 1
    for el in spTree.iter():
        sid = el.get("id")
        if sid and sid.isdigit():
            max_id = max(max_id, int(sid))
    return max_id + 1


def add_text_placeholder(
    layout,
    *,
    idx: int,
    name: str,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    prompt_text: str = "",
    size_px: float = 26,
    weight: str = "regular",
    color=T.BLACK,
    font: str | None = None,
    tracking_em: float = 0,
    line_height: float = 1.0,
    uppercase: bool = False,
    align: str = "l",
    anchor: str = "t",
    ph_type: str | None = None,
):
    """Add a typed text placeholder to a SlideLayout.

    ph_type: None (custom body) | "title" | "body" | "ctrTitle" | "subTitle".
    idx:     unique id within the layout (0 = title, 1+ for others).
    """
    spTree = layout.element.find(qn("p:cSld")).find(qn("p:spTree"))
    sid = _next_shape_id(spTree)

    sp = etree.SubElement(spTree, qn("p:sp"))

    # nvSpPr
    nvSpPr = etree.SubElement(sp, qn("p:nvSpPr"))
    cNvPr = etree.SubElement(nvSpPr, qn("p:cNvPr"))
    cNvPr.set("id", str(sid))
    cNvPr.set("name", name)

    cNvSpPr = etree.SubElement(nvSpPr, qn("p:cNvSpPr"))
    spLocks = etree.SubElement(cNvSpPr, qn("a:spLocks"))
    spLocks.set("noGrp", "1")

    nvPr = etree.SubElement(nvSpPr, qn("p:nvPr"))
    ph = etree.SubElement(nvPr, qn("p:ph"))
    if ph_type:
        ph.set("type", ph_type)
    if idx is not None and idx != 0:
        ph.set("idx", str(idx))

    # spPr
    spPr = etree.SubElement(sp, qn("p:spPr"))
    xfrm = etree.SubElement(spPr, qn("a:xfrm"))
    off = etree.SubElement(xfrm, qn("a:off"))
    off.set("x", str(int(px(x_px))))
    off.set("y", str(int(px(y_px))))
    ext = etree.SubElement(xfrm, qn("a:ext"))
    ext.set("cx", str(int(px(w_px))))
    ext.set("cy", str(int(px(h_px))))

    # txBody
    txBody = etree.SubElement(sp, qn("p:txBody"))
    bodyPr = etree.SubElement(txBody, qn("a:bodyPr"))
    bodyPr.set("lIns", "0")
    bodyPr.set("tIns", "0")
    bodyPr.set("rIns", "0")
    bodyPr.set("bIns", "0")
    bodyPr.set("wrap", "square")
    bodyPr.set("anchor", {"t": "t", "m": "ctr", "b": "b"}[anchor])

    etree.SubElement(txBody, qn("a:lstStyle"))

    # Build one <a:p> per newline-separated line so multi-line prompts render.
    lines = (prompt_text or "").split("\n") if prompt_text else [""]
    for line in lines:
        p = etree.SubElement(txBody, qn("a:p"))
        pPr = etree.SubElement(p, qn("a:pPr"))
        # Reset bullet-list metrics inherited from the master's body textStyle.
        pPr.set("marL", "0")
        pPr.set("indent", "0")
        pPr.set("algn", {"l": "l", "c": "ctr", "r": "r"}[align])
        if line_height != 1.0:
            lnSpc = etree.SubElement(pPr, qn("a:lnSpc"))
            spcPct = etree.SubElement(lnSpc, qn("a:spcPct"))
            spcPct.set("val", str(int(line_height * 100000)))
        # Always disable bullets on custom placeholders — Feinschliff is a flat system.
        etree.SubElement(pPr, qn("a:buNone"))

        if line:
            r = etree.SubElement(p, qn("a:r"))
            rPr = _rPr(
                size_px=size_px, weight=weight, color=color,
                font=font or T.FONT_DISPLAY, tracking_em=tracking_em,
                cap=("all" if uppercase else None),
            )
            r.append(rPr)
            t = etree.SubElement(r, qn("a:t"))
            # Still uppercase the <a:t> content so renderers without cap
            # support (e.g. older viewers) see uppercase too.
            t.text = line.upper() if uppercase else line
        else:
            etree.SubElement(p, qn("a:endParaRPr")).set("lang", "en-US")

    return sp


def add_picture_placeholder(
    layout,
    *,
    idx: int,
    name: str,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
):
    """Add a picture placeholder. User clicks it to insert a photo."""
    spTree = layout.element.find(qn("p:cSld")).find(qn("p:spTree"))
    sid = _next_shape_id(spTree)

    sp = etree.SubElement(spTree, qn("p:sp"))

    nvSpPr = etree.SubElement(sp, qn("p:nvSpPr"))
    cNvPr = etree.SubElement(nvSpPr, qn("p:cNvPr"))
    cNvPr.set("id", str(sid))
    cNvPr.set("name", name)

    cNvSpPr = etree.SubElement(nvSpPr, qn("p:cNvSpPr"))
    spLocks = etree.SubElement(cNvSpPr, qn("a:spLocks"))
    spLocks.set("noGrp", "1")

    nvPr = etree.SubElement(nvSpPr, qn("p:nvPr"))
    ph = etree.SubElement(nvPr, qn("p:ph"))
    ph.set("type", "pic")
    ph.set("idx", str(idx))

    spPr = etree.SubElement(sp, qn("p:spPr"))
    xfrm = etree.SubElement(spPr, qn("a:xfrm"))
    off = etree.SubElement(xfrm, qn("a:off"))
    off.set("x", str(int(px(x_px))))
    off.set("y", str(int(px(y_px))))
    ext = etree.SubElement(xfrm, qn("a:ext"))
    ext.set("cx", str(int(px(w_px))))
    ext.set("cy", str(int(px(h_px))))
    # Striped grey fill so the placeholder is visually obvious even unfilled.
    solidFill = etree.SubElement(spPr, qn("a:solidFill"))
    srgb = etree.SubElement(solidFill, qn("a:srgbClr"))
    srgb.set("val", "E0E0E0")

    txBody = etree.SubElement(sp, qn("p:txBody"))
    bodyPr = etree.SubElement(txBody, qn("a:bodyPr"))
    bodyPr.set("anchor", "ctr")
    etree.SubElement(txBody, qn("a:lstStyle"))
    p = etree.SubElement(txBody, qn("a:p"))
    pPr = etree.SubElement(p, qn("a:pPr"))
    pPr.set("algn", "ctr")
    etree.SubElement(p, qn("a:endParaRPr")).set("lang", "en-US")

    return sp


def _rPr(*, size_px, weight, color, font, tracking_em, cap: str | None = None):
    rPr = etree.Element(qn("a:rPr"))
    rPr.set("lang", "en-US")
    rPr.set("sz", str(int(size_px * 0.5 * 100)))
    if weight == "bold":
        rPr.set("b", "1")
    if tracking_em:
        rPr.set("spc", str(int(round(tracking_em * size_px * 0.5 * 100))))
    if cap:
        # cap="all" → PowerPoint renders the run as uppercase regardless of
        # the actual <a:t> text, so user-typed replacements stay uppercase.
        rPr.set("cap", cap)

    solidFill = etree.SubElement(rPr, qn("a:solidFill"))
    srgb = etree.SubElement(solidFill, qn("a:srgbClr"))
    srgb.set("val", "{:02X}{:02X}{:02X}".format(*color))

    latin = etree.SubElement(rPr, qn("a:latin"))
    type_name = font
    if weight == "light":
        type_name += " Light"
    elif weight == "medium":
        type_name += " Medium"
    latin.set("typeface", type_name)
    return rPr


def set_layout_background(layout, hex_color: str):
    """Paint a solid background on a SlideLayout's cSld element."""
    cSld = layout.element.find(qn("p:cSld"))
    # Remove existing bg, if any.
    existing = cSld.find(qn("p:bg"))
    if existing is not None:
        cSld.remove(existing)
    bg = etree.Element(qn("p:bg"))
    bgPr = etree.SubElement(bg, qn("p:bgPr"))
    solidFill = etree.SubElement(bgPr, qn("a:solidFill"))
    srgb = etree.SubElement(solidFill, qn("a:srgbClr"))
    srgb.set("val", hex_color.lstrip("#"))
    etree.SubElement(bgPr, qn("a:effectLst"))
    # Must go at the top of cSld (before spTree).
    cSld.insert(0, bg)


def set_layout_name(layout, name: str):
    """Rename the SlideLayout. Appears in Insert → New Slide menu."""
    cSld = layout.element.find(qn("p:cSld"))
    cSld.set("name", name)


def clear_layout_shapes(layout, *, keep_chrome: bool = True):
    """Remove all existing `<p:sp>` / `<p:pic>` shapes from a layout.

    Leaves group shape placeholder + nvGrpSpPr intact. Optionally keeps the
    default date/footer/slidenum placeholders if keep_chrome=True (we generally
    don't — chrome lives on the master).
    """
    spTree = layout.element.find(qn("p:cSld")).find(qn("p:spTree"))
    for child in list(spTree):
        tag = etree.QName(child.tag).localname
        if tag in ("sp", "pic", "graphicFrame", "cxnSp"):
            spTree.remove(child)
