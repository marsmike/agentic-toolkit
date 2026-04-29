"""Feinschliff theme — derived from `brands/feinschliff/tokens.json` (DTCG 1.0).

`tokens.json` is the single source of truth (renderer-protocol.md). This
module reads it once at import time and exposes the tokens in the shape
the PPTX renderer expects (RGBColor constants, HEX dict, SIZE_PX dict in
CSS px, font family strings, weight mapping).

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
