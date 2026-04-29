"""Shared helpers used by multiple SVG layouts.

Kept small on purpose — same rule as the PPTX renderer: if a pattern is
used by 2+ layouts, it belongs here; if it's only used by 1, keep it
inline in that layout's file.
"""
from __future__ import annotations

from xml.etree.ElementTree import Element

import theme as T
from components import rule, eyebrow as _eyebrow, title as _title
from geometry import FOOTER_Y, LOGO_X, LOGO_Y, PGMETA_X, PGMETA_Y
from primitives import text


def content_header(parent: Element, *, eyebrow: str, title: str, y_rule: float = 260) -> None:
    """Top-of-slide rule + eyebrow + title stack used by content layouts."""
    rule(parent, 100, y_rule, width=80, height=4, color=T.HEX["black"])
    _eyebrow(parent, 100, y_rule + 40, eyebrow)
    _title(
        parent, 100, y_rule + 80, title,
        size_px=T.SIZE_PX["slide_title"], weight="bold",
        tracking_em=-0.015, line_height=1.1,
    )


def paint_chrome(
    parent: Element,
    *,
    variant: str = "light",
    pgmeta: str = "Feinschliff Design System · 2026",
    slide_num: str = "01",
    footer_left: str = "Feinschliff Design System · 2026",
) -> None:
    """Paint logo + pgmeta + footer-left + slide-num onto `parent`.

    `variant="dark"` uses white chrome type (for accent / ink backgrounds
    where black chrome would fight the wordmark). `variant="light"` uses
    black chrome type for paper/white backgrounds.
    """
    chrome_color = T.HEX["white"] if variant == "dark" else T.HEX["black"]

    _wordmark(parent, variant=variant)

    # Top-right pgmeta (mono 18 px).
    text(
        parent, PGMETA_X, PGMETA_Y, pgmeta,
        size_px=T.SIZE_PX["pgmeta"],
        weight=T.WEIGHT["regular"],
        color=chrome_color,
        font=T.FONT_MONO,
        anchor="end",
        tracking_em=0.1,
        uppercase=True,
    )

    # Footer-left.
    text(
        parent, 100, FOOTER_Y, footer_left,
        size_px=T.SIZE_PX["footer"],
        weight=T.WEIGHT["regular"],
        color=chrome_color,
        font=T.FONT_MONO,
        tracking_em=0.12,
        uppercase=True,
    )

    # Footer-right slide number.
    text(
        parent, 1820, FOOTER_Y, slide_num,
        size_px=T.SIZE_PX["footer"],
        weight=T.WEIGHT["regular"],
        color=chrome_color,
        font=T.FONT_MONO,
        anchor="end",
        tracking_em=0.1,
        uppercase=True,
    )


def _wordmark(parent: Element, *, variant: str) -> None:
    """Inline-SVG Feinschliff wordmark — Noto Sans, 28 px, accent, 0.1em tracking,
    uppercase. Kept pure-SVG (no PNG embed) so outputs stay self-contained."""
    # Wordmark colour follows the PPTX logo asset: white on dark, accent on
    # light. On accent backgrounds we also use white so the mark reads.
    color = T.HEX["white"] if variant == "dark" else T.HEX["accent"]
    text(
        parent, LOGO_X, LOGO_Y, "Feinschliff",
        size_px=28,
        weight=T.WEIGHT["bold"],
        color=color,
        font=T.FONT_DISPLAY,
        tracking_em=0.1,
        uppercase=True,
    )
