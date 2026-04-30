"""Slide chrome — logo, page-meta, footer, slide-number, Binance-signature primitives.

Chrome lives on the **master** so every layout / slide inherits it for free.
Only the pgmeta text and the slide-number value change per slide; those are
wired as placeholders.

Three Binance-signature primitives live here (the brand-elevation chrome,
analogous to BMW's `add_m_stripe`, Spotify's `add_equalizer_marker` /
`add_pill_link`, Ferrari's `add_livery_band`):

  * `add_signup_pill`     — yellow pill CTA (radius=9999), the iconic
                            "Sign Up" / "Join Now" / "Get the App" shape.
                            Reserved for top-of-page "this is THE action"
                            moments. One pill per layout, max.
  * `add_ticker_row`      — single 5-column markets row (coin disc / pair
                            symbol / price / 24h % / chevron). The
                            product-DNA chrome — same role in the deck as
                            Spotify's album-art tile.
  * `add_arena_gradient`  — vertical yellow→dark linear-gradient band, the
                            Futures Arena product-launch hero treatment.

Plus:
  * `add_hairline`        — 1px brightness-step divider on dark surfaces
                            (`fog` / `#2B3139`, same hex as the elevated
                            card surface — borders feel like surface steps,
                            not ink lines).
  * `add_section_marker`  — yellow ▌ left-rule, replaces M-stripe role at
                            chapter dividers.
"""
from __future__ import annotations

from pathlib import Path

from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu
from pptx.dml.color import RGBColor
from lxml import etree
from pptx.oxml.ns import qn

import theme as T
from geometry import px, pt_from_px, LOGO_X_PX, LOGO_Y_PX, LOGO_H_PX
from components.primitives import add_text, add_rect, add_rounded_rect, _shapes

ASSETS = Path(__file__).resolve().parent.parent / "assets"

WORDMARK_TEXT = "BINANCE"

# Generic 4-segment diamond/pinwheel abstraction of the Binance brand mark —
# four right-angle triangles arranged around a hollow centre to read as a
# rotated square / 4-pointed pinwheel. Drawn as four independent triangles
# (not one freeform) so each segment renders as a crisp filled wedge.
#
# Coordinates are in a 0..100 viewBox, centred on (50, 50). The triangles
# point outward (N / E / S / W) and stop short of the centre to leave the
# characteristic hollow square.
#
# This is a brand-evoking abstraction, NOT the licensed Binance asset.
_DIAMOND_TRIANGLES = [
    [(50,  6), (78, 34), (50, 34)],   # N wedge
    [(94, 50), (66, 22), (66, 50)],   # E wedge
    [(50, 94), (22, 66), (50, 66)],   # S wedge
    [( 6, 50), (34, 78), (34, 50)],   # W wedge
]
_DIAMOND_VB_SIZE = 100
_DIAMOND_PX = 28  # Render size on the slide.


def _sp_name(sp) -> str:
    nvSpPr = sp.find(qn("p:nvSpPr"))
    if nvSpPr is not None:
        cNvPr = nvSpPr.find(qn("p:cNvPr"))
        if cNvPr is not None:
            return cNvPr.get("name", "")
    return ""


def _add_diamond(target, *, x_px: float, y_px: float, size_px: float, color: RGBColor):
    """Draw the Binance-evoking diamond glyph as four filled triangles.

    Generic 4-segment pinwheel/diamond — abstracts the four-rhombus Binance
    mark without copying the licensed geometry. Each wedge is its own shape
    so the hollow centre stays crisp at all render sizes.
    """
    s = size_px / _DIAMOND_VB_SIZE
    last_shape = None
    for tri in _DIAMOND_TRIANGLES:
        pts = [(x_px + p[0] * s, y_px + p[1] * s) for p in tri]
        head, *tail = pts
        builder = _shapes(target).build_freeform(px(head[0]), px(head[1]), scale=1)
        builder.add_line_segments([(px(x), px(y)) for x, y in tail], close=True)
        shape = builder.convert_to_shape()
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.fill.background()
        last_shape = shape
    return last_shape


def add_logo(target, *, variant: str = "dark"):
    """Place the Binance lockup (diamond glyph + wordmark) at top-left.

    Binance reads as a dark-first brand: the canvas across the deck is the
    deep crypto-black surface, so the wordmark renders in **Binance Yellow**
    by default per DESIGN.md ("the wordmark uses {colors.primary} for
    'BINANCE' type"). The diamond glyph also stays yellow — that's the
    brand mark.

    On the single light-canvas surface (the closing footer-reset band on
    `end`) the wordmark flips to pure ink (`T.INK = #0B0E11`) for contrast
    — pass `variant="ink"` for that. On the yellow-on-yellow Arena gradient
    transition the glyph flips to ink so it reads against the yellow upper
    band — pass `variant="accent"`.
    """
    if variant == "ink":
        # Light footer-reset band: yellow→black would lose contrast, so the
        # whole lockup flips to pure ink.
        glyph_color = T.INK
        text_color  = T.INK
    elif variant == "accent":
        # Yellow canvas (Arena gradient upper band): glyph flips to ink for
        # contrast; wordmark stays in ink.
        glyph_color = T.INK
        text_color  = T.INK
    else:
        # Default dark canvas — yellow glyph + yellow wordmark, the iconic
        # Binance lockup register.
        glyph_color = T.ACCENT
        text_color  = T.ACCENT

    _add_diamond(target, x_px=LOGO_X_PX, y_px=LOGO_Y_PX + 4, size_px=_DIAMOND_PX, color=glyph_color)
    return add_text(
        target,
        LOGO_X_PX + _DIAMOND_PX + 14, LOGO_Y_PX + 4,
        320, max(LOGO_H_PX, 28),
        WORDMARK_TEXT,
        size_px=22,
        weight="bold",
        font=T.FONT_DISPLAY,
        color=text_color,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
        uppercase=True,
    )


def add_pgmeta(master_or_slide, text: str = "BINANCE · 2026", *, color=None):
    """Page-meta stamp at top-right — UPPERCASE 1.4px-tracked label voice."""
    color = color if color is not None else T.SILVER
    return add_text(
        master_or_slide, 1420, 80, 420, 28, text,
        size_px=T.SIZE_PX["pgmeta"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=color, align=PP_ALIGN.RIGHT,
        uppercase=True, tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )


def add_footer_left(master_or_slide, text: str = "JAN 2026 · SHOWCASE", *, color=None):
    """Footer-left — date / classification."""
    color = color if color is not None else T.SILVER
    return add_text(
        master_or_slide, 120, 1030, 700, 24, text,
        size_px=T.SIZE_PX["footer"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=color,
        uppercase=True, tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )


def add_footer_right(master_or_slide, text: str, *, color=None):
    """Footer-right — slide number / total."""
    color = color if color is not None else T.SILVER
    return add_text(
        master_or_slide, 1100, 1030, 700, 24, text,
        size_px=T.SIZE_PX["footer"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=color, align=PP_ALIGN.RIGHT,
        uppercase=True, tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )


def paint_chrome(target, *, variant: str = "dark",
                 pgmeta: str = "BINANCE · 2026",
                 footer_left: str = "JAN 2026 · SHOWCASE",
                 total: int | None = None):
    """Paint full chrome (logo + pgmeta + footer) onto a layout or slide.

    The footer-right is a live slide-number field: PowerPoint auto-fills the
    current slide index. Pass `total` to render "SLIDE 1 / N" instead of
    "SLIDE 1".

    `variant`:
      * "dark"   — default. Yellow lockup, silver chrome on dark canvas.
      * "ink"    — light footer-reset surface (closing band on `end`). Ink
                   lockup, ink chrome.
      * "accent" — Arena-gradient upper-yellow band. Ink lockup; chrome
                   reads ink-on-yellow.
    """
    # Chrome ink reads silver on dark, near-ink on light/accent.
    if variant == "ink":
        chrome_color = T.INK
    elif variant == "accent":
        chrome_color = T.INK
    else:
        chrome_color = T.SILVER

    add_logo(target, variant=variant)
    add_pgmeta(target, pgmeta, color=chrome_color)
    add_footer_left(target, footer_left, color=chrome_color)
    tb = add_footer_right(target, "SLIDE ", color=chrome_color)
    _append_slide_num_field(tb, total=total, color=chrome_color)


def _append_slide_num_field(tb, *, total: int | None, color):
    """Replace the text frame's runs with "SLIDE <fld> [/ N]" so PowerPoint
    renders the live slide number — UPPERCASE 600 1.4px-tracked label voice
    in BinanceNova (FONT_DISPLAY)."""
    tf = tb.text_frame
    p = tf.paragraphs[0]
    for r in list(p._p):
        if r.tag in (qn("a:r"), qn("a:fld")):
            p._p.remove(r)

    tracking_em = float(T.CHIP_RULE.get("tracking-em", 0.1))

    def _rPr(el):
        rPr = etree.SubElement(el, qn("a:rPr"))
        rPr.set("lang", "en-US")
        rPr.set("dirty", "0")
        rPr.set("sz", str(int(T.SIZE_PX["footer"] * 0.5 * 100)))
        rPr.set("b",  "0")
        rPr.set("spc", str(int(round(tracking_em * (T.SIZE_PX["footer"] * 0.5) * 100))))
        fill = etree.SubElement(rPr, qn("a:solidFill"))
        srgb = etree.SubElement(fill, qn("a:srgbClr"))
        srgb.set("val", "{:02X}{:02X}{:02X}".format(*color))
        latin = etree.SubElement(rPr, qn("a:latin"))
        latin.set("typeface", T.FONT_DISPLAY + " SemiBold")
        return rPr

    # "Slide "
    r1 = etree.SubElement(p._p, qn("a:r"))
    _rPr(r1)
    t1 = etree.SubElement(r1, qn("a:t"))
    t1.text = "SLIDE "

    # <fld type="slidenum">1</fld>
    fld = etree.SubElement(p._p, qn("a:fld"))
    fld.set("id", "{A1B2C3D4-E5F6-4890-ABCD-EF0123456789}")
    fld.set("type", "slidenum")
    _rPr(fld)
    tF = etree.SubElement(fld, qn("a:t"))
    tF.text = "1"

    if total is not None:
        r2 = etree.SubElement(p._p, qn("a:r"))
        _rPr(r2)
        t2 = etree.SubElement(r2, qn("a:t"))
        t2.text = f" / {total:02d}"


# ─── Binance-signature primitives (per DESIGN.md) ──────────────────────────

def add_signup_pill(target, x_px: float, y_px: float,
                    label: str = "Sign Up", *,
                    w_px: float = 240, h_px: float = 72,
                    variant: str = "primary"):
    """Binance's iconic top-of-page CTA — yellow pill, black bold uppercase
    label, 1.4px tracking. The "this is THE action" shape, reserved for
    cover / chapter / end slides per DESIGN.md `button-primary-pill`.

    `variant`:
      * "primary" — Binance Yellow fill, ink label (default).
      * "ink"     — surface-card-dark fill, off-white label. Used as the
                    secondary CTA next to a primary pill.
    """
    fills        = {"primary": T.ACCENT,         "ink": T.PAPER}
    label_colors = {"primary": T.INK,            "ink": T.OFF_WHITE}
    fill        = fills.get(variant, T.ACCENT)
    label_color = label_colors.get(variant, T.INK)

    add_rounded_rect(
        target, x_px, y_px, w_px, h_px,
        radius_px=T.RADIUS["pill"],
        fill=fill,
    )
    return add_text(
        target,
        x_px, y_px, w_px, h_px,
        label,
        size_px=T.SIZE_PX["btn"],
        weight="semibold",
        font=T.FONT_DISPLAY,
        color=label_color,
        align=PP_ALIGN.CENTER,
        anchor=MSO_ANCHOR.MIDDLE,
        uppercase=True,
        tracking_em=float(T.CHIP_RULE.get("tracking-em", 0.1)),
    )


def add_section_marker(target, x_px: float, y_px: float, h_px: float,
                       *, w_px: float | None = None, color: RGBColor | None = None):
    """Yellow ▌ left-rule — an 8px vertical bar in Binance Yellow set flush
    to a chapter / hero headline. Replaces BMW's `add_m_stripe` role and
    Spotify's `add_equalizer_marker` role at chapter dividers and major
    editorial breaks. Reads as the trading-pane "active row" indicator.

    `h_px` matches the headline cap-height (~ 0.7-0.85 × font-size). Default
    width is 8px per `tokens.json` `section-marker.bar-width`.
    """
    if w_px is None:
        w_px = float(T.SECTION_MARKER.get("bar-width", "8px").rstrip("px"))
    color = color if color is not None else T.ACCENT
    return add_rect(target, x_px, y_px, w_px, h_px, fill=color)


def add_hairline(target, x_px: float, y_px: float, w_px: float,
                 *, color: RGBColor | None = None):
    """1px brightness-step divider on dark surfaces — `fog` / `#2B3139`.

    Per DESIGN.md the hairline-on-dark token is the same hex as the
    elevated card surface, so the divider feels like a surface step rather
    than an ink line. Use between markets-row / FAQ-row / table rows.
    """
    color = color if color is not None else T.FOG
    return add_rect(target, x_px, y_px, w_px, 1, fill=color)


def add_ticker_row(target, x_px: float, y_px: float, w_px: float,
                   *, symbol: str = "BTC/USDT",
                   icon_letter: str | None = None,
                   icon_color: RGBColor | None = None,
                   price: str = "79065.04",
                   change_pct: str = "+0.45%",
                   direction: str = "up",
                   show_hairline: bool = True):
    """Single 5-column markets row — the Binance product-DNA chrome.

    Geometry (column widths chosen to read at 1920×1080 deck density):

        [icon 56] [pair 220] [price right-aligned 240] [Δ% right-aligned 180] [chevron 40]

    `direction` selects the trading-up / trading-down colour for the Δ%
    cell and the ▲/▼ glyph that prefixes it. "neutral" suppresses the glyph
    and uses muted silver — for placeholder / loading rows.

    `show_hairline=True` draws a 1px `fog` divider 56px below the row's top
    so consecutive rows stack visually. The caller is responsible for
    spacing rows by the row pitch (commonly 56-72px).
    """
    row_h = 56  # px — matches `markets-row` 12px vertical padding × 2 + 32px content

    # 1. Coin disc — 32×32 colored circle with a single ink letter inside.
    icon_letter = icon_letter if icon_letter is not None else symbol[:1]
    icon_color  = icon_color  if icon_color  is not None else T.ACCENT
    icon_size   = 32
    icon_x      = x_px
    icon_y      = y_px + (row_h - icon_size) / 2
    disc = _shapes(target).add_shape(
        MSO_SHAPE.OVAL,
        px(icon_x), px(icon_y), px(icon_size), px(icon_size),
    )
    disc.fill.solid()
    disc.fill.fore_color.rgb = icon_color
    disc.line.fill.background()
    disc.shadow.inherit = False
    add_text(
        target, icon_x, icon_y, icon_size, icon_size,
        icon_letter.upper(),
        size_px=14, weight="bold", font=T.FONT_DISPLAY,
        color=T.INK, align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
    )

    # 2. Pair symbol — BinanceNova 600 left-aligned.
    pair_x = icon_x + icon_size + 14
    pair_w = 220
    add_text(
        target, pair_x, y_px, pair_w, row_h,
        symbol,
        size_px=T.SIZE_PX["ticker_pair"],
        weight="semibold", font=T.FONT_DISPLAY,
        color=T.OFF_WHITE,
        anchor=MSO_ANCHOR.MIDDLE,
    )

    # 3. Price — BinancePlex 600 right-aligned, negative tracking for the
    # "tabular and reliable" voice.
    price_w = 240
    price_x = x_px + w_px - 40 - 180 - price_w  # 40 chevron, 180 Δ%, then price
    add_text(
        target, price_x, y_px, price_w, row_h,
        price,
        size_px=T.SIZE_PX["ticker_price"],
        weight="semibold", font=T.FONT_MONO,
        color=T.OFF_WHITE,
        align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE,
        tracking_em=-0.01,
    )

    # 4. Δ% cell — BinancePlex 500, coloured green/red, prefixed with ▲/▼.
    pct_w = 180
    pct_x = x_px + w_px - 40 - pct_w
    direction_glyphs = {"up": "▲ ", "down": "▼ ", "neutral": ""}
    direction_colors = {"up": T.TRADING_UP, "down": T.TRADING_DOWN, "neutral": T.SILVER}
    glyph = direction_glyphs.get(direction, "")
    pct_color = direction_colors.get(direction, T.SILVER)
    add_text(
        target, pct_x, y_px, pct_w, row_h,
        f"{glyph}{change_pct}",
        size_px=T.SIZE_PX["ticker_pct"],
        weight="medium", font=T.FONT_MONO,
        color=pct_color,
        align=PP_ALIGN.RIGHT, anchor=MSO_ANCHOR.MIDDLE,
    )

    # 5. Right chevron — muted silver, indicates "view detail".
    chev_x = x_px + w_px - 40
    add_text(
        target, chev_x, y_px, 40, row_h,
        "›",
        size_px=24, weight="regular", font=T.FONT_DISPLAY,
        color=T.SILVER,
        align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE,
    )

    # 6. Hairline divider below the row.
    if show_hairline:
        add_hairline(target, x_px, y_px + row_h, w_px)

    return row_h


def add_arena_gradient(target, x_px: float, y_px: float,
                       w_px: float, h_px: float):
    """Vertical yellow→dark linear-gradient band — the Futures Arena
    product-launch hero treatment per DESIGN.md `arena-hero-gradient`.

    A single GradientFillFormat-driven shape; from `accent` (top, 100%) to
    `surface-dark` (bottom, 100%). Used scarcely — one slide per deck.

    Implementation: build the gradient stops directly in OOXML because
    python-pptx's `GradientStop` API does not expose explicit stop colours
    — we need both the angle AND the brand-correct hex pair.
    """
    from lxml import etree
    from pptx.oxml.ns import qn

    band = _shapes(target).add_shape(
        MSO_SHAPE.RECTANGLE, px(x_px), px(y_px), px(w_px), px(h_px),
    )
    band.line.fill.background()
    band.shadow.inherit = False

    spPr = band._element.spPr
    # Remove any existing fill so our gradFill is the only one.
    A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
    for tag in ("solidFill", "noFill", "gradFill", "blipFill", "pattFill"):
        for el in spPr.findall(qn(f"a:{tag}")):
            spPr.remove(el)

    grad = etree.SubElement(spPr, qn("a:gradFill"))
    grad.set("flip", "none")
    grad.set("rotWithShape", "1")
    gsLst = etree.SubElement(grad, qn("a:gsLst"))

    def _stop(pos: int, hex_value: str):
        gs = etree.SubElement(gsLst, qn("a:gs"))
        gs.set("pos", str(pos))
        srgb = etree.SubElement(gs, qn("a:srgbClr"))
        srgb.set("val", hex_value)

    # Yellow at top, surface-dark at bottom.
    _stop(0,      T.HEX["accent"])
    _stop(100000, T.HEX["surface_dark"])

    # Linear gradient, 90° (top → bottom).
    lin = etree.SubElement(grad, qn("a:lin"))
    lin.set("ang", "5400000")  # 90° in OOXML 60000-units
    lin.set("scaled", "1")

    # Move the band element to the back of the spTree so it doesn't cover chrome.
    spTree = band._element.getparent()
    spTree.remove(band._element)
    # Re-insert just after the grpSpPr (first painted element).
    grp = spTree.find(qn("p:grpSpPr"))
    if grp is not None:
        idx = list(spTree).index(grp) + 1
        spTree.insert(idx, band._element)
    else:
        spTree.insert(0, band._element)

    return band
