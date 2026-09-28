#!/usr/bin/env python3
"""Deterministic generator for the unisphere brand images: the README banners
(banner-dark.svg, banner-light.svg) and the GitHub social-preview source
(social-preview.svg). Stdlib only.

    python3 assets/build_banner.py

The owner's sharpened metaphor, applied literally: **space = the graph.** A note is a world
(a small planet, shaded and colored by its real group), a link is a wormhole (a lane, brighter
near the planets it joins, fading mid-span), a cluster of related notes is a star system (a
faint nebula haze behind same-group planets), a hub note is a core world (an atmosphere glow; at
most one — the graph's single highest-degree node — gets a thin tilted ring), and the whole
scene sits inside one wormhole ring: the frame and portal the graph is viewed through.

Same graph substructure everywhere: `video/src/graph.json` (gaiafield's index of the example
vault, also used by the explainer video and the cheat sheet) already carries a highlighted
"focus" node (36, Knowledge-Graphs-from-Wikilinks) and its neighbors, including Gaiafield
itself. Here that one-hop set is extended, deterministically, to its two-hop neighborhood
(capped at 38 nodes: the one-hop set in full, then the remaining two-hop nodes in ascending
node-id order) so the picture reads as a graph, not five dots — while staying the same real
data every other image already uses, not a hand-drawn motif.

Palette: kept from `video/src/Explainer.tsx` / `docs/cheatsheet/build.py` (`C`, `GROUP`) for the
dark-mode neutrals, the gold "accent" (now used only as the focus/you-are-here marker) and the
five group colors (now the planets' actual fill hues, not a generic accent). New for this brand
pass: a violet-to-magenta `wormhole` gradient (the ring, and every lane/edge), a light-mode
"starlight" counterpart palette, and a per-group light-mode color set — none of that existed
before this pass; the old banners had one dark palette and no lane/ring language at all.
"""
from __future__ import annotations

import json
import math
import random
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
GRAPH = REPO / "video" / "src" / "graph.json"

# kept as-is from Explainer.tsx / cheatsheet build.py
GROUP_DARK = {
    "Concepts": "#9b87ff", "Guides": "#2fd4c0", "Tools": "#ffb547",
    "field-guide": "#ff7ab6", "home-lab-migration": "#ff7ab6", "03_Areas": "#5fb0ff",
}
# new: darkened/saturated for AA-legible use on a light background
GROUP_LIGHT = {
    "Concepts": "#6b46c1", "Guides": "#0c8a7d", "Tools": "#b3690a",
    "field-guide": "#a81f57", "home-lab-migration": "#a81f57", "03_Areas": "#2f6fb3",
}

PALETTE = {
    "dark": dict(
        bg="#0a0e1c", bg2="#141a33", ink="#eef1ff", dim="#8d94b8", line="#3c4270",
        wormhole1="#9b87ff", wormhole2="#ff7ab6", accent="#ffcf5c", star="#c7d0ff",
        group=GROUP_DARK, group_default="#b8bdd6",
    ),
    "light": dict(
        bg="#f5f6fb", bg2="#e9ebf7", ink="#141833", dim="#4b5178", line="#c7cbea",
        wormhole1="#6b46c1", wormhole2="#a81f57", accent="#d9820a", star="#7d84ac",
        group=GROUP_LIGHT, group_default="#5b6088",
    ),
}


def slug(s: str) -> str:
    return "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")


def spread(x: float, y: float) -> tuple[float, float]:
    """The video's/cheat sheet's radial power curve: opens the dense core, keeps the far notes."""
    r = math.hypot(x, y / 0.62) or 1
    f = r**0.55 / r
    return x * f, y * f * 0.62


def load_subset(target: int = 38):
    """focus's one-hop set in full, then two-hop nodes by ascending id, capped at `target`."""
    g = json.loads(GRAPH.read_text(encoding="utf-8"))
    focus = g["focus"]
    adj: dict[int, set[int]] = {}
    for a, b in g["links"]:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    one = set(g["neighbors"]) | {focus}
    two = set(one)
    for n in one:
        two |= adj.get(n, set())
    extra = sorted(two - one)
    take = extra[: max(0, target - len(one))]
    subset = sorted(one | set(take))
    idx = {n: i for i, n in enumerate(subset)}
    nodes = [g["nodes"][n] for n in subset]
    edges = [(idx[a], idx[b]) for a, b in g["links"] if a in idx and b in idx]
    return idx[focus], nodes, edges


def layout(nodes: list[dict], radii: list[float], target_radius: float, iterations: int = 60,
           pad: float = 1.5) -> list[list[float]]:
    """One uniform scale, centered at the origin, then deterministic separation passes so no two
    planets (or a planet and the label margin) overlap — a few fixed relaxation iterations, no
    randomness, clamped back inside `target_radius` every pass so the field can't drift outward."""
    pts = [list(spread(n["x"], n["y"])) for n in nodes]
    cx0 = sum(p[0] for p in pts) / len(pts)
    cy0 = sum(p[1] for p in pts) / len(pts)
    for p in pts:
        p[0] -= cx0
        p[1] -= cy0
    maxr = max(math.hypot(*p) for p in pts) or 1.0
    scale = target_radius / maxr
    for p in pts:
        p[0] *= scale
        p[1] *= scale

    n = len(pts)
    for _ in range(iterations):
        disp = [[0.0, 0.0] for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                dx, dy = pts[i][0] - pts[j][0], pts[i][1] - pts[j][1]
                dist = math.hypot(dx, dy) or 0.01
                min_dist = radii[i] + radii[j] + pad
                if dist < min_dist:
                    push = (min_dist - dist) * 0.5
                    ux, uy = dx / dist, dy / dist
                    disp[i][0] += ux * push
                    disp[i][1] += uy * push
                    disp[j][0] -= ux * push
                    disp[j][1] -= uy * push
        for i in range(n):
            pts[i][0] += disp[i][0]
            pts[i][1] += disp[i][1]
            r = math.hypot(*pts[i])
            if r > target_radius:
                s = target_radius / r
                pts[i][0] *= s
                pts[i][1] *= s
    return pts


def stars(seed: int, n: int, w: float, h: float) -> list[tuple[float, float, float, float]]:
    rnd = random.Random(seed)
    return [
        (round(rnd.uniform(0, w), 1), round(rnd.uniform(0, h), 1),
         round(rnd.uniform(0.3, 1.15), 2), round(rnd.uniform(0.12, 0.65), 2))
        for _ in range(n)
    ]


TAGLINE = "the network your notes, agents and engines connect through"


def render(p: dict, mode: str, *, w: int, h: int, cx: float, cy: float, ring_inner_rx: float,
           unit: float, word_px: int, kicker_px: int, tag_px: int, tx: float, ty0: float,
           star_seed: int, star_n: int, tagline_lines: list[str] | None = None,
           subtitle: str | None = None, sub_px: int = 16) -> str:
    tagline_lines = tagline_lines or [TAGLINE]
    focus_i, nodes, edges = load_subset()
    degrees = [nde["degree"] for nde in nodes]
    radii = [unit * (1.0 + math.sqrt(d) * 0.42) for d in degrees]

    target_radius = ring_inner_rx * 0.65
    pts = layout(nodes, radii, target_radius)
    pts = [(cx + x, cy + y) for x, y in pts]

    ring_ry = ring_inner_rx * 0.68
    ring_outer_rx = ring_inner_rx * 1.18
    ring_outer_ry = ring_outer_rx * 0.68
    tilt = -18

    # hubs: the focus, plus the top 2-3 nodes by degree (excluding the focus if it's already top)
    by_degree = sorted(range(len(nodes)), key=lambda i: (-degrees[i], nodes[i]["title"]))
    top_hubs = [i for i in by_degree if i != focus_i][:3]
    glow_hubs = [focus_i] + top_hubs

    # at most one planet gets a ring: the single highest-degree node, ties broken toward a Tools
    # (engine) node first, then by title, so a real tie resolves the same way every run
    maxdeg = max(degrees)
    ring_candidates = [i for i in range(len(nodes)) if degrees[i] == maxdeg]
    ring_candidates.sort(key=lambda i: (0 if nodes[i]["group"] == "Tools" else 1, nodes[i]["title"]))
    ring_hub = ring_candidates[0]

    # star systems: groups with >=3 members present get a faint nebula haze at their centroid
    groups: dict[str, list[int]] = {}
    for i, nde in enumerate(nodes):
        groups.setdefault(nde["group"], []).append(i)
    nebulae = [(g, ids) for g, ids in groups.items() if len(ids) >= 3]

    out: list[str] = [
        f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" '
        f'role="img" aria-label="unisphere: the network your notes, agents and engines connect through">'
    ]

    # -------------------------------------------------------------- style
    out.append(f"""<style>
    :root {{ color-scheme: {mode}; }}
    .bg {{ fill: {p['bg']}; }}
    .star {{ fill: {p['star']}; }}
    .ring-group {{ transform-origin: {cx}px {cy}px; }}
    .ring-group.cw {{ animation: spin 34s linear infinite; }}
    .ring-group.ccw {{ animation: spin 44s linear infinite reverse; }}
    .glow {{ animation: pulse 4.5s ease-in-out infinite alternate; }}
    .transit {{ animation: transit linear infinite; offset-rotate: 0deg; }}
    .word {{ font: 700 {word_px}px -apple-system, "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif;
             fill: {p['ink']}; letter-spacing: 0.4px; }}
    .kicker {{ font: 600 {kicker_px}px ui-monospace, "SF Mono", Menlo, monospace; fill: {p['dim']};
               letter-spacing: 2.5px; }}
    .tagline {{ font: 400 {tag_px}px ui-monospace, "SF Mono", Menlo, monospace; fill: {p['dim']}; }}
    @keyframes spin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
    @keyframes pulse {{ from {{ opacity: 0.5; }} to {{ opacity: 1; }} }}
    @keyframes transit {{ from {{ offset-distance: 0%; opacity: 0; }} 8% {{ opacity: 1; }}
                           92% {{ opacity: 1; }} to {{ offset-distance: 100%; opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{
      .ring-group, .glow, .transit {{ animation: none !important; }}
      .transit {{ opacity: 0.9; }}
    }}
  </style>""")

    # -------------------------------------------------------------- defs
    defs: list[str] = [
        f'<linearGradient id="wormhole" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{p["wormhole1"]}"/>'
        f'<stop offset="100%" stop-color="{p["wormhole2"]}"/></linearGradient>',
        f'<radialGradient id="core"><stop offset="0%" stop-color="{p["accent"]}" stop-opacity="0.55"/>'
        f'<stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/></radialGradient>',
        f'<radialGradient id="hubglow"><stop offset="0%" stop-color="{p["wormhole1"]}" stop-opacity="0.35"/>'
        f'<stop offset="100%" stop-color="{p["wormhole1"]}" stop-opacity="0"/></radialGradient>',
        '<filter id="haze" x="-60%" y="-60%" width="220%" height="220%">'
        '<feGaussianBlur stdDeviation="3.2"/></filter>',
    ]
    for gname in groups:
        color = p["group"].get(gname, p["group_default"])
        gid = slug(gname)
        defs.append(
            f'<radialGradient id="planet-{gid}" cx="35%" cy="32%" r="75%">'
            f'<stop offset="0%" stop-color="#ffffff" stop-opacity="0.55"/>'
            f'<stop offset="35%" stop-color="{color}"/>'
            f'<stop offset="100%" stop-color="{p["bg"]}" stop-opacity="0.55"/>'
            f"</radialGradient>"
        )
        defs.append(
            f'<radialGradient id="nebula-{gid}"><stop offset="0%" stop-color="{color}" stop-opacity="0.16"/>'
            f'<stop offset="100%" stop-color="{color}" stop-opacity="0"/></radialGradient>'
        )
    # one shared gradient for every lane (objectBoundingBox default: 0,0 -> 1,1, so it still runs
    # roughly start-to-end along each near-straight curve) instead of one per edge — keeps the
    # "brighter near the planets, fading mid-span" look without 100+ near-duplicate defs
    defs.append(
        f'<linearGradient id="lanefade">'
        f'<stop offset="0%" stop-color="{p["wormhole1"]}" stop-opacity="0.8"/>'
        f'<stop offset="50%" stop-color="{p["wormhole1"]}" stop-opacity="0.12"/>'
        f'<stop offset="100%" stop-color="{p["wormhole2"]}" stop-opacity="0.8"/></linearGradient>'
    )
    out.append("<defs>" + "".join(defs) + "</defs>")

    # -------------------------------------------------------------- background
    out.append(f'<rect class="bg" x="0" y="0" width="{w}" height="{h}"/>')
    for x, y, r, o in stars(star_seed, star_n, w, h):
        out.append(f'<circle class="star" cx="{x}" cy="{y}" r="{r}" opacity="{o}"/>')

    # -------------------------------------------------------------- the wormhole ring: frame + portal
    out.append(
        f'<g class="ring-group cw"><ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{ring_outer_rx:.1f}" '
        f'ry="{ring_outer_ry:.1f}" transform="rotate({tilt} {cx:.1f} {cy:.1f})" fill="none" '
        f'stroke="url(#wormhole)" stroke-width="{ring_inner_rx * 0.16:.1f}" opacity="0.16" filter="url(#haze)"/>'
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{ring_outer_rx:.1f}" ry="{ring_outer_ry:.1f}" '
        f'transform="rotate({tilt} {cx:.1f} {cy:.1f})" fill="none" stroke="url(#wormhole)" '
        f'stroke-width="1.6" opacity="0.85"/></g>'
    )
    out.append(
        f'<g class="ring-group ccw"><ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{ring_inner_rx:.1f}" '
        f'ry="{ring_ry:.1f}" transform="rotate({tilt} {cx:.1f} {cy:.1f})" fill="none" '
        f'stroke="url(#wormhole)" stroke-width="0.9" stroke-dasharray="2 7" opacity="0.4"/></g>'
    )

    # -------------------------------------------------------------- star systems (nebula haze)
    for gname, ids in nebulae:
        gx = sum(pts[i][0] for i in ids) / len(ids)
        gy = sum(pts[i][1] for i in ids) / len(ids)
        gr = max(math.hypot(pts[i][0] - gx, pts[i][1] - gy) for i in ids) + unit * 3
        out.append(f'<circle cx="{gx:.1f}" cy="{gy:.1f}" r="{gr:.1f}" fill="url(#nebula-{slug(gname)})"/>')

    # -------------------------------------------------------------- wormhole lanes (edges)
    def curve(i: int, a: int, b: int) -> tuple[str, tuple[float, float]]:
        (x1, y1), (x2, y2) = pts[a], pts[b]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy) or 1
        nx, ny = -dy / length, dx / length
        rnd = random.Random(f"lane-{a}-{b}")
        mag = length * rnd.uniform(0.07, 0.16) * (1 if rnd.random() < 0.5 else -1)
        cxp, cyp = mx + nx * mag, my + ny * mag
        return f"M {x1:.1f} {y1:.1f} Q {cxp:.1f} {cyp:.1f} {x2:.1f} {y2:.1f}", (cxp, cyp)

    lane_paths: list[str] = []
    lit_edges: list[tuple[int, str]] = []
    for i, (a, b) in enumerate(edges):
        d, _ = curve(i, a, b)
        lane_paths.append(d)
        if a == focus_i or b == focus_i:
            lit_edges.append((i, d))

    # a soft glow underlay just for the focus node's own lanes
    for _i, d in lit_edges:
        out.append(f'<path d="{d}" fill="none" stroke="{p["wormhole1"]}" stroke-width="{unit * 2.6:.1f}" '
                    f'opacity="0.22" filter="url(#haze)"/>')
    for i, (a, b) in enumerate(edges):
        lit = a == focus_i or b == focus_i
        sw = unit * (0.85 if lit else 0.5)
        out.append(f'<path d="{lane_paths[i]}" fill="none" stroke="url(#lanefade)" stroke-width="{sw:.2f}"/>')

    # a few transit dots gliding along focus lanes, motion-gated below via prefers-reduced-motion
    for k, (_i, d) in enumerate(lit_edges[:3]):
        out.append(
            f'<circle r="{unit * 0.55:.1f}" fill="{p["ink"]}" class="transit" '
            f'style="offset-path: path(\'{d}\'); animation-duration: {9 + k * 3}s; '
            f'animation-delay: {k * 2}s;"/>'
        )

    # -------------------------------------------------------------- hub atmosphere glows
    for i in glow_hubs:
        gx, gy = pts[i]
        gr = radii[i] * (3.4 if i == focus_i else 2.6)
        gid = "core" if i == focus_i else "hubglow"
        out.append(f'<circle cx="{gx:.1f}" cy="{gy:.1f}" r="{gr:.1f}" fill="url(#{gid})"/>')

    # -------------------------------------------------------------- the ring-hub's own thin ring
    rx0, ry0 = pts[ring_hub]
    rr = radii[ring_hub]
    out.append(
        f'<ellipse cx="{rx0:.1f}" cy="{ry0:.1f}" rx="{rr * 2.3:.1f}" ry="{rr * 0.62:.1f}" '
        f'transform="rotate(-24 {rx0:.1f} {ry0:.1f})" fill="none" stroke="{p["star"]}" '
        f'stroke-width="{unit * 0.4:.2f}" opacity="0.8"/>'
    )

    # -------------------------------------------------------------- planets
    for i, (x, y) in enumerate(pts):
        gid = slug(nodes[i]["group"])
        fill = f"url(#planet-{gid})"
        stroke = p["accent"] if i == focus_i else "none"
        sw = f' stroke="{stroke}" stroke-width="1.1"' if i == focus_i else ""
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radii[i]:.2f}" fill="{fill}"{sw}/>')

    # -------------------------------------------------------------- wordmark
    out.append(f'<text class="kicker" x="{tx:.1f}" y="{ty0:.1f}">AGENTIC-TOOLKIT</text>')
    out.append(f'<text class="word" x="{tx - 2:.1f}" y="{ty0 + word_px * 1.05:.1f}">unisphere</text>')
    tag_y0 = ty0 + word_px * 1.05 + tag_px * 1.7
    for li, line in enumerate(tagline_lines):
        out.append(f'<text class="tagline" x="{tx:.1f}" y="{tag_y0 + li * tag_px * 1.4:.1f}">{line}</text>')
    if subtitle:
        sub_y = tag_y0 + len(tagline_lines) * tag_px * 1.4 + sub_px * 1.4
        out.append(
            f'<text class="tagline" x="{tx:.1f}" y="{sub_y:.1f}" style="font-size:{sub_px}px">{subtitle}</text>'
        )
    out.append("</svg>")
    return "".join(out)


def render_icon(p: dict, *, size: int = 512) -> str:
    """The brand mark alone, no graph and no wordmark: one tilted wormhole ring framing
    one core (accent-gold, "you are here") planet, on the dark palette. Deliberately not
    graph data and not light/dark-paired — Quartz's Favicon and CustomOgImages plugins
    both read exactly one docs-site/static/icon.png, and a mark has to still read at the
    16px a browser tab actually shows. Reuses the same gradients/proportions as `render`'s
    ring and hub-planet so the mark and the banners read as the same object at any size.
    """
    cx = cy = size / 2
    ring_inner_rx = size * 0.34
    ring_ry = ring_inner_rx * 0.68
    ring_outer_rx = ring_inner_rx * 1.18
    ring_outer_ry = ring_outer_rx * 0.68
    tilt = -18
    planet_r = size * 0.135

    out: list[str] = [
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" '
        f'xmlns="http://www.w3.org/2000/svg" role="img" aria-label="unisphere">'
        f'<style>:root {{ color-scheme: dark; }}</style>'
    ]
    defs = [
        f'<linearGradient id="wormhole" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0%" stop-color="{p["wormhole1"]}"/>'
        f'<stop offset="100%" stop-color="{p["wormhole2"]}"/></linearGradient>',
        f'<radialGradient id="core"><stop offset="0%" stop-color="{p["accent"]}" stop-opacity="0.55"/>'
        f'<stop offset="100%" stop-color="{p["accent"]}" stop-opacity="0"/></radialGradient>',
        f'<radialGradient id="planet" cx="35%" cy="32%" r="75%">'
        f'<stop offset="0%" stop-color="#ffffff" stop-opacity="0.6"/>'
        f'<stop offset="35%" stop-color="{p["accent"]}"/>'
        f'<stop offset="100%" stop-color="{p["bg"]}" stop-opacity="0.6"/></radialGradient>',
        f'<filter id="haze" x="-60%" y="-60%" width="220%" height="220%">'
        f'<feGaussianBlur stdDeviation="{size * 0.012:.1f}"/></filter>',
    ]
    out.append("<defs>" + "".join(defs) + "</defs>")

    # rounded-square badge background, like an app icon
    out.append(f'<rect x="0" y="0" width="{size}" height="{size}" rx="{size * 0.18:.1f}" fill="{p["bg"]}"/>')
    for x, y, r, o in stars(2718, 26, size, size):
        out.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{p["star"]}" opacity="{o}"/>')

    # the ring: soft haze + crisp line (outer), a faint dashed inner ring, tilted, double
    out.append(
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{ring_outer_rx:.1f}" ry="{ring_outer_ry:.1f}" '
        f'transform="rotate({tilt} {cx:.1f} {cy:.1f})" fill="none" stroke="url(#wormhole)" '
        f'stroke-width="{ring_inner_rx * 0.16:.1f}" opacity="0.18" filter="url(#haze)"/>'
    )
    out.append(
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{ring_outer_rx:.1f}" ry="{ring_outer_ry:.1f}" '
        f'transform="rotate({tilt} {cx:.1f} {cy:.1f})" fill="none" stroke="url(#wormhole)" '
        f'stroke-width="{size * 0.014:.1f}" opacity="0.9"/>'
    )
    out.append(
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{ring_inner_rx:.1f}" ry="{ring_ry:.1f}" '
        f'transform="rotate({tilt} {cx:.1f} {cy:.1f})" fill="none" stroke="url(#wormhole)" '
        f'stroke-width="{size * 0.007:.1f}" stroke-dasharray="{size * 0.006:.1f} {size * 0.018:.1f}" opacity="0.45"/>'
    )

    # the core world: atmosphere glow, then the planet itself, occluding the ring's middle
    out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{planet_r * 3.0:.1f}" fill="url(#core)"/>')
    out.append(
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{planet_r:.1f}" fill="url(#planet)" '
        f'stroke="{p["accent"]}" stroke-width="{size * 0.004:.1f}"/>'
    )
    out.append("</svg>")
    return "".join(out)


def main() -> None:
    assets = REPO / "assets"

    dark = render(
        PALETTE["dark"], "dark", w=720, h=200, cx=122, cy=100, ring_inner_rx=76, unit=1.05,
        word_px=34, kicker_px=12, tag_px=12, tx=250, ty0=64,
        star_seed=1729, star_n=70,
    )
    light = render(
        PALETTE["light"], "light", w=720, h=200, cx=122, cy=100, ring_inner_rx=76, unit=1.05,
        word_px=34, kicker_px=12, tag_px=12, tx=250, ty0=64,
        star_seed=1729, star_n=70,
    )
    social = render(
        PALETTE["dark"], "dark", w=1280, h=640, cx=350, cy=320, ring_inner_rx=220, unit=2.9,
        word_px=80, kicker_px=20, tag_px=18, tx=660, ty0=230,
        star_seed=4104, star_n=160,
        tagline_lines=["the network your notes, agents", "and engines connect through"],
        subtitle="search &#183; graph &#183; agents &#183; one vault", sub_px=18,
    )

    (assets / "banner-dark.svg").write_text(dark, encoding="utf-8")
    (assets / "banner-light.svg").write_text(light, encoding="utf-8")
    (assets / "social-preview.svg").write_text(social, encoding="utf-8")

    for name in ("banner-dark.svg", "banner-light.svg", "social-preview.svg"):
        n = len((assets / name).read_bytes())
        print(f"{name}: {n:,} bytes")

    # docs-site: Quartz's Favicon and CustomOgImages plugins both read exactly one
    # docs-site/static/icon.png (see docs-site/quartz.config.ts's Plugin.Favicon()/
    # Plugin.CustomOgImages() and .github/workflows/docs.yml). icon.svg is kept
    # alongside as the readable source; icon.png is the rasterized file Quartz
    # actually needs, produced with rsvg-convert (already used for repo image work
    # the same way docs/cheatsheet/build.py shells out to headless Chrome) rather
    # than a new Python image dependency.
    static_dir = REPO / "docs-site" / "static"
    static_dir.mkdir(parents=True, exist_ok=True)
    icon_svg = render_icon(PALETTE["dark"], size=512)
    (static_dir / "icon.svg").write_text(icon_svg, encoding="utf-8")
    print(f"icon.svg: {len(icon_svg.encode('utf-8')):,} bytes")

    rsvg = shutil.which("rsvg-convert")
    icon_png = static_dir / "icon.png"
    if rsvg:
        subprocess.run(
            [rsvg, "-w", "512", "-h", "512", "-o", str(icon_png), str(static_dir / "icon.svg")],
            check=True,
        )
        print(f"icon.png: {icon_png.stat().st_size:,} bytes")
    else:
        print("icon.png: SKIPPED (rsvg-convert not found on PATH — rasterize icon.svg by hand)")


if __name__ == "__main__":
    main()
