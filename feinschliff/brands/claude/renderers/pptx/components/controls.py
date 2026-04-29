"""Interactive-looking components — buttons + chips.

These render as native rectangles with a single text run inside.
"""
from __future__ import annotations

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

import theme as T
from geometry import px, pt_from_px
from components.primitives import add_rect


def add_button(target, x_px, y_px, label, *, variant: str = "dark",
               w_px: float = 260, h_px: float = 80, arrow: bool | None = None):
    """Feinschliff button. Variants: primary (orange), dark (black), ghost (transparent w/ border).

    `arrow` defaults to True for primary + dark, False for ghost — matching
    the HTML reference. Pass explicitly to override.
    """
    fills = {"primary": T.ACCENT, "dark": T.BLACK, "ghost": None}
    label_colors = {"primary": T.BLACK, "dark": T.WHITE, "ghost": T.BLACK}
    fill = fills[variant]
    if arrow is None:
        arrow = variant != "ghost"

    btn = add_rect(
        target, x_px, y_px, w_px, h_px,
        fill=fill,
        line=(T.BLACK if variant == "ghost" else fill),
        line_weight_px=2,
    )
    tf = btn.text_frame
    tf.margin_left = px(36)
    tf.margin_right = px(36)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = f"{label}  →" if arrow else label
    run.font.name = T.FONT_DISPLAY + " Medium"
    run.font.size = pt_from_px(T.SIZE_PX["btn"])
    run.font.color.rgb = label_colors[variant]
    return btn


def add_chip(target, x_px, y_px, label, *, variant: str = "ink", w_px: float = 170, h_px: float = 44):
    """Feinschliff chip / tag. Variants: ink, orange, amber, ghost."""
    ghost = variant == "ghost"
    fg_fills = {
        "ink":    (T.INK, T.WHITE),
        "orange": (T.ACCENT, T.BLACK),
        "amber":  (T.HIGHLIGHT, T.BLACK),
        "ghost":  (None, T.INK),
    }
    fill, text_color = fg_fills[variant]
    chip = add_rect(
        target, x_px, y_px, w_px, h_px,
        fill=fill,
        line=(T.INK if ghost else None),
        line_weight_px=1 if ghost else 0,
    )
    tf = chip.text_frame
    tf.margin_left = px(18)
    tf.margin_right = px(18)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    run = p.add_run()
    run.text = label.upper()
    run.font.name = T.FONT_MONO
    run.font.size = pt_from_px(T.SIZE_PX["chip"])
    run.font.color.rgb = text_color
    rPr = run._r.get_or_add_rPr()
    rPr.set("spc", str(int(T.SIZE_PX["chip"] * 0.5 * 0.1 * 100)))
    return chip
