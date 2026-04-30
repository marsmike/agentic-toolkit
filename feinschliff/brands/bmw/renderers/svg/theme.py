"""Feinschliff theme — derived from `brands/feinschliff/tokens.json` (DTCG 1.0).

`tokens.json` is the single source of truth (renderer-protocol.md). This
module reads it once at import time and exposes the tokens in the shape
the SVG renderer expects: hex strings usable directly as `fill=`/`stroke=`
attributes, px ints for font-size (SVG speaks CSS px natively), and font
family strings for `font-family=`.

Keep this module as a pure projection of tokens.json — never hard-code
values that exist in the JSON. Mirrors `brands/feinschliff/renderers/pptx/theme.py`
minus the RGBColor wrapper (SVG uses hex strings directly) and minus the
pt conversion (SVG uses CSS px natively — no `pt_from_px`).
"""
from __future__ import annotations

import json
from pathlib import Path

_TOKENS_PATH = Path(__file__).resolve().parents[2] / "tokens.json"


def _load_tokens() -> dict:
    with _TOKENS_PATH.open() as f:
        return json.load(f)


def _px_to_int(px_str: str) -> int:
    return int(px_str.rstrip("px"))


_TOKENS = _load_tokens()

# ─── Colors ────────────────────────────────────────────────────────────────
# HEX: DTCG keys (with dashes projected to snake_case) → full "#RRGGBB"
# strings ready to drop into SVG attributes. Also exported as uppercase
# module-level constants (e.g. theme.ACCENT) for ergonomic in-code use.
HEX: dict[str, str] = {
    key.replace("-", "_"): token["$value"].upper()
    for key, token in _TOKENS["color"].items()
    if not key.startswith("$")
}

for _key, _hex in HEX.items():
    globals()[_key.upper()] = _hex

# ─── Typography ────────────────────────────────────────────────────────────
# SVG consumes a CSS-ish font-family string, so we ship the whole fallback
# stack quoted. `FONT_DISPLAY_PRIMARY` is just the first family — useful
# when constructing the wordmark or referencing Noto Sans weights by name.
def _css_font_stack(families: list[str]) -> str:
    parts = []
    for fam in families:
        # Quote families with spaces; leave generic keywords bare.
        if " " in fam and fam not in ("sans-serif", "serif", "monospace"):
            parts.append(f'"{fam}"')
        else:
            parts.append(fam)
    return ", ".join(parts)


FONT_DISPLAY: str = _css_font_stack(_TOKENS["font-family"]["display"]["$value"])
FONT_MONO:    str = _css_font_stack(_TOKENS["font-family"]["mono"]["$value"])
FONT_DISPLAY_PRIMARY: str = _TOKENS["font-family"]["display"]["$value"][0]
FONT_MONO_PRIMARY:    str = _TOKENS["font-family"]["mono"]["$value"][0]

# ─── Size scale (CSS px) ───────────────────────────────────────────────────
SIZE_PX: dict[str, int] = {
    key.replace("-", "_"): _px_to_int(token["$value"])
    for key, token in _TOKENS["font-size"].items()
    if not key.startswith("$")
}

# ─── Weights ───────────────────────────────────────────────────────────────
# SVG accepts numeric font-weight directly.
WEIGHT: dict[str, int] = {
    key: token["$value"]
    for key, token in _TOKENS["font-weight"].items()
    if not key.startswith("$")
}
