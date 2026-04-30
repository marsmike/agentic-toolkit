"""Graphical bars component — horizontal bar chart for category breakdowns.

A pure renderer. Given a bounding box and a list of 3–6 bars (each with a
label, value 0–100, and optional accent flag) it paints stacked horizontal
rows: left-aligned mono label, coloured bar whose width is proportional to
`value`, and a right-aligned value text. A thin T.FOG hairline sits beneath
each row as a divider.

The component does NOT paint editable placeholders — those belong on the
hosting layout, so users can rewrite labels/values without re-running the
renderer. This function is purely for the decorative bar geometry + divider.

Layout inside the bounding box (CSS px, top-left origin):

    +-----------------------------------------------------+
    | LABEL (mono)  | ████████████████ fill ██████  | NN% |
    |  - hairline ------------------------------------- - |
    | LABEL (mono)  | ████ fill ██                   | N% |
    |  - hairline ------------------------------------- - |
    | ...                                                 |
    +-----------------------------------------------------+

Row spacing is controlled by `row_spacing_px` (default 80). Rows always
start at (x_px, y_px) — the component does not vertically centre the stack
inside h_px, so the hosting layout can pack extra content below.
"""
from __future__ import annotations

import theme as T
from components.primitives import add_rect, add_line, add_text


# Geometry defaults — tuned for 1920×1080 canvas with content x=100..1820.
LABEL_W_PX = 180
LABEL_GAP_PX = 24
VALUE_W_PX = 120
VALUE_GAP_PX = 16
BAR_H_PX = 50
ROW_SPACING_PX = 80
HAIRLINE_PX = 1


def add_graphical_bars(
    target,
    x_px: float,
    y_px: float,
    w_px: float,
    h_px: float,
    bars: list[tuple[str, float, bool]] | list[dict],
    *,
    label_w_px: float = LABEL_W_PX,
    value_w_px: float = VALUE_W_PX,
    bar_h_px: float = BAR_H_PX,
    row_spacing_px: float = ROW_SPACING_PX,
    fill_color=None,
    accent_color=None,
    label_color=None,
    value_color=None,
    hairline_color=None,
):
    """Paint 3–6 horizontal bar rows inside the (x, y, w, h) box.

    `bars` accepts either:
        - a list of (label, value, accent) tuples, or
        - a list of dicts {"label": str, "value": float, "accent": bool}

    Values are percentages 0–100; the bar fill width scales linearly so that
    100% fills the entire bar-area width. Accent bars use T.ACCENT, plain
    bars use T.INK (these defaults match the Feinschliff HTML reference — change by
    passing fill_color / accent_color).

    The `h_px` parameter is advisory — it does NOT clip or scale rows.
    Rows are always bar_h_px tall and spaced row_spacing_px apart so the
    typography stays consistent across decks. Pass enough `h_px` for
    `len(bars) * row_spacing_px` if you also want a trailing divider line.
    """
    if not bars:
        return

    # Normalise bars into (label, value, accent) triples.
    norm: list[tuple[str, float, bool]] = []
    for b in bars:
        if isinstance(b, dict):
            norm.append((b.get("label", ""), float(b.get("value", 0)),
                         bool(b.get("accent", False))))
        else:
            # tuple / list
            label = b[0]
            value = float(b[1])
            accent = bool(b[2]) if len(b) > 2 else False
            norm.append((label, value, accent))

    # Resolve theme colours lazily so callers can pass any RGBColor but we
    # still fall back to Feinschliff defaults when they pass None.
    fill_color = fill_color if fill_color is not None else T.INK
    accent_color = accent_color if accent_color is not None else T.ACCENT
    label_color = label_color if label_color is not None else T.BLACK
    value_color = value_color if value_color is not None else T.BLACK
    hairline_color = hairline_color if hairline_color is not None else T.FOG

    # Bar-area (the coloured fill region) sits between the label column and
    # the value column. Widths derived from w_px so the component scales if
    # the caller hands us a narrower box than the default content area.
    bar_x = x_px + label_w_px + LABEL_GAP_PX
    value_x = x_px + w_px - value_w_px
    bar_area_w = max(0, value_x - bar_x - VALUE_GAP_PX)

    for i, (label, value, accent) in enumerate(norm):
        row_y = y_px + i * row_spacing_px

        # Centre the bar vertically inside the row so label + value can sit
        # in a taller band without visual drift.
        bar_y = row_y + (row_spacing_px - bar_h_px) // 2 - 8  # -8 nudges row up to leave hairline breathing room

        # Bar fill — proportional to value (clamped 0..100).
        pct = max(0.0, min(100.0, value))
        fill_w = int(round(bar_area_w * (pct / 100.0)))
        if fill_w > 0:
            add_rect(
                target, bar_x, bar_y, fill_w, bar_h_px,
                fill=(accent_color if accent else fill_color),
            )

        # Divider hairline — at the bottom of the row, full width of the bbox.
        hairline_y = row_y + row_spacing_px - HAIRLINE_PX
        add_line(target, x_px, hairline_y, w_px, HAIRLINE_PX, hairline_color)
