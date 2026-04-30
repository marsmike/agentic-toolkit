"""Ferrari theme — derived from `brands/ferrari/tokens.json` (DTCG 1.0).

`tokens.json` is the single source of truth (renderer-protocol.md). This
module reads it once at import time and exposes the tokens in the shape
the PPTX renderer expects (RGBColor constants, HEX dict, SIZE_PX dict in
CSS px, font family strings, weight mapping, and the Ferrari-specific
policy blocks: layout / cover / section-marker / photography /
headline-rule / chip-rule / shadow).

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
# Read by the component primitives. Ferrari sets every CTA / card / band
# slot to 0 (rectangular precision IS the brand) — only `chip` (badge-pill,
# the one place pill geometry is allowed) and form-input `sm` keep non-zero
# values. Same shape as BMW's radius block; opposite of Spotify's.
RADIUS: dict[str, int] = {
    key.replace("-", "_"): _px_to_int(token["$value"])
    for key, token in _TOKENS["radius"].items()
    if not key.startswith("$")
}


# ─── Ferrari policy blocks ─────────────────────────────────────────────────
# Each policy block is a flat dict of literal values (or token-name refs).
# Layouts read from these to drive Ferrari idioms — cinematic dark canvas,
# the Rosso Corsa livery band as section marker, the spec-cell number-display
# pattern for KPIs, and the 500/400/700 weight ladder (display-medium, never
# bold; bold reserved for buttons + component titles).

def _flatten_policy(block: dict) -> dict:
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
SHADOW:          dict = _flatten_policy(_TOKENS.get("shadow", {}))

# Coerce dimension fields that arrive as "96px" into ints for callers.
for _block in (LAYOUT, COVER, SECTION_MARKER):
    for _k, _v in list(_block.items()):
        if isinstance(_v, str) and _v.endswith("px"):
            _block[_k] = _px_to_int(_v)
