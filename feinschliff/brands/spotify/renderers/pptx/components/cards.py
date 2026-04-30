"""Card & list components — content column, card, agenda row."""
from __future__ import annotations

from pptx.dml.color import RGBColor

import theme as T
from components.primitives import add_rect, add_rounded_rect, add_line, add_text


def add_column(
    target,
    x_px: float,
    y_px: float,
    w_px: float,
    *,
    number: str,
    title: str,
    body: str,
    as_card: bool = False,
    card_bg: RGBColor = T.PAPER,
    fg_title: RGBColor = T.BLACK,
    fg_body: RGBColor = T.GRAPHITE,
    number_color: RGBColor = T.ACCENT,
    title_size_px: float | None = None,
    height_px: float = 600,
    pad_px: float = 40,
):
    """A single content column (optionally wrapped in a Spotify rounded card).

    Spotify cards are 8px rounded with `rgba(0,0,0,0.3)` elevation shadow.
    The radius slot lives in `tokens.json` `radius.card`; the shadow comes
    from the `shadow` parameter on `add_rounded_rect`.
    """
    if as_card:
        add_rounded_rect(
            target, x_px, y_px, w_px, height_px,
            radius_px=T.RADIUS.get("card", 0),
            fill=card_bg,
            shadow="elevated",
        )
        inner_x = x_px + pad_px
        inner_w = w_px - 2 * pad_px
        cursor_y = y_px + pad_px
    else:
        inner_x = x_px
        inner_w = w_px
        cursor_y = y_px

    # Number label
    add_text(
        target, inner_x, cursor_y, inner_w, 30, number,
        size_px=T.SIZE_PX["col_num"], font=T.FONT_MONO,
        color=number_color, uppercase=True, tracking_em=0.12,
    )
    cursor_y += 44

    # Title
    add_text(
        target, inner_x, cursor_y, inner_w, 160, title,
        size_px=title_size_px or T.SIZE_PX["col_title"], weight="medium",
        color=fg_title, tracking_em=-0.012, line_height=1.15,
    )
    cursor_y += 160

    # Body
    add_text(
        target, inner_x, cursor_y, inner_w, 400, body,
        size_px=T.SIZE_PX["col_body"], color=fg_body, line_height=1.5,
    )


def add_agenda_row(
    target,
    y_px: float,
    number: str,
    title: str,
    description: str,
    *,
    x_px: float = 100,
    w_px: float = 860,
    number_color: RGBColor = T.ACCENT,
    title_color: RGBColor = T.BLACK,
    desc_color: RGBColor = T.GRAPHITE,
    rule_color: RGBColor = T.FOG,
):
    """A single agenda list row: hairline, number, title, description."""
    add_line(target, x_px, y_px, w_px, 1, rule_color)
    add_text(
        target, x_px, y_px + 14, 110, 30, number,
        size_px=T.SIZE_PX["agenda_num"], font=T.FONT_MONO,
        color=number_color, tracking_em=0.08,
    )
    add_text(
        target, x_px + 120, y_px + 10, w_px - 120, 40, title,
        size_px=T.SIZE_PX["agenda_t"], weight="medium",
        color=title_color, tracking_em=-0.01,
    )
    add_text(
        target, x_px + 120, y_px + 52, w_px - 120, 32, description,
        size_px=T.SIZE_PX["agenda_d"], color=desc_color,
    )
