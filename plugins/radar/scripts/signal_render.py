"""Signal Radar: `signal.json` -> one self-contained HTML page, a short Obsidian note and two SVGs.

Every value already left `signal_radar.py`'s `build()`; this module only lays it out, so it makes
no network call and touches nothing outside its own return value. `render_html` embeds the data
verbatim as `<script type="application/json" id="data">` (escaping `</` so a fetched title can't
close the tag early) and leaves every render to the page's own inline JS — a polar radar scope,
a sortable signals table, the vault pulse and the knowledge-graph view. `render_md` is the
Obsidian note, which embeds `render_scope_svg` (the same scope, drawn here in Python) and
`render_momentum_svg` (the top signals' strength and 14-day trend): Obsidian cannot show an .html
file, but it shows an SVG inline.

Nothing here reaches the network or the filesystem except reading its own template next to it.
"""
from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path
from typing import Any

TEMPLATE = Path(__file__).resolve().parent / "signal_template.html"
MD_TOP_SIGNALS = 15
MD_TOP_EARLY = 8
MD_TOP_BLIND = 8
MD_TOP_TAGS = 8

STAGE_LABEL = {"new": "New", "rising": "Rising", "hot": "Hot", "steady": "Steady", "fading": "Fading"}
FAMILY_LABEL = {"hn": "Hacker News", "hf": "Hugging Face", "github": "GitHub", "reddit": "Reddit",
                "rss": "Blogs & news", "arxiv": "arXiv", "feed": "Reader feeds", "kagi": "Kagi news", "tavily": "Tavily web", "kagi_news": "Kagi News",
                "graph": "Knowledge graph", "vault": "Your vault"}
SCOPE_SVG = "Signal-Radar-scope.svg"
MOMENTUM_SVG = "Signal-Radar-momentum.svg"

# The page's colours (signal_template.html `--stage-*`, `--sec-*`), one mid-tone between each
# light/dark pair: Obsidian embeds the SVG as an <img>, which sees no CSS variable and no colour
# scheme, so every colour here has to read on a white note and on a near-black one alike.
STAGE_COLOR = {"new": "#6f62cf", "rising": "#e0703a", "hot": "#db5252", "steady": "#3180de", "fading": "#8a8a8a"}
SECTOR_COLORS = ("#3180de", "#e2612d", "#1aa675", "#bb8200", "#ce5886", "#26a126", "#6d5fc8")
INK = "#8a8a8a"  # text, rings and dividers: mid-grey, legible on both backgrounds without a halo
FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"


def render_html(data: dict[str, Any]) -> str:
    """The whole self-contained page: the template with `signal.json` dropped into it."""
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)


# ---- the two SVGs the note embeds ---------------------------------------------------------------
# The scope's geometry, dot spread and label placement are the page's own (signal_template.html,
# "the radar scope"), ported so the note and the page put every blip in the same place: same
# sectors in the same order, same rings, same fnv-keyed jitter. An SVG shown as an <img> has no
# script, no CSS variables and no colour scheme, so it is drawn once, in mid-tones, on no background.
CX, CY, R_MIN, R_MAX, W, H = 380, 320, 34, 272, 760, 660
PAD_X = 48  # the page clips a long sector label at the edge; the image widens its viewBox instead
BANDS = ((75, "Hot"), (55, "Rising"), (35, "Watch"), (0, "Faint"))
RING_CHARW, RING_LH = 6.4, 12
LABEL_SIZE, LABEL_CHARW, LABEL_LH, LABEL_GAP = 10.5, 6.0, 12, 9
SCOPE_LABELS = 12
LEGEND_Y, LEGEND_H = H - 6, 28  # the page's legend sits outside its SVG; an embedded image has to carry its own
MOMENTUM_TOP = 15
MOMENTUM_W, MOMENTUM_ROW, MOMENTUM_HEAD = 680, 24, 26
NAME_CHARS = 34
_XML_INVALID = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def _esc(value: Any) -> str:
    """Names come from feeds: drop what XML 1.0 cannot hold at all, then escape the rest."""
    return html.escape(_XML_INVALID.sub("", str(value)), quote=True)


def _n(x: float) -> str:
    """Every coordinate at one fixed precision, so the same data renders byte for byte the same."""
    s = f"{x:.1f}".removesuffix(".0")
    return "0" if s == "-0" else s


def _fnv(s: str) -> float:
    """The page's fnv(): FNV-1a over UTF-16 code units (JS charCodeAt), as a fraction of 1."""
    h = 0x811C9DC5
    units = s.encode("utf-16-le")
    for i in range(0, len(units), 2):
        h = ((h ^ (units[i] | units[i + 1] << 8)) * 0x01000193) & 0xFFFFFFFF
    return h / 4294967295


def _radius_for(strength: float) -> float:
    return R_MIN + (R_MAX - R_MIN) * (1 - max(0, min(100, strength)) / 100)


def _dot_radius(mentions: float) -> float:
    return max(4, min(11, 3 + math.sqrt(max(1, mentions)) * 1.5))


def _polar(r: float, angle: float) -> tuple[float, float]:
    a = math.radians(angle)
    return CX + r * math.cos(a), CY + r * math.sin(a)


def _ring_boxes() -> list[dict[str, Any]]:
    """The ring labels' boxes, stacked above the centre: dots and blip labels keep clear of them."""
    boxes = []
    for i, (thresh, label) in enumerate(BANDS):
        r_outer = R_MIN if i == 0 else _radius_for(BANDS[i - 1][0])
        r_mid = (r_outer + _radius_for(thresh)) / 2 or R_MIN / 2
        w = len(label) * RING_CHARW
        boxes.append({"left": CX - 4 - w - 4, "top": CY - r_mid - RING_LH / 2, "w": w + 8, "h": RING_LH,
                      "label": label, "ly": CY - r_mid})
    return boxes


def _sector_labels(sectors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Each sector's name just outside its wedge, with its box: blip labels keep clear of it too."""
    span = 360 / len(sectors)
    labels = []
    for i, s in enumerate(sectors):
        mid = -90 + i * span + span / 2
        x, y = _polar(R_MAX + 16, mid)
        text = str(s.get("short") or s.get("name") or s.get("id", ""))
        label = {"text": text, "x": x, "y": y, "anchor": _anchor(math.cos(math.radians(mid)), 0.35),
                 "lx": x, "ly": y, "w": len(text) * 7.0, "h": 14}
        labels.append({**label, **_label_box(label)})
    return labels


def _keep_clear(p: dict[str, Any], rect: dict[str, Any], margin: float) -> bool:
    left, top = rect["left"] - margin, rect["top"] - margin
    right, bottom = rect["left"] + rect["w"] + margin, rect["top"] + rect["h"] + margin
    dx, dy = p["x"] - min(max(p["x"], left), right), p["y"] - min(max(p["y"], top), bottom)
    dist = math.hypot(dx, dy)
    if dist >= p["rad"]:
        return False
    if dist < 0.01:  # centre inside the band: push straight down
        dx, dy, dist = 0.0, 1.0, 1.0
    push = p["rad"] - dist + 0.5
    p["x"] += dx / dist * push
    p["y"] += dy / dist * push
    return True


def _spread_dots(pts: list[dict[str, Any]], ring_boxes: list[dict[str, Any]]) -> None:
    """The page's spreadDots(): a short pairwise relaxation so same-strength dots don't stack."""
    for _ in range(40):
        moved = False
        for i, a in enumerate(pts):
            for b in pts[i + 1:]:
                min_dist = a["rad"] + b["rad"] + 1.5
                dx, dy = a["x"] - b["x"], a["y"] - b["y"]
                dist = math.hypot(dx, dy)
                if dist >= min_dist:
                    continue
                moved = True
                if dist < 0.01:
                    ang = _fnv(a["key"] + b["key"]) * math.pi * 2
                    dx, dy, dist = math.cos(ang), math.sin(ang), 1.0
                push = (min_dist - dist) / 2
                a["x"] += dx / dist * push
                a["y"] += dy / dist * push
                b["x"] -= dx / dist * push
                b["y"] -= dy / dist * push
            for rect in ring_boxes:
                moved = _keep_clear(a, rect, 3) or moved
        if not moved:
            break


def _by_strength(blips: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(blips, key=lambda b: (-(b.get("strength") or 0), str(b.get("key", ""))))


def _scope_layout(blips: list[dict[str, Any]], sectors: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """The page's buildScopeLayout(): one wedge per sector in `sectors` order, strength inward. A
    blip whose sector is not in `sectors` gets no place, on the page or here."""
    span = 360 / len(sectors)
    ring_boxes = _ring_boxes()
    placed: dict[str, dict[str, Any]] = {}
    for i, s in enumerate(sectors):
        mid = -90 + i * span + span / 2
        members = _by_strength([b for b in blips if b.get("sector") == s["id"]])
        usable = span * min(0.94, max(0.55, 0.55 + 0.045 * len(members)))
        pts = []
        for j, b in enumerate(members):
            key = str(b.get("key", ""))
            frac = j / (len(members) - 1) - 0.5 if len(members) > 1 else 0
            angle = mid + frac * usable + (_fnv(key) - 0.5) * span * 0.12
            x, y = _polar(_radius_for(b.get("strength") or 0) + (_fnv(key + "r") - 0.5) * 6, angle)
            pts.append({"key": key, "x": x, "y": y, "rad": _dot_radius(b.get("mentions") or 0)})
        _spread_dots(pts, ring_boxes)
        for p in pts:
            p["angle"] = math.degrees(math.atan2(p["y"] - CY, p["x"] - CX))
            placed[p["key"]] = p
    return placed


def _anchor(cos_a: float, cut: float) -> str:
    return "start" if cos_a > cut else "end" if cos_a < -cut else "middle"


def _label_box(label: dict[str, Any]) -> dict[str, float]:
    """The text's box as its anchor paints it, plus 2px either side so two names never touch."""
    shift = {"start": 0, "end": label["w"], "middle": label["w"] / 2}[label["anchor"]]
    return {"left": label["lx"] - shift - 2, "top": label["ly"] - label["h"] / 2, "w": label["w"] + 4, "h": label["h"]}


def _overlap(a: dict[str, float], b: dict[str, float]) -> tuple[float, float] | None:
    ox = min(a["left"] + a["w"], b["left"] + b["w"]) - max(a["left"], b["left"])
    oy = min(a["top"] + a["h"], b["top"] + b["h"]) - max(a["top"], b["top"])
    return (ox, oy) if ox > 0 and oy > 0 else None


def _place_labels(items: list[dict[str, Any]], obstacles: list[dict[str, Any]], dots: list[dict[str, Any]]) -> None:
    """The page's placeLabels(): each label starts just outside its dot, along the dot's angle, and
    is pushed off other labels and the ring labels; every tie-break is fnv-keyed, never random.
    Unlike the page it also steps off every dot: a static image has no hover to tell a name
    printed across a dot from the dot's own. [earned: 2026-09-29, first render — "Deno" and
    "Aider" sat on their neighbours' dots]"""
    for lab in items:
        cos_a, sin_a = math.cos(math.radians(lab["angle"])), math.sin(math.radians(lab["angle"]))
        lab["lx"] = lab["x"] + cos_a * (lab["r"] + LABEL_GAP + 6)
        lab["ly"] = lab["y"] + sin_a * (lab["r"] + LABEL_GAP + 6)
        lab["x0"], lab["y0"] = lab["lx"], lab["ly"]
        lab["anchor"] = _anchor(cos_a, 0.15)
        lab["w"], lab["h"] = len(lab["text"]) * LABEL_CHARW, LABEL_LH
    for _ in range(50):
        moved = False
        for i, a in enumerate(items):
            for b in items[i + 1:]:
                hit = _overlap(_label_box(a), _label_box(b))
                if not hit:
                    continue
                moved = True
                dx = (a["lx"] - b["lx"]) or (_fnv(a["key"] + "x") - 0.5)
                dy = (a["ly"] - b["ly"]) or (_fnv(a["key"] + "y") - 0.5)
                length = math.hypot(dx, dy) or 1
                push = min(hit[1], 8) / 2
                a["ly"] += dy / length * push
                b["ly"] -= dy / length * push
                a["lx"] += dx / length * push * 0.4
                b["lx"] -= dx / length * push * 0.4
            for ob in obstacles:
                box = _label_box(a)
                hit = _overlap(box, ob)
                if not hit:
                    continue
                moved = True
                dx = (box["left"] + box["w"] / 2 - ob["left"] - ob["w"] / 2) or (_fnv(a["key"] + "ox") - 0.5)
                dy = (box["top"] + box["h"] / 2 - ob["top"] - ob["h"] / 2) or (_fnv(a["key"] + "oy") - 0.5)
                length = math.hypot(dx, dy) or 1
                push = max(hit) + 2
                a["lx"] += dx / length * push
                a["ly"] += dy / length * push
            for dot in dots:  # the shortest way off the dot's square (its ring included), away from it
                box, reach = _label_box(a), dot["rad"] + 4
                hit = _overlap(box, {"left": dot["x"] - reach, "top": dot["y"] - reach, "w": 2 * reach, "h": 2 * reach})
                if not hit:
                    continue
                moved = True
                if hit[0] < hit[1]:
                    a["lx"] += math.copysign(hit[0] + 1, box["left"] + box["w"] / 2 - dot["x"])
                else:
                    a["ly"] += math.copysign(hit[1] + 1, box["top"] + box["h"] / 2 - dot["y"])
        for lab in items:  # inside the image, whatever the anchor
            box = _label_box(lab)
            lab["lx"] += max(0, -PAD_X + 2 - box["left"]) - max(0, box["left"] + box["w"] - (W + PAD_X - 2))
            lab["ly"] = max(14, min(LEGEND_Y - 24, lab["ly"]))
        if not moved:
            break


def _svg_open(width: float, height: float, min_x: float, title: str, desc: str) -> list[str]:
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{_n(width)}" height="{_n(height)}" '
            f'viewBox="{_n(min_x)} 0 {_n(width)} {_n(height)}" role="img" aria-labelledby="t d" '
            f'font-family="{FONT}">',
            f'<title id="t">{_esc(title)}</title>',
            f'<desc id="d">{_esc(desc)}</desc>']


def _generated_label(data: dict[str, Any]) -> str:
    generated = str(data.get("generated") or "")
    return generated[:16].replace("T", " ") + " UTC" if len(generated) >= 16 and generated[10] == "T" else generated


def _sector_color(sectors: list[dict[str, Any]], i: int) -> str:
    return INK if sectors[i].get("id") == "other" else SECTOR_COLORS[i % len(SECTOR_COLORS)]


def _scope_legend(y: float, generated: str) -> list[str]:
    """Stage swatches, then what the rings and positions mean — the page's legend and scope note."""
    out = []
    x = CX - len(STAGE_COLOR) * 74 / 2
    for stage, color in STAGE_COLOR.items():
        out.append(f'<circle cx="{_n(x + 5)}" cy="{_n(y)}" r="5" fill="{color}"/>')
        out.append(f'<text x="{_n(x + 14)}" y="{_n(y + 4)}" font-size="12" fill="{INK}">{_esc(STAGE_LABEL[stage])}</text>')
        x += 74
    key = "centre = strongest · size = mentions · solid ring = in your vault · dashed ring = not yet"
    if generated:
        key += f" · {generated}"
    out.append(f'<text x="{CX}" y="{_n(y + 24)}" font-size="11" fill="{INK}" text-anchor="middle">{_esc(key)}</text>')
    return out


def render_scope_svg(data: dict[str, Any]) -> str:
    """The radar scope as a standalone SVG: rings by strength (strong near the centre), a wedge per
    sector, a dot per blip coloured by stage and sized by mentions, the top 12 named."""
    blips = data.get("blips") or []
    sectors = data.get("sectors") or []
    generated = _generated_label(data)
    placed = _scope_layout(blips, sectors) if sectors and blips else {}
    drawn = [b for b in blips if str(b.get("key", "")) in placed]
    named = _by_strength(drawn)[:SCOPE_LABELS]
    desc = (f"{len(drawn)} signals over the last {data.get('window_days') or 7} days"
            + (f", generated {generated}" if generated else "")
            + ". Strong signals sit near the centre, colour is stage, size is mentions. Strongest: "
            + ("; ".join(f"{b.get('name', '')} ({STAGE_LABEL.get(b.get('stage'), b.get('stage', ''))}, "
                         f"strength {b.get('strength', 0)})" for b in named) or "none") + ".")
    if not placed:  # a one-line image, not an empty disc the height of a full scope
        out = _svg_open(W + 2 * PAD_X, 32, -PAD_X, "Signal Radar scope", desc)
        out.append(f'<text x="{CX}" y="20" font-size="13" fill="{INK}" text-anchor="middle">'
                   "No signals scored this run.</text>")
        return "\n".join(out + ["</svg>"]) + "\n"
    out = _svg_open(W + 2 * PAD_X, H + LEGEND_H, -PAD_X, "Signal Radar scope", desc)

    span = 360 / len(sectors)
    out.append(f'<g fill="none" stroke="{INK}" stroke-opacity="0.35">')
    out += [f'<circle cx="{CX}" cy="{CY}" r="{_n(_radius_for(thresh))}"/>' for thresh, _ in BANDS]
    out.append("</g>")
    for i, s in enumerate(sectors):
        a0 = -90 + i * span
        (x0, y0), (x1, y1) = _polar(R_MAX, a0), _polar(R_MAX, a0 + span)
        opacity = "0.05" if s.get("id") == "other" else "0.1"
        if len(sectors) == 1:  # one sector is the whole disc: an arc from a point to itself draws nothing
            out.append(f'<circle cx="{CX}" cy="{CY}" r="{R_MAX}" fill="{_sector_color(sectors, i)}" '
                       f'fill-opacity="{opacity}"/>')
        else:
            out.append(f'<path d="M{CX},{CY} L{_n(x0)},{_n(y0)} A{R_MAX},{R_MAX} 0 {1 if span > 180 else 0} 1 '
                       f'{_n(x1)},{_n(y1)} Z" fill="{_sector_color(sectors, i)}" fill-opacity="{opacity}"/>')
            out.append(f'<line x1="{CX}" y1="{CY}" x2="{_n(x0)}" y2="{_n(y0)}" stroke="{INK}" stroke-opacity="0.35"/>')

    blind = set(data.get("blind_spots") or [])
    for b in drawn:
        p = placed[str(b.get("key", ""))]
        r = _dot_radius(b.get("mentions") or 0)
        x, y = _n(p["x"]), _n(p["y"])
        out.append('<g class="blip">')
        if (b.get("in_vault") or 0) > 0:
            out.append(f'<circle cx="{x}" cy="{y}" r="{_n(r + 4)}" fill="none" stroke="{STAGE_COLOR["new"]}" '
                       'stroke-opacity="0.55"/>')
        if b.get("key") in blind:
            out.append(f'<circle cx="{x}" cy="{y}" r="{_n(r + 3)}" fill="none" stroke="{INK}" stroke-dasharray="2 2"/>')
        out.append(f'<circle cx="{x}" cy="{y}" r="{_n(r)}" fill="{STAGE_COLOR.get(b.get("stage"), INK)}"/>')
        out.append("</g>")

    labels = [{**placed[str(b.get("key", ""))], "r": _dot_radius(b.get("mentions") or 0), "text": str(b.get("name", ""))}
              for b in named]
    ring_boxes, sector_labels = _ring_boxes(), _sector_labels(sectors)
    _place_labels(labels, ring_boxes + sector_labels, list(placed.values()))
    for sl in sector_labels:
        out.append(f'<text x="{_n(sl["x"])}" y="{_n(sl["y"] + 4)}" font-size="12" font-weight="600" fill="{INK}" '
                   f'text-anchor="{sl["anchor"]}">{_esc(sl["text"])}</text>')
    for lab in labels:
        if math.hypot(lab["lx"] - lab["x0"], lab["ly"] - lab["y0"]) > 6:  # pushed away: point back at its dot
            out.append(f'<line x1="{_n(lab["x"])}" y1="{_n(lab["y"])}" x2="{_n(lab["lx"])}" y2="{_n(lab["ly"])}" '
                       f'stroke="{INK}" stroke-opacity="0.6" stroke-width="0.75"/>')
        out.append(f'<text x="{_n(lab["lx"])}" y="{_n(lab["ly"] + 3.5)}" font-size="{LABEL_SIZE}" fill="{INK}" '
                   f'text-anchor="{lab["anchor"]}">{_esc(lab["text"])}</text>')
    for rb in ring_boxes:
        out.append(f'<text x="{CX - 4}" y="{_n(rb["ly"] + 3.5)}" font-size="9.5" letter-spacing="0.4" fill="{INK}" '
                   f'text-anchor="end">{_esc(rb["label"].upper())}</text>')
    out += _scope_legend(LEGEND_Y, generated)
    return "\n".join(out + ["</svg>"]) + "\n"


def _short(name: str) -> str:
    return name if len(name) <= NAME_CHARS else name[:NAME_CHARS - 1].rstrip() + "…"


def _spark_points(spark: list[Any], x: float, y: float, w: float, h: float) -> list[tuple[float, float]]:
    """The page's sparkSvg(), in a box: each row scaled to its own busiest day."""
    values = [v if isinstance(v, int | float) else 0 for v in spark]
    top = max([1, *values])
    step = w / (len(values) - 1 or 1)
    return [(x + i * step, y + h - v / top * (h - 2) - 1) for i, v in enumerate(values)]


def render_momentum_svg(data: dict[str, Any]) -> str:
    """The top signals as a strip: name, strength bar in the stage colour, the 14-day mention
    sparkline and the stage, strongest first."""
    top = _by_strength(data.get("blips") or [])[:MOMENTUM_TOP]
    generated = _generated_label(data)
    desc = (f"The {len(top)} strongest signals" + (f", generated {generated}" if generated else "") + ": "
            + ("; ".join(f"{b.get('name', '')}, strength {b.get('strength', 0)}, "
                         f"{STAGE_LABEL.get(b.get('stage'), b.get('stage', ''))}" for b in top) or "none") + ".")
    height = MOMENTUM_HEAD + max(1, len(top)) * MOMENTUM_ROW + 6
    out = _svg_open(MOMENTUM_W, height, 0, "Signal Radar momentum", desc)
    bar_x, bar_w, spark_x, spark_w, stage_x = 232, 150, 432, 150, 600
    head = (("Signal", 0), ("Strength", bar_x), ("Last 14 days", spark_x), ("Stage", stage_x))
    out += [f'<text x="{x}" y="14" font-size="10" letter-spacing="0.4" fill="{INK}">{_esc(t.upper())}</text>'
            for t, x in head]
    if not top:
        out.append(f'<text x="0" y="{MOMENTUM_HEAD + 14}" font-size="12" fill="{INK}">No signals scored this run.</text>')
    for i, b in enumerate(top):
        y = MOMENTUM_HEAD + i * MOMENTUM_ROW
        mid = y + MOMENTUM_ROW / 2
        color = STAGE_COLOR.get(b.get("stage"), INK)
        strength = max(0, min(100, b.get("strength") or 0))
        out.append(f'<text x="0" y="{_n(mid + 4)}" font-size="12.5" fill="{INK}">{_esc(_short(str(b.get("name", ""))))}</text>')
        out.append(f'<rect x="{bar_x}" y="{_n(mid - 5)}" width="{bar_w}" height="10" rx="2" fill="{INK}" fill-opacity="0.15"/>')
        out.append(f'<rect x="{bar_x}" y="{_n(mid - 5)}" width="{_n(bar_w * strength / 100)}" height="10" rx="2" '
                   f'fill="{color}"/>')
        out.append(f'<text x="{bar_x + bar_w + 8}" y="{_n(mid + 4)}" font-size="11.5" fill="{INK}">'
                   f'{_esc(b.get("strength", 0))}</text>')
        pts = _spark_points(b.get("spark") or [], spark_x, mid - 8, spark_w, 16)
        if len(pts) > 1:
            out.append(f'<line x1="{spark_x}" y1="{_n(mid + 8)}" x2="{spark_x + spark_w}" y2="{_n(mid + 8)}" '
                       f'stroke="{INK}" stroke-opacity="0.3"/>')
            out.append(f'<polyline points="{" ".join(f"{_n(px)},{_n(py)}" for px, py in pts)}" fill="none" '
                       f'stroke="{color}" stroke-width="1.5" stroke-linejoin="round" stroke-linecap="round"/>')
        if pts:
            out.append(f'<circle cx="{_n(pts[-1][0])}" cy="{_n(pts[-1][1])}" r="2.5" fill="{color}"/>')
        out.append(f'<text x="{stage_x}" y="{_n(mid + 4)}" font-size="11.5" font-weight="600" fill="{color}">'
                   f'{_esc(STAGE_LABEL.get(b.get("stage"), b.get("stage", "")))}</text>')
    return "\n".join(out + ["</svg>"]) + "\n"


def _wikilink(path: str, title: str) -> str:
    """Same-vault link for the companion note, which lives inside the vault itself."""
    stem = path[:-3] if path.endswith(".md") else path
    title = title.replace("|", "–").replace("[", "(").replace("]", ")")
    return f"[[{stem}|{title}]]" if stem != title else f"[[{stem}]]"


def _fam_badges(families: list[str]) -> str:
    return ", ".join(FAMILY_LABEL.get(f, f) for f in families)


def _top_link(blip: dict[str, Any]) -> str:
    items = blip.get("items") or []
    if not items:
        return ""
    it = items[0]
    title = (it.get("title") or blip["name"]).replace("\n", " ").replace("[", "(").replace("]", ")").strip()
    url = it.get("url") or ""
    return f"[{title}]({url})" if url else title


def _blip_line(b: dict[str, Any]) -> str:
    stage = STAGE_LABEL.get(b.get("stage"), b.get("stage", ""))
    fams = _fam_badges(b.get("families") or [])
    link = _top_link(b)
    tail = f" — {link}" if link else ""
    return f"- **{b['name']}** — {stage}, strength {b.get('strength', 0)}, {fams}{tail}{_graph_tail(b)}"


def _graph_tail(b: dict[str, Any]) -> str:
    """Where the thing sits in the owner's graph: its newest note and the hubs it connects to."""
    notes = b.get("vault_notes") or []
    if not notes:
        return ""
    g = b.get("graph") or {}
    hubs = ", ".join(_wikilink(h["path"], h["title"]) for h in (g.get("hubs") or [])[:2] if h.get("path"))
    head = f"\n  - in your graph: {_wikilink(notes[0]['path'], notes[0]['title'])} ({b.get('in_vault', len(notes))} notes"
    head += f", {g.get('neighborhood', 0)} linked)" + (f" → {hubs}" if hubs else "")
    return head


def render_md(data: dict[str, Any]) -> str:
    """The Obsidian note: the scope and momentum SVGs embedded at the top, then early warnings, top
    signals, blind spots, rising vault tags, and a link to the full page. Notes and hubs are
    wikilinks (same vault); outside items are plain markdown links (someone else's URL)."""
    generated = str(data.get("generated") or "")
    created = generated[:10] or "1970-01-01"
    generated_label = _generated_label(data)
    blips = data.get("blips") or []
    early_keys = data.get("early") or []
    blind_keys = data.get("blind_spots") or []
    by_key = {b["key"]: b for b in blips}
    top = blips[:MD_TOP_SIGNALS]
    early = [by_key[k] for k in early_keys if k in by_key][:MD_TOP_EARLY]
    blind = [by_key[k] for k in blind_keys if k in by_key][:MD_TOP_BLIND]
    vault = data.get("vault") or {}
    rising_tags = [t for t in (vault.get("tags") or []) if t.get("rising") or t.get("new")][:MD_TOP_TAGS]
    graph = data.get("graph") or {}
    hubs = (graph.get("growing_hubs") or [])[:MD_TOP_TAGS]

    lines: list[str] = [
        "---",
        f"description: \"Signal Radar {created} — {len(blips)} signals, {len(early)} early warnings, "
        f"{len(blind)} not yet in the vault.\"",
        "status: active",
        f"created: {created}",
        "tags:",
        "  - domain/toolkit-meta",
        "---",
        "",
        "# Signal Radar",
        "",
        # Obsidian hands an .html file to the system browser: say so before the click does.
        f"Generated {generated_label}. Full page, opens in your browser: [[Signal-Radar.html|Signal Radar (HTML)]].",
        "",
        f"![[{SCOPE_SVG}]]",
        "",
        f"![[{MOMENTUM_SVG}]]",
        "",
    ]

    lines += ["## Early warning", ""]
    if early:
        for b in early:
            lines.append(_blip_line(b))
    else:
        lines.append("Nothing crossed the early-warning bar this run.")
    lines.append("")

    lines += [f"## Top {len(top)} signals", ""]
    if top:
        for b in top:
            lines.append(_blip_line(b))
    else:
        lines.append("No signals scored this run.")
    lines.append("")

    lines += ["## Not in your vault yet", "", "Strong outside, no anchor in the graph yet:", ""]
    if blind:
        for b in blind:
            link = _top_link(b)
            tail = f" — {link}" if link else ""
            lines.append(f"- **{b['name']}** — strength {b.get('strength', 0)}, {_fam_badges(b.get('families') or [])}{tail}")
    else:
        lines.append("None — everything strong enough already has a note.")
    lines.append("")

    lines += ["## Rising in your vault", ""]
    if rising_tags:
        for t in rising_tags:
            examples = t.get("examples") or []
            ex = ", ".join(_wikilink(e["path"], e["title"]) for e in examples[:2] if e.get("path"))
            mark = "new" if t.get("new") else "rising"
            tail = f" ({ex})" if ex else ""
            lines.append(f"- **{t['tag']}** — {mark}, {t.get('this_week', 0)} this week vs {t.get('baseline', 0)} baseline{tail}")
    else:
        lines.append("Nothing rising in your own notes this week.")
    lines.append("")

    if hubs:
        lines += ["## Your graph is growing around", ""]
        for h in hubs:
            examples = h.get("examples") or []
            ex = ", ".join(_wikilink(e["path"], e["title"]) for e in examples[:2] if e.get("path"))
            tail = f" — {ex}" if ex else ""
            mark = " (new hub)" if h.get("new") else ""
            lines.append(f"- {_wikilink(h['path'], h['title'])}{mark} — {h.get('this_week', 0)} this week vs "
                         f"{h.get('baseline', 0)} baseline{tail}")
        lines.append("")

    lines.append("The full page adds the sortable table, each signal's detail and the interest trend.")
    return "\n".join(lines) + "\n"
