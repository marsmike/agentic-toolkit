"""BMW theme — derived from `brands/bmw/tokens.json` (DTCG 1.0).

`tokens.json` is the single source of truth (renderer-protocol.md). This
module reads it once at import time and exposes the tokens in the shape
the PPTX renderer expects (RGBColor constants, HEX dict, SIZE_PX dict in
CSS px, font family strings, weight mapping, and the BMW-specific policy
blocks: layout / cover / section-marker / photography / headline-rule /
chip-rule).

Keep this module as a pure projection of tokens.json — never hard-code
values that exist in the JSON. Fields used only by the PPTX renderer
(e.g. `pt_from_px` factor) live in `geometry.py`, not here.
"""
from __future__ import annotations

import json
from pathlib import Path

from pptx.dml.color import RGBColor

_TOKENS_PATH = Path(__file__).resolve().parents[2] / "tokens.json"


def _load_tokens() -> dict:
    with _TOKENS_PATH.open() as f:
        return json.load(f)


def _hex_to_rgb(hex_str: str) -> RGBColor:
    h = hex_str.lstrip("#")
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _px_to_int(px_str: str) -> int:
    return int(px_str.rstrip("px"))


def _maybe_px_to_int(value):
    """Coerce '4px' → 4, '4' → 4, 4 → 4. Used for policy blocks where the
    DTCG `dimension` type accepts either form."""
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value)
    return int(s.rstrip("px")) if s.rstrip("px").isdigit() else value


_TOKENS = _load_tokens()

# ─── Colors ────────────────────────────────────────────────────────────────
# HEX: DTCG keys (with dashes) → uppercase no-# hex, for OOXML theme injection.
# Module constants: uppercase snake_case → RGBColor, for in-code use.
HEX: dict[str, str] = {
    key.replace("-", "_"): token["$value"].lstrip("#").upper()
    for key, token in _TOKENS["color"].items()
    if not key.startswith("$")
}

for _key, _hex in HEX.items():
    globals()[_key.upper()] = _hex_to_rgb(_hex)

# ─── Typography ────────────────────────────────────────────────────────────
FONT_DISPLAY: str = _TOKENS["font-family"]["display"]["$value"][0]
FONT_MONO:    str = _TOKENS["font-family"]["mono"]["$value"][0]

# ─── Size scale (CSS px) ───────────────────────────────────────────────────
SIZE_PX: dict[str, int] = {
    key.replace("-", "_"): _px_to_int(token["$value"])
    for key, token in _TOKENS["font-size"].items()
    if not key.startswith("$")
}

# ─── Weights ───────────────────────────────────────────────────────────────
# python-pptx exposes bold=True only. Medium/Light are named variants so
# PowerPoint resolves to the correct installed Noto Sans TTF.
WEIGHT: dict[str, int] = {
    key: token["$value"]
    for key, token in _TOKENS["font-weight"].items()
    if not key.startswith("$")
}

# ─── Radius (CSS px → int) ─────────────────────────────────────────────────
# Read by `add_rounded_rect` and the component primitives. BMW sets every
# slot to 0 (rectangular IS the brand); Spotify sets `btn`/`chip`/`card` to
# pill / 8 to opt into rounded geometry without changing renderer code.
RADIUS: dict[str, int] = {
    key.replace("-", "_"): _px_to_int(token["$value"])
    for key, token in _TOKENS["radius"].items()
    if not key.startswith("$")
}


# ─── BMW policy blocks ─────────────────────────────────────────────────────
# Each policy block is a flat dict of literal values (or token-name refs).
# Layouts read from these to drive cover composition, section markers,
# photography placement, and the 700/300 type-weight contrast.

def _flatten_policy(block: dict) -> dict:
    """Project a `tokens.json` policy block (dict-of-{$value: x}) into a
    plain dict {key: x}, dropping `$description` / `$type` meta fields."""
    out = {}
    for key, entry in block.items():
        if key.startswith("$"):
            continue
        if isinstance(entry, dict) and "$value" in entry:
            out[key] = entry["$value"]
        else:
            out[key] = entry
    return out


LAYOUT:          dict = _flatten_policy(_TOKENS.get("layout", {}))
COVER:           dict = _flatten_policy(_TOKENS.get("cover", {}))
SECTION_MARKER:  dict = _flatten_policy(_TOKENS.get("section-marker", {}))
PHOTOGRAPHY:     dict = _flatten_policy(_TOKENS.get("photography", {}))
HEADLINE_RULE:   dict = _flatten_policy(_TOKENS.get("headline-rule", {}))
CHIP_RULE:       dict = _flatten_policy(_TOKENS.get("chip-rule", {}))

# Coerce dimension fields into ints for callers.
for _block in (LAYOUT, COVER, SECTION_MARKER):
    for _k, _v in list(_block.items()):
        if isinstance(_v, str) and _v.endswith("px"):
            _block[_k] = _px_to_int(_v)
        elif _k in ("height-px", "stripe-height", "grid-columns",
                    "model-grid-cols") and isinstance(_v, (str, int)):
            _block[_k] = int(_v)
