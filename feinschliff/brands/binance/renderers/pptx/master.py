"""Slide master + theme authoring + named-layout plumbing.

Public API (in call order from build.py):
  1. `set_slide_size`        — 16:9 at 1920×1080 (13.333" × 7.5").
  2. `apply_binance_theme` — rewrite clrScheme + fontScheme to Binance tokens.
  3. `ensure_n_layouts`      — grow the master up to N layout parts by cloning.
  4. `reset_master_shapes`   — clear the master so chrome lives only on layouts.
  5. `reset_layout`          — clear a layout's shapes so a layout-builder can fill it.
  6. `order_layouts`         — arrange sldLayoutIdLst to match demo-deck order.
"""
from __future__ import annotations

from lxml import etree
from pptx.opc.constants import CONTENT_TYPE as CT
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.opc.package import PackURI
from pptx.oxml.ns import qn
from pptx.parts.slide import SlideLayoutPart
from pptx.util import Inches

import theme as T


# ─── Slide size ────────────────────────────────────────────────────────────
def set_slide_size(prs, width_in: float = 13.333, height_in: float = 7.5):
    """16:9 widescreen at 1920×1080 CSS px (matches the HTML reference)."""
    prs.slide_width = Inches(width_in)
    prs.slide_height = Inches(height_in)


# ─── Theme (colour + font scheme) ──────────────────────────────────────────
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def _clr(tag: str, hex_value: str):
    el = etree.Element(f"{A}{tag}")
    srgb = etree.SubElement(el, f"{A}srgbClr")
    srgb.set("val", hex_value)
    return el


def _sys_clr(tag: str, system_name: str, last_hex: str):
    el = etree.Element(f"{A}{tag}")
    sysclr = etree.SubElement(el, f"{A}sysClr")
    sysclr.set("val", system_name)
    sysclr.set("lastClr", last_hex)
    return el


def apply_binance_theme(prs):
    """Rewrite the theme's clrScheme + fontScheme to Binance tokens."""
    master_part = prs.slide_masters[0].part
    theme_part = master_part.part_related_by(RT.THEME)
    tree = etree.fromstring(theme_part.blob)

    clr_scheme = tree.find(f".//{A}clrScheme")
    if clr_scheme is not None:
        for child in list(clr_scheme):
            clr_scheme.remove(child)
        clr_scheme.set("name", "Binance")
        clr_scheme.append(_sys_clr("dk1", "windowText", T.HEX["black"]))
        clr_scheme.append(_sys_clr("lt1", "window",     T.HEX["white"]))
        clr_scheme.append(_clr("dk2",     T.HEX["ink"]))
        clr_scheme.append(_clr("lt2",     T.HEX["paper"]))
        clr_scheme.append(_clr("accent1", T.HEX["accent"]))
        clr_scheme.append(_clr("accent2", T.HEX["highlight"]))
        clr_scheme.append(_clr("accent3", T.HEX["graphite"]))
        clr_scheme.append(_clr("accent4", T.HEX["steel"]))
        clr_scheme.append(_clr("accent5", T.HEX["silver"]))
        clr_scheme.append(_clr("accent6", T.HEX["fog"]))
        clr_scheme.append(_clr("hlink",    T.HEX["accent_hover"]))
        clr_scheme.append(_clr("folHlink", T.HEX["accent"]))

    font_scheme = tree.find(f".//{A}fontScheme")
    if font_scheme is not None:
        for child in list(font_scheme):
            font_scheme.remove(child)
        font_scheme.set("name", "Binance")
        for tag in ("majorFont", "minorFont"):
            font = etree.SubElement(font_scheme, f"{A}{tag}")
            latin = etree.SubElement(font, f"{A}latin")
            latin.set("typeface", T.FONT_DISPLAY)
            latin.set("panose", "020B0604020202020204")
            etree.SubElement(font, f"{A}ea").set("typeface", "")
            etree.SubElement(font, f"{A}cs").set("typeface", "")

    theme_part._blob = etree.tostring(
        tree, xml_declaration=True, encoding="UTF-8", standalone=True
    )


# ─── Growing the layout set via cloning ────────────────────────────────────
_BLANK_LAYOUT_XML = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
             xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"
             type="blank" preserve="1">
  <p:cSld name="Blank">
    <p:spTree>
      <p:nvGrpSpPr>
        <p:cNvPr id="1" name=""/>
        <p:cNvGrpSpPr/>
        <p:nvPr/>
      </p:nvGrpSpPr>
      <p:grpSpPr>
        <a:xfrm>
          <a:off x="0" y="0"/>
          <a:ext cx="0" cy="0"/>
          <a:chOff x="0" y="0"/>
          <a:chExt cx="0" cy="0"/>
        </a:xfrm>
      </p:grpSpPr>
    </p:spTree>
  </p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>
"""


def _next_sldLayoutId(sldLayoutIdLst) -> int:
    """Allocate the next free layout id (2^31 range, incrementing)."""
    mx = 2147483648
    for c in sldLayoutIdLst:
        sid = int(c.get("id"))
        mx = max(mx, sid)
    return mx + 1


def ensure_n_layouts(prs, n: int):
    """Grow the master's SlideLayout collection to at least `n` parts.

    New layouts are minimal "Blank" skeletons — caller is expected to fully
    repaint each via the `register_layouts` pipeline.
    """
    master_part = prs.slide_masters[0].part
    existing = [
        rel for rel in master_part.rels.values()
        if rel.reltype == RT.SLIDE_LAYOUT
    ]
    needed = n - len(existing)
    if needed <= 0:
        return

    sldLayoutIdLst = prs.slide_masters[0].element.find(qn("p:sldLayoutIdLst"))
    pkg = master_part.package

    for _ in range(needed):
        partname = pkg.next_partname("/ppt/slideLayouts/slideLayout%d.xml")
        new_part = SlideLayoutPart.load(
            PackURI(partname),
            CT.PML_SLIDE_LAYOUT,
            pkg,
            _BLANK_LAYOUT_XML,
        )
        # Link layout → master
        new_part.relate_to(master_part, RT.SLIDE_MASTER)
        # Link master → layout
        rId = master_part.relate_to(new_part, RT.SLIDE_LAYOUT)
        # Register in sldLayoutIdLst (compute id BEFORE attaching the element).
        new_id = _next_sldLayoutId(sldLayoutIdLst)
        entry = etree.SubElement(sldLayoutIdLst, qn("p:sldLayoutId"))
        entry.set("id", str(new_id))
        entry.set(qn("r:id"), rId)


def reset_master_shapes(master):
    """Strip all default placeholders (title, body, date, footer, slideNum)
    from the slide master. Feinschliff puts its own chrome on.
    """
    spTree = master.element.find(qn("p:cSld")).find(qn("p:spTree"))
    for child in list(spTree):
        local = etree.QName(child.tag).localname
        if local in ("sp", "pic", "graphicFrame", "cxnSp"):
            spTree.remove(child)


def reset_layout(layout):
    """Strip all shapes + background from a layout so a builder can repaint."""
    cSld = layout.element.find(qn("p:cSld"))
    bg = cSld.find(qn("p:bg"))
    if bg is not None:
        cSld.remove(bg)
    spTree = cSld.find(qn("p:spTree"))
    for child in list(spTree):
        local = etree.QName(child.tag).localname
        if local in ("sp", "pic", "graphicFrame", "cxnSp"):
            spTree.remove(child)


def order_layouts(prs, layout_part_ids: list[str]):
    """Reorder the master's sldLayoutIdLst by a sequence of layout rIds."""
    master = prs.slide_masters[0]
    sldLayoutIdLst = master.element.find(qn("p:sldLayoutIdLst"))
    existing = {c.get(qn("r:id")): c for c in sldLayoutIdLst}
    # Clear then re-append in desired order
    for c in list(sldLayoutIdLst):
        sldLayoutIdLst.remove(c)
    for rId in layout_part_ids:
        if rId in existing:
            sldLayoutIdLst.append(existing[rId])
    # Append any that weren't in the ordering list (stays trailing).
    for rId, el in existing.items():
        if rId not in layout_part_ids:
            sldLayoutIdLst.append(el)
