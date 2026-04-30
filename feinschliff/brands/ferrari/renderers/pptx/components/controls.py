"""Ferrari interactive components — buttons + chips.

Ferrari's button is the brand's signature CTA: sharp 0px corners, Rosso Corsa
fill, UPPERCASE 700 14px label with 1.4px (~0.1em) tracking, NO arrow / chevron
terminator (DESIGN.md is explicit — labels end at the last letter).
The chip is the badge-pill — the ONE place Ferrari uses pill geometry
(rounded.full = 9999), caption-uppercase voice (11px / 600 / 1.1px tracking).

Variants:
  * `primary`  — Rosso Corsa fill, white label. The brand voltage.
  * `dark`     — canvas-elevated (#303030) fill, white label.
  * `outline`  — transparent fill with 1px white outline on dark, ink outline
                 on light. DESIGN.md `button-outline-on-dark` / `-on-light`.
  * `ghost`    — alias of outline for backwards compatibility with layouts.
"""
from __future__ import annotations

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu

import theme as T
from geometry import px, pt_from_px
from components.primitives import add_rect, _shapes


def add_button(target, x_px, y_px, label, *, variant: str = "primary",
               w_px: float = 220, h_px: float = 64, arrow: bool | None = None):
    """Ferrari button — sharp 0px CTA in the brand's UPPERCASE 700 button voice.

    `arrow` defaults to False per DESIGN.md (Ferrari CTAs end at the last
    letter, never with a chevron). Pass `arrow=True` if a layout explicitly
    wants the arrow terminator — but it's off-brand.
    """
    fills = {"primary": T.ACCENT, "dark": T.SURFACE_DARK_ELEVATED,
             "ghost":  None,     "outline": None}
    label_colors = {"primary": T.INK, "dark": T.INK,
                    "ghost":   T.INK, "outline": T.INK}
    fill = fills.get(variant, T.ACCENT)
    text_color = label_colors.get(variant, T.INK)
    is_outlined = variant in ("ghost", "outline")
    if arrow is None:
        arrow = False  # Ferrari default — labels end at the last letter

    btn = add_rect(
        target, x_px, y_px, w_px, h_px,
        fill=fill,
        line=(T.INK if is_outlined else fill),
        line_weight_px=1 if is_outlined else 0,
    )
    btn.shadow.inherit = False
    tf = btn.text_frame
    tf.margin_left = px(28)
    tf.margin_right = px(28)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = (f"{label}  →" if arrow else label).upper()
    run.font.name = T.FONT_DISPLAY
    run.font.size = pt_from_px(T.SIZE_PX["btn"])
    run.font.bold = True
    run.font.color.rgb = text_color
    rPr = run._r.get_or_add_rPr()
    spc_val = int(round(0.1 * (T.SIZE_PX["btn"] * 0.5) * 100))
    rPr.set("spc", str(spc_val))
    return btn


def add_chip(target, x_px, y_px, label, *, variant: str = "ink",
             w_px: float = 150, h_px: float = 30):
    """Ferrari badge-pill — the ONE place pill geometry is allowed.
    Caption-uppercase voice: 11px / 600 / 1.1px (~0.1em) tracking.

    Variants:
      * `ink`    — canvas-elevated (#303030) fill, white text.
      * `red`    — Rosso Corsa fill, white text. F1 race-position badge.
      * `yellow` — Modena yellow fill, ink text. Hypersail-only — off-brand outside that scope.
      * `ghost`  — transparent with 1px white outline on dark.
    """
    fg_fills = {
        "ink":     (T.SURFACE_DARK_ELEVATED, T.INK),
        "red":     (T.ACCENT,                T.INK),
        "yellow":  (T.HIGHLIGHT,             T.INK_ON_LIGHT),
        "orange":  (T.ACCENT,                T.INK),  # alias for back-compat
        "amber":   (T.HIGHLIGHT,             T.INK_ON_LIGHT),  # alias for back-compat
        "ghost":   (None,                    T.INK),
    }
    fill, text_color = fg_fills.get(variant, fg_fills["ink"])
    ghost = variant == "ghost"
    chip_radius = T.RADIUS.get("chip", 9999)
    if chip_radius >= 9999:
        shape = _shapes(target).add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            px(x_px), px(y_px), px(w_px), px(h_px),
        )
        try:
            shape.adjustments[0] = 0.5
        except (IndexError, AttributeError):
            pass
        if fill is not None:
            shape.fill.solid()
            shape.fill.fore_color.rgb = fill
        else:
            shape.fill.background()
        if ghost:
            shape.line.color.rgb = T.INK
            shape.line.width = px(1)
        else:
            shape.line.fill.background()
        shape.shadow.inherit = False
    else:
        shape = add_rect(
            target, x_px, y_px, w_px, h_px,
            fill=fill,
            line=(T.INK if ghost else None),
            line_weight_px=1 if ghost else 0,
        )
        shape.shadow.inherit = False

    tf = shape.text_frame
    tf.margin_left = px(14)
    tf.margin_right = px(14)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = label.upper()
    run.font.name = T.FONT_DISPLAY
    run.font.size = pt_from_px(T.SIZE_PX["chip"])
    run.font.bold = False  # caption-uppercase is 600, not 700
    run.font.color.rgb = text_color
    rPr = run._r.get_or_add_rPr()
    spc_val = int(round(0.1 * (T.SIZE_PX["chip"] * 0.5) * 100))
    rPr.set("spc", str(spc_val))
    return shape
