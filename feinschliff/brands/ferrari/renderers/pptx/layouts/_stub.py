"""Universal stub renderer — emits a legible, on-brand slide for any
`data-slots` schema, without the layout's bespoke visual design.

Purpose: lets /deck use every catalog entry (including MCK layouts that
haven't had /extend hand-tuning yet). A stub will look correct and branded
but not McKinsey-pretty — enough for a manager to see their content in
place. Replace with a hand-written layout via /extend when visual fidelity
matters (charts, Venn, Gantt, Funnel, etc.).

Idx allocation (mirrors conventions in existing layouts):
    0      title                       mandatory
    10     eyebrow / short top label   optional
    11-19  scalar body slots           in declaration order
    20+i*N array-item fields           N = min(len(item.properties), 4)
    40     trailing scalar (caption/legend/attribution/source)
    80+    picture placeholders        one per `format: path` slot
"""
from __future__ import annotations

import theme as T
from components import (
    add_text_placeholder, add_picture_placeholder,
    paint_chrome, set_layout_background, set_layout_name,
)
from layouts._shared import content_header

# Canvas: 1920 × 1080, content area below the header.
CONTENT_X = 100
CONTENT_W = 1720
CONTENT_Y = 460  # below content_header stack
CONTENT_H = 560

# Slot names chrome already paints — never emit placeholders for these.
CHROME_SLOTS = {"logo", "pgmeta", "tracker"}

# Slot names that belong in the footer (mono, trailing).
TRAILING_SLOTS = {
    "caption", "legend", "legend_title", "legend_body",
    "attribution", "source", "note", "focus_note", "axis_label",
}


def plan_placeholders(slots_schema: dict) -> dict[str, int]:
    """Pure: compute the placeholder_map a stub would emit for this schema.

    compile.py --apply calls this to populate the catalog's placeholder_map
    without having to actually render a layout. The stub engine uses the
    same logic so the catalog and renderer stay in lockstep.
    """
    pmap: dict[str, int] = {}
    title_key = _first_key(slots_schema, ("title", "action_title", "headline"))
    eyebrow_key = _first_key(slots_schema, ("eyebrow", "kicker"))
    if title_key:
        pmap[title_key] = 0
        if eyebrow_key:
            pmap[eyebrow_key] = 10

    scalar_idx = 11
    trailing_idx = 40
    picture_idx = 80

    for key, spec in slots_schema.items():
        if key in CHROME_SLOTS or key == title_key or key == eyebrow_key:
            continue
        stype = spec.get("type", "string")
        if stype == "array":
            continue  # handled below
        if stype == "string" and spec.get("format") == "path":
            pmap[key] = picture_idx
            picture_idx += 1
        elif key in TRAILING_SLOTS:
            pmap[key] = trailing_idx
            trailing_idx += 1
        else:
            if scalar_idx > 19:
                continue  # overflow buffer; dropped on purpose
            pmap[key] = scalar_idx
            scalar_idx += 1

    # Array items — 4 fields per item, base = 20 + i*4.
    for key, spec in slots_schema.items():
        if key in CHROME_SLOTS or key == title_key or key == eyebrow_key:
            continue
        if spec.get("type") != "array":
            continue
        items_spec = spec.get("items", {})
        properties = list(items_spec.get("properties", {}).keys())[:4]
        if not properties:
            continue
        min_items = spec.get("minItems", 3)
        max_items = spec.get("maxItems", 6)
        n = min(max_items, max(min_items, 4))
        for i in range(n):
            for j, field in enumerate(properties):
                pmap[f"{key}[{i}].{field}"] = 20 + i * 4 + j
    return pmap


def emit_stub_layout(
    layout,
    *,
    name: str,
    slots_schema: dict,
    eyebrow_prompt: str = "",
    title_prompt: str = "",
    bg: str = "white",
    pgmeta: str = "Layout",
) -> dict[str, int]:
    """Render a stub layout. Returns the placeholder_map it emitted.

    The returned map is exactly what the catalog should record so the
    catalog and renderer never drift. compile.py --apply uses this.
    """
    set_layout_name(layout, name)
    set_layout_background(layout, T.HEX[bg])
    variant = "dark" if bg == "ink" else "light"
    paint_chrome(layout, variant=variant, pgmeta=pgmeta)

    # Derive title + eyebrow hook from schema (may be absent on title-only
    # layouts where the title is called action_title or similar).
    title_key = _first_key(slots_schema, ("title", "action_title", "headline"))
    eyebrow_key = _first_key(slots_schema, ("eyebrow", "kicker"))

    pmap: dict[str, int] = {}

    if title_key:
        content_header(layout, eyebrow=eyebrow_prompt, title=title_prompt)
        pmap[title_key] = 0
        if eyebrow_key:
            pmap[eyebrow_key] = 10

    # Partition remaining slots.
    scalar_idx = 11
    trailing_idx = 40
    picture_idx = 80
    array_slots: list[tuple[str, dict]] = []
    scalar_body_slots: list[tuple[str, dict]] = []
    trailing_scalar_slots: list[tuple[str, dict]] = []
    picture_slots: list[tuple[str, dict]] = []

    for key, spec in slots_schema.items():
        if key in CHROME_SLOTS or key == title_key or key == eyebrow_key:
            continue
        stype = spec.get("type", "string")
        if stype == "array":
            array_slots.append((key, spec))
        elif stype == "string" and spec.get("format") == "path":
            picture_slots.append((key, spec))
        elif key in TRAILING_SLOTS:
            trailing_scalar_slots.append((key, spec))
        else:
            scalar_body_slots.append((key, spec))

    # Scalar body slots — stacked vertically in the top of the content area.
    y = CONTENT_Y
    for key, spec in scalar_body_slots:
        add_text_placeholder(
            layout, idx=scalar_idx, name=key.title(), ph_type="body",
            x_px=CONTENT_X, y_px=y, w_px=CONTENT_W, h_px=60,
            prompt_text=f"[{key}]",
            size_px=T.SIZE_PX.get("body", 26),
            color=T.GRAPHITE, line_height=1.4,
        )
        pmap[key] = scalar_idx
        scalar_idx += 1
        y += 72
        if scalar_idx > 19:
            break  # buffer zone; anything more goes in arrays or trailing

    # Picture slots — right half of canvas.
    for key, spec in picture_slots:
        add_picture_placeholder(
            layout, idx=picture_idx, name=key.title(),
            x_px=1020, y_px=CONTENT_Y, w_px=800, h_px=CONTENT_H,
        )
        pmap[key] = picture_idx
        picture_idx += 1

    # Array slots — take the remaining vertical space.
    array_y0 = y if scalar_body_slots else CONTENT_Y
    array_h = CONTENT_Y + CONTENT_H - array_y0
    if array_slots:
        if len(array_slots) == 1:
            key, spec = array_slots[0]
            _emit_array(layout, pmap, key, spec, y0=array_y0, h=array_h)
        else:
            row_h = array_h // len(array_slots) - 16
            for i, (key, spec) in enumerate(array_slots):
                _emit_array(layout, pmap, key, spec,
                            y0=array_y0 + i * (row_h + 16), h=row_h)

    # Trailing scalar slots — mono line(s) near the bottom.
    ty = 1000
    for key, spec in trailing_scalar_slots:
        add_text_placeholder(
            layout, idx=trailing_idx, name=key.title(), ph_type="body",
            x_px=CONTENT_X, y_px=ty, w_px=CONTENT_W, h_px=30,
            prompt_text=f"[{key}]",
            size_px=14, weight="bold", font=T.FONT_DISPLAY,
            color=T.GRAPHITE, uppercase=True, tracking_em=0.1,
        )
        pmap[key] = trailing_idx
        trailing_idx += 1
        ty -= 32

    return pmap


def _emit_array(layout, pmap: dict, key: str, spec: dict, *, y0: int, h: int) -> None:
    """Repeat item placeholders — horizontal row if items ≤ 4, vertical list otherwise.

    Each item gets up to 4 stacked placeholders (one per property), idx
    base = 20 + item_index * 4 + slot_offset.
    """
    items_spec = spec.get("items", {})
    properties = items_spec.get("properties", {})
    fields = list(properties.keys())[:4]
    if not fields:
        return

    min_items = spec.get("minItems", 3)
    max_items = spec.get("maxItems", 6)
    # Pick a reasonable sample count for the prompt-text template (master
    # carries N placeholders; users fill what they need).
    n = min(max_items, max(min_items, 4))

    horizontal = n <= 4
    if horizontal:
        gap = 48
        item_w = (CONTENT_W - gap * (n - 1)) // n
        for i in range(n):
            x = CONTENT_X + i * (item_w + gap)
            _emit_item_placeholders(layout, pmap, key, i, fields,
                                     x=x, y=y0, w=item_w, h=h)
    else:
        row_h = max(48, min(h // n, 80))
        for i in range(n):
            y = y0 + i * row_h
            _emit_item_placeholders(layout, pmap, key, i, fields,
                                     x=CONTENT_X, y=y, w=CONTENT_W, h=row_h - 8,
                                     compact=True)


def _emit_item_placeholders(
    layout, pmap: dict, key: str, item_idx: int, fields: list[str],
    *, x: int, y: int, w: int, h: int, compact: bool = False,
) -> None:
    idx_base = 20 + item_idx * 4
    n_fields = len(fields)
    if compact:
        # Single-row compact: split width by field.
        field_w = (w - 16 * (n_fields - 1)) // n_fields
        for j, field in enumerate(fields):
            fx = x + j * (field_w + 16)
            _emit_field(layout, pmap, key, item_idx, field,
                        idx=idx_base + j,
                        x=fx, y=y, w=field_w, h=h,
                        style="compact")
    else:
        # Stacked per-item: first field at top (small mono), then title,
        # then body fills the rest.
        sections = _split_item_height(h, n_fields)
        sy = y
        for j, field in enumerate(fields):
            sh = sections[j]
            style = _style_for_pos(j, n_fields)
            _emit_field(layout, pmap, key, item_idx, field,
                        idx=idx_base + j, x=x, y=sy, w=w, h=sh,
                        style=style)
            sy += sh


def _split_item_height(h: int, n: int) -> list[int]:
    """Divide an item's vertical space into n bands: thin top, taller middle, thinner bottom."""
    if n == 1:
        return [h]
    if n == 2:
        return [40, h - 40]
    if n == 3:
        return [40, h - 120, 80]
    # n == 4
    return [40, max(120, (h - 120) // 2), max(120, (h - 120) // 2), 60]


def _style_for_pos(pos: int, total: int) -> str:
    if pos == 0 and total > 1:
        return "tag"
    if pos == 1 and total > 2:
        return "title"
    if pos == total - 1 and total > 2:
        return "meta"
    return "body"


def _emit_field(
    layout, pmap: dict, key: str, item_idx: int, field: str,
    *, idx: int, x: int, y: int, w: int, h: int, style: str,
) -> None:
    kwargs = {
        "tag":     dict(size_px=14, weight="bold", font=T.FONT_DISPLAY, color=T.ACCENT,
                        uppercase=True, tracking_em=0.1),
        "title":   dict(size_px=T.SIZE_PX.get("col_title", 36), weight="medium",
                        color=T.BLACK, tracking_em=-0.012, line_height=1.15),
        "body":    dict(size_px=T.SIZE_PX.get("col_body", 20),
                        color=T.GRAPHITE, line_height=1.5),
        "meta":    dict(size_px=14, weight="bold", font=T.FONT_DISPLAY, color=T.GRAPHITE),
        "compact": dict(size_px=T.SIZE_PX.get("col_body", 20),
                        color=T.GRAPHITE, line_height=1.3),
    }[style]

    add_text_placeholder(
        layout, idx=idx, name=f"{key.title()} {item_idx+1} {field.title()}",
        ph_type="body",
        x_px=x, y_px=y, w_px=w, h_px=h,
        prompt_text=f"[{key}[{item_idx}].{field}]",
        **kwargs,
    )
    pmap[f"{key}[{item_idx}].{field}"] = idx


def _first_key(schema: dict, candidates: tuple[str, ...]) -> str | None:
    for c in candidates:
        if c in schema:
            return c
    return None
