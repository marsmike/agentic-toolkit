"""Spotify buttons + chips — pill geometry, uppercase labels, wide tracking.

Per Spotify DESIGN.md `pill-and-circle geometry`:
  * Primary CTA: pill (radius 9999) with Spotify Green (#1ED760) fill +
    near-black icon/text.
  * Dark Pill: `#1f1f1f` background, white text — secondary actions.
  * Outlined Pill: transparent + 1px `#7c7c7c` border — follow / tertiary.
  * Chip: pill background `#1f1f1f`, label-uppercase 14px / 700 / 1.4px tracking.

Corner geometry comes from `tokens.json` `radius.btn` / `radius.chip` —
both 9999 (full pill) — read by `add_rounded_rect`.
"""
from __future__ import annotations

from pptx.enum.text import MSO_ANCHOR, PP_ALIGN

import theme as T
from geometry import px, pt_from_px
from components.primitives import add_rect, add_rounded_rect


def add_button(target, x_px, y_px, label, *, variant: str = "primary",
               w_px: float = 260, h_px: float = 64, arrow: bool | None = None):
    """Spotify pill button.

    Variants:
      * `primary` — Spotify Green pill, near-black label (the play CTA).
      * `dark`    — `#1f1f1f` pill, white label (secondary action).
      * `ghost`   — transparent pill, 1px hairline border, white label.

    Per Spotify DESIGN.md, label is UPPERCASE 14px / 700 / 1.4px tracking.
    """
    fills = {
        "primary": T.ACCENT,
        "dark":    T.SURFACE_DARK_ELEVATED,
        "ghost":   None,
    }
    label_colors = {
        "primary": T.SURFACE_DARK,    # near-black on green for max punch
        "dark":    T.WHITE,
        "ghost":   T.WHITE,
    }
    fill = fills[variant]
    if arrow is None:
        arrow = False    # Spotify buttons don't carry the chevron — pill IS the affordance

    btn = add_rounded_rect(
        target, x_px, y_px, w_px, h_px,
        radius_px=T.RADIUS.get("btn", 0),
        fill=fill,
        line=(T.OFF_WHITE_2 if variant == "ghost" else None),
        line_weight_px=1 if variant == "ghost" else 0,
    )
    tf = btn.text_frame
    tf.margin_left = px(28)
    tf.margin_right = px(28)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = (label.upper() + "  →") if arrow else label.upper()
    run.font.name = T.FONT_DISPLAY
    run.font.size = pt_from_px(T.SIZE_PX["btn"])
    run.font.color.rgb = label_colors[variant]
    run.font.bold = True
    rPr = run._r.get_or_add_rPr()
    # Spotify spec: 1.4px tracking on uppercase button labels — at 14pt that's ~0.1em.
    rPr.set("spc", str(int(0.1 * T.SIZE_PX["btn"] * 0.5 * 100)))
    return btn


def add_chip(target, x_px, y_px, label, *, variant: str = "dark", w_px: float = 170, h_px: float = 36):
    """Spotify pill chip / tag.

    Variants:
      * `dark`  — `#1f1f1f` pill, white label (default).
      * `green` — Spotify Green pill, near-black label (active state).
      * `ghost` — transparent pill, 1px border, silver label.
    """
    fg_fills = {
        "dark":  (T.SURFACE_DARK_ELEVATED, T.WHITE),
        "green": (T.ACCENT,                T.SURFACE_DARK),
        "ghost": (None,                    T.OFF_WHITE_2),
    }
    fill, text_color = fg_fills.get(variant, fg_fills["dark"])
    ghost = variant == "ghost"

    chip = add_rounded_rect(
        target, x_px, y_px, w_px, h_px,
        radius_px=T.RADIUS.get("chip", 0),
        fill=fill,
        line=(T.OFF_WHITE_2 if ghost else None),
        line_weight_px=1 if ghost else 0,
    )
    tf = chip.text_frame
    tf.margin_left = px(16)
    tf.margin_right = px(16)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = label.upper()
    run.font.name = T.FONT_DISPLAY
    run.font.size = pt_from_px(T.SIZE_PX["chip"])
    run.font.color.rgb = text_color
    run.font.bold = True
    rPr = run._r.get_or_add_rPr()
    rPr.set("spc", str(int(0.1 * T.SIZE_PX["chip"] * 0.5 * 100)))
    return chip
