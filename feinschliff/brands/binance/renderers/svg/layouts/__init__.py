"""Feinschliff SVG layout registry.

Each entry is a (slug, module) pair. The module exposes:
  NAME   — human-readable name (mirrors the PPTX registry)
  ID     — file-name slug used when emitting `out/<id>.svg`
  build  — function that takes an SVG root <svg> Element and paints it in place

Adding a new layout:
  1. Drop a module next to this file, e.g. `quote.py`, with `NAME`, `ID`
     and `build(root)`.
  2. Append it to `LAYOUTS` below.
"""
from __future__ import annotations

from . import title_orange, kpi_grid, two_column_cards

LAYOUTS = [
    title_orange,
    kpi_grid,
    two_column_cards,
]
