#!/usr/bin/env python3
"""The agentic-toolkit cheat sheet: one A3 landscape page, in the explainer video's design.

    python3 docs/cheatsheet/build.py            # writes cheatsheet.html, .pdf and .png here

Same palette, type and art as `video/src/Explainer.tsx`: the deep-navy field, gold accent, pink
INFERRED links, and the example vault's real link graph (`video/src/graph.json`, gaiafield) laid
out with the video's radial spread. Rendered by headless Google Chrome (DIN Condensed is a macOS
system font; elsewhere Oswald or Arial Narrow stand in). Stdlib only.

Every command on the sheet is one the toolkit, its engines or a companion CLI answers today; when
one changes, change it here and rebuild. [earned: 2026-09-28, owner's request]
"""
from __future__ import annotations

import html
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
GRAPH = REPO / "video" / "src" / "graph.json"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# The video's palette (Explainer.tsx `C` and `GROUP`).
C = {"bg": "#0a0e1c", "bg2": "#141a33", "ink": "#eef1ff", "dim": "#8d94b8", "line": "#6d78b8",
     "label": "#6d3fe0", "accent": "#ffcf5c", "inferred": "#ff7ab6"}
VIOLET, TEAL, AMBER, PINK, BLUE = "#9b87ff", "#2fd4c0", "#ffb547", "#ff7ab6", "#5fb0ff"
GROUP = {"Concepts": VIOLET, "Guides": TEAL, "Tools": AMBER, "field-guide": PINK,
         "home-lab-migration": PINK, "03_Areas": BLUE}
DISPLAY = '"DIN Condensed", "Oswald", "Arial Narrow", sans-serif'
SANS = '-apple-system, "SF Pro Display", "Helvetica Neue", Helvetica, Arial, sans-serif'
MONO = 'Menlo, "DejaVu Sans Mono", monospace'

PAGE_W, PAGE_H = 1587, 1123  # A3 landscape at 96 dpi


# ---------------------------------------------------------------- the graph art


def spread(x: float, y: float, size: float) -> tuple[float, float]:
    """The video's radial power curve: opens the dense core, keeps the far notes."""
    r = math.hypot(x, y / 0.62) or 1
    f = r ** 0.55 / r
    return x * f * size, y * f * size * 0.62


def graph_svg(g: dict, width: int, height: int, size: float, rotate: float = -8) -> str:
    pts = [spread(n["x"], n["y"], size) for n in g["nodes"]]
    focus, neighbors = g["focus"], set(g["neighbors"])
    hits = {h["node"] for h in g["hits"]}
    parts = [f'<svg class="graph" width="{width}" height="{height}" viewBox="{-width / 2} {-height / 2} {width} {height}">',
             f'<defs><radialGradient id="glow"><stop offset="0%" stop-color="{C["accent"]}" stop-opacity="0.6"/>'
             f'<stop offset="100%" stop-color="{C["accent"]}" stop-opacity="0"/></radialGradient>'
             f'<radialGradient id="glowp"><stop offset="0%" stop-color="{C["inferred"]}" stop-opacity="0.5"/>'
             f'<stop offset="100%" stop-color="{C["inferred"]}" stop-opacity="0"/></radialGradient>'
             f'<linearGradient id="fx" x1="0" x2="1" y1="0" y2="0"><stop offset="0.22" stop-color="#fff" stop-opacity="0"/>'
             f'<stop offset="0.52" stop-color="#fff" stop-opacity="1"/></linearGradient>'
             f'<linearGradient id="fy" x1="0" x2="0" y1="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
             f'<stop offset="0.34" stop-color="#fff" stop-opacity="1"/></linearGradient>'
             f'<mask id="mx" maskUnits="userSpaceOnUse" x="{-width / 2}" y="{-height / 2}" width="{width}" height="{height}">'
             f'<rect x="{-width / 2}" y="{-height / 2}" width="{width}" height="{height}" fill="url(#fx)"/></mask>'
             f'<mask id="my" maskUnits="userSpaceOnUse" x="{-width / 2}" y="{-height / 2}" width="{width}" height="{height}">'
             f'<rect x="{-width / 2}" y="{-height / 2}" width="{width}" height="{height}" fill="url(#fy)"/></mask></defs>',
             f'<g mask="url(#mx)"><g mask="url(#my)"><g transform="rotate({rotate})">']
    for a, b in g["links"]:
        lit = (a == focus and b in neighbors) or (b == focus and a in neighbors)
        (x1, y1), (x2, y2) = pts[a], pts[b]
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
                     f'stroke="{C["accent"] if lit else C["line"]}" stroke-opacity="{0.95 if lit else 0.3}" '
                     f'stroke-width="{2.4 if lit else 1.1}"/>')
    for pair in g["inferred"]:
        (x1, y1), (x2, y2) = pts[pair["a"]], pts[pair["b"]]
        parts.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{C["inferred"]}" '
                     f'stroke-width="2.6" stroke-dasharray="8 7" stroke-linecap="round"/>')
    for i, n in enumerate(g["nodes"]):
        x, y = pts[i]
        lit = i == focus or i in neighbors or i in hits
        r = 3.2 + math.sqrt(n["degree"]) * 1.35 + (2.5 if i == focus else 0)
        if lit:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r * 4.2:.1f}" fill="url(#glow)"/>')
        color = C["accent"] if i == focus else GROUP.get(n["group"], "#b8bdd6")
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{color}"/>')
    fx, fy = pts[focus]
    parts.append(f'<g transform="translate({fx:.1f} {fy:.1f}) rotate({-rotate})">'
                 f'<text x="16" y="-2" class="nl">{html.escape(g["nodes"][focus]["title"].replace("-", " "))}</text>'
                 f'<text x="16" y="17" class="nlsub">{len(neighbors)} links · gaiafield</text></g>')
    # The tag goes on the INFERRED link furthest into the picture, clear of the fade on the left.
    pair = max(g["inferred"], key=lambda q: pts[q["a"]][0] + pts[q["b"]][0])
    (x1, y1), (x2, y2) = pts[pair["a"]], pts[pair["b"]]
    mx, my = x1 + (x2 - x1) * 0.5, y1 + (y2 - y1) * 0.5
    parts.append(f'<g transform="translate({mx:.1f} {my:.1f}) rotate({-rotate})"><rect x="-58" y="-26" width="116" height="24" rx="12" '
                 f'fill="{C["bg"]}" stroke="{C["inferred"]}" stroke-width="1.5"/>'
                 f'<text x="0" y="-8" text-anchor="middle" class="tag">INFERRED {pair["score"]}</text></g>')
    parts.append("</g></g></g></svg>")
    return "".join(parts)


# ---------------------------------------------------------------- the card logos: small network motifs


def logo(kind: str, color: str) -> str:
    """A 44 px mark per card, drawn as a little network in the card's colour."""
    a, d, ln = color, C["accent"], C["line"]
    body = {
        # a globe of nodes: the one front door
        "unisphere": f'<circle cx="22" cy="22" r="17" fill="none" stroke="{a}" stroke-width="1.6"/>'
                     f'<ellipse cx="22" cy="22" rx="7.5" ry="17" fill="none" stroke="{a}" stroke-opacity=".7" stroke-width="1.3"/>'
                     f'<path d="M5 22h34M8 13h28M8 31h28" stroke="{a}" stroke-opacity=".55" stroke-width="1.1"/>'
                     + "".join(f'<circle cx="{x}" cy="{y}" r="2.6" fill="{d}"/>' for x, y in ((22, 5), (29.5, 13), (14.5, 31), (39, 22), (5, 22), (22, 39))),
        # two clusters, one search, one graph, bridged
        "engines": f'<path d="M8 12 L17 20 L8 29 M17 20 L27 22 M27 22 L36 12 M27 22 L37 31 M36 12 L37 31" stroke="{a}" stroke-width="1.5" fill="none"/>'
                   + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>' for x, y, r, c in
                             ((8, 12, 3, a), (8, 29, 3, a), (17, 20, 4.2, d), (27, 22, 4.2, d), (36, 12, 3, a), (37, 31, 3, a))),
        # a node sending rays to the web
        "tavily": f'<g stroke="{a}" stroke-width="1.5">' + "".join(
            f'<line x1="22" y1="22" x2="{22 + 16 * math.cos(t):.1f}" y2="{22 + 16 * math.sin(t):.1f}"/>' for t in
            [k * math.tau / 7 - 1.2 for k in range(7)]) + "</g>" + "".join(
            f'<circle cx="{22 + 16 * math.cos(t):.1f}" cy="{22 + 16 * math.sin(t):.1f}" r="2.5" fill="{a}"/>' for t in
            [k * math.tau / 7 - 1.2 for k in range(7)]) + f'<circle cx="22" cy="22" r="5.5" fill="{d}"/>',
        # words becoming a small net
        "skills": f'<rect x="4" y="6" width="36" height="24" rx="8" fill="none" stroke="{a}" stroke-width="1.6"/>'
                  f'<path d="M12 30 L10 38 L19 30" fill="none" stroke="{a}" stroke-width="1.6" stroke-linejoin="round"/>'
                  f'<path d="M13 18 L22 13 L31 19 M22 13 L22 23" stroke="{d}" stroke-width="1.4" fill="none"/>'
                  + "".join(f'<circle cx="{x}" cy="{y}" r="2.6" fill="{d}"/>' for x, y in ((13, 18), (22, 13), (31, 19), (22, 23))),
        # sweeping arcs and blips
        "radar": f'<g fill="none" stroke="{a}" stroke-width="1.4">'
                 f'<path d="M6 36 A18 18 0 0 1 38 36" stroke-opacity=".45"/><path d="M12 36 A11 11 0 0 1 32 36" stroke-opacity=".7"/>'
                 f'<line x1="22" y1="36" x2="34" y2="16"/></g><circle cx="22" cy="36" r="3" fill="{a}"/>'
                 + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>' for x, y, r, c in ((31, 21, 3.4, d), (14, 24, 2.4, a), (27, 12, 2, a))),
        # a clock ring with three routines on it
        "routines": f'<circle cx="22" cy="22" r="16" fill="none" stroke="{ln}" stroke-width="2"/>'
                    f'<path d="M22 22 L22 11 M22 22 L30 26" stroke="{a}" stroke-width="1.8" stroke-linecap="round"/>'
                    + "".join(f'<circle cx="{22 + 16 * math.cos(t):.1f}" cy="{22 + 16 * math.sin(t):.1f}" r="3.2" fill="{c}"/>'
                              for t, c in ((-1.9, TEAL), (-0.4, d), (1.2, PINK))),
        # two apps bridged to the vault
        "companions": f'<rect x="3" y="8" width="14" height="14" rx="4" fill="none" stroke="{a}" stroke-width="1.5"/>'
                      f'<rect x="27" y="22" width="14" height="14" rx="4" fill="none" stroke="{a}" stroke-width="1.5"/>'
                      f'<path d="M17 15 C26 15 18 29 27 29" stroke="{d}" stroke-width="1.5" fill="none"/>'
                      f'<circle cx="10" cy="15" r="2.6" fill="{a}"/><circle cx="34" cy="29" r="2.6" fill="{a}"/>',
        # capture -> notes -> links
        "vault": f'<path d="M22 6 L22 16 M22 16 L10 28 M22 16 L34 28 M10 28 L22 36 M34 28 L22 36 M10 28 L34 28" stroke="{a}" stroke-width="1.4" fill="none"/>'
                 + "".join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}"/>' for x, y, r, c in
                           ((22, 6, 3, a), (22, 16, 4, d), (10, 28, 3.2, VIOLET), (34, 28, 3.2, TEAL), (22, 36, 3.2, BLUE))),
    }[kind]
    return f'<svg class="logo" width="44" height="44" viewBox="0 0 44 44">{body}</svg>'


# ---------------------------------------------------------------- the content


def rows(items: list[tuple[str, str]]) -> str:
    return "".join(f'<div class="row"><code>{html.escape(c)}</code><span>{html.escape(t)}</span></div>' for c, t in items)


def card(kind: str, color: str, kicker: str, title: str, inner: str, foot: str = "", cls: str = "") -> str:
    foot_html = f'<div class="foot">{foot}</div>' if foot else ""
    return (f'<section class="card {cls}" style="--c:{color}"><header>{logo(kind, color)}<div><div class="kicker">{kicker}</div>'
            f'<h2>{title}</h2></div></header><div class="body">{inner}</div>{foot_html}</section>')


def routines_clock() -> str:
    """A 24 h ring, UTC: each routine's fires as dots on its own orbit."""
    cx, cy, parts = 95, 95, []
    orbits = [("Pipeline", "58 */3", PINK, 82, [h + 58 / 60 for h in range(0, 24, 3)]),
              ("Signal Radar", "28 2-23/3", TEAL, 66, [h + 28 / 60 for h in range(2, 24, 3)]),
              ("Watchdog", "58 2-23/3", C["accent"], 50, [h + 58 / 60 for h in range(2, 24, 3)])]
    parts.append('<svg width="170" height="170" viewBox="0 0 190 190">')
    for h in range(24):
        t = h / 24 * math.tau - math.pi / 2
        r0, r1 = (88, 94) if h % 6 == 0 else (90, 93)
        parts.append(f'<line x1="{cx + r0 * math.cos(t):.1f}" y1="{cy + r0 * math.sin(t):.1f}" x2="{cx + r1 * math.cos(t):.1f}" '
                     f'y2="{cy + r1 * math.sin(t):.1f}" stroke="{C["dim"]}" stroke-width="{1.6 if h % 6 == 0 else 0.8}"/>')
    for _label, _, color, r, hours in orbits:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-opacity=".28" stroke-width="1.2"/>')
        for hh in hours:
            t = hh / 24 * math.tau - math.pi / 2
            parts.append(f'<circle cx="{cx + r * math.cos(t):.1f}" cy="{cy + r * math.sin(t):.1f}" r="4.2" fill="{color}"/>')
    for h, anchor in ((0, "00"), (6, "06"), (12, "12"), (18, "18")):
        t = h / 24 * math.tau - math.pi / 2
        parts.append(f'<text x="{cx + 38 * math.cos(t):.1f}" y="{cy + 38 * math.sin(t) + 4:.1f}" text-anchor="middle" class="clk">{anchor}</text>')
    parts.append(f'<text x="{cx}" y="{cy + 5}" text-anchor="middle" class="clkc">UTC</text></svg>')
    legend = "".join(f'<div class="leg"><i style="background:{c}"></i><b>{lbl}</b><code>{cron}</code></div>' for lbl, cron, c, _, _ in orbits)
    return f'<div class="clock">{"".join(parts)}<div class="legend">{legend}' \
           f'<p>Pipeline ingests, distills and commits. Signal Radar: <code>sensors</code> + <code>signal --check</code>. ' \
           f'Watchdog pushes only when something is wrong.</p></div></div>'


def vault_flow() -> str:
    """Capture to linked notes, as a small labelled network."""
    n = {"cap": (40, 62, "01_Capture", C["accent"]), "dis": (150, 62, "distill", C["ink"]),
         "p": (262, 24, "02_Projects", PINK), "a": (262, 62, "03_Areas", BLUE), "r": (262, 100, "04_Resources", VIOLET),
         "arc": (378, 62, "05_Archive", C["dim"]), "mem": (150, 124, "00_Memory", TEAL)}
    edges = [("cap", "dis", C["accent"], ""), ("dis", "p", C["line"], ""), ("dis", "a", C["line"], ""), ("dis", "r", C["line"], ""),
             ("p", "a", C["inferred"], "4 3"), ("a", "r", C["line"], ""), ("a", "arc", C["dim"], "2 4"), ("mem", "dis", TEAL, "3 3")]
    s = ['<svg width="420" height="152" viewBox="0 0 420 152">']
    for a, b, col, dash in edges:
        (x1, y1, *_), (x2, y2, *_) = n[a], n[b]
        s.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="1.6" stroke-opacity=".8"'
                 + (f' stroke-dasharray="{dash}"' if dash else "") + "/>")
    for key, (x, y, label, col) in n.items():
        r = 9 if key == "dis" else 6.5
        if key in ("cap", "dis"):
            s.append(f'<circle cx="{x}" cy="{y}" r="{r * 3.4}" fill="url(#glowsmall)"/>')
        s.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{col}"/>')
        if key in ("p", "a", "r"):  # beside the note, clear of the links that fan in from the left
            s.append(f'<text x="{x + 12}" y="{y + 4}" class="vf">{label}</text>')
        else:
            s.append(f'<text x="{x}" y="{y + (-16 if key in ("cap", "dis") else 22)}" text-anchor="middle" class="vf">{label}</text>')
    s.append('<defs><radialGradient id="glowsmall"><stop offset="0%" stop-color="#ffcf5c" stop-opacity=".45"/>'
             '<stop offset="100%" stop-color="#ffcf5c" stop-opacity="0"/></radialGradient></defs></svg>')
    return "".join(s)


def page() -> str:
    g = json.loads(GRAPH.read_text(encoding="utf-8"))
    cards = [
        card("unisphere", C["accent"], "the front door · people read, agents add --json", "unisphere", rows([
            ("unisphere status", "engines, plugins, vault, pipeline, companions: all current?"),
            ("unisphere search agent memory", "ranked full-text search (farsight)"),
            ("unisphere graph neighbors <note>", "links to and from a note  --depth 2"),
            ("unisphere graph path <a> <b>", "the shortest chain of links"),
            ("unisphere graph candidates <note>", "same topic, not linked yet"),
            ("unisphere commands --json", "the catalogue an agent starts from"),
            ("unisphere link --vault <path>", "put it all on ~/.local/bin"),
            ("unisphere doctor · engines status", "vault structure · engine versions"),
        ]), foot="<b>--json</b> on every command · exit <b>0</b> ok · <b>1</b> problem · <b>2</b> usage"),
        card("engines", VIOLET, "Rust · deterministic · on your PATH", "The engines", rows([
            ("farsight query <words> --k 5", "BM25 over active notes"),
            ("gaiafield index", "wikilinks + frontmatter → SQLite graph"),
            ("gaiafield neighbors <note>", "depth, direction in|out|both"),
            ("gaiafield stats", "nodes, edges, dangling, top linked"),
            ("gaiafield infer", "embeddings → INFERRED edges"),
            ("gaiafield candidates <note>", "link suggestions, scored"),
            ("gaiafield surprise", "cross-domain pairs worth a look"),
        ]), foot=f'example vault: <b>{g["stats"]["nodes"]}</b> notes · <b>{g["stats"]["edges"]}</b> links'),
        card("tavily", TEAL, "the one way to the web", "tvly · Tavily", rows([
            ('tvly search "<q>" --json', "--time-range week · --topic news"),
            ("  --include-domains reddit.com", "what the radar does for Reddit"),
            ("tvly extract <url> --format markdown", "clean page text, JS rendered"),
            ("tvly map <site>", "every URL on a site"),
            ("tvly crawl <site> --max-depth 2", "a docs section, page by page"),
            ('tvly research "X vs Y"', "cited report, 30–120 s"),
            ("tvly --status --json", "version, authenticated?"),
        ]), foot="<b>TAVILY_API_KEY</b> · <b>1 credit</b> a search · <b>$2</b>/week"),
        card("skills", PINK, "the toolkit's six · just say it", "Skills", rows([
            ("“distill my inbox”", "obsidian:distill · captures → linked notes"),
            ("“run the pipeline”", "obsidian:pipeline · the unattended run"),
            ("“find orphans · vault health”", "obsidian:vault · read, write, audit"),
            ("“what's new in my feeds”", "radar:radar · scan, weekly, Kagi"),
            ("“save a handoff” · “resume”", "handoff:handoff · for another session"),
            ("“distill this session's memory”", "memory:distill-memory"),
        ]), foot="also installed: <b>tavily:*</b> (search, extract, research …) · <b>todoist-cli</b>"),
        card("radar", AMBER, "radar.py <command> --json", "Radar", rows([
            ("scan", "judge Reader items against your interests"),
            ("sensors", "HN · Hugging Face · GitHub · Reddit · RSS"),
            ("signal --check", "named things + web check (Tavily)"),
            ("weekly", "the week's capture, 01_Capture/"),
            ("gaps", "what the feeds missed, per interest"),
            ("scout · discover", "new sources · new feeds (OPML)"),
            ("kagi search|news|answer|summarize", "Kagi on demand"),
        ]), foot="<b>plugins/radar/scripts/radar.py</b> · via uv run"),
        card("routines", BLUE, "Claude cloud routines · every 3 h", "Cloud", routines_clock(), cls="wide-body"),
        card("companions", VIOLET, "next to unisphere, on your PATH", "Obsidian · Todoist", rows([
            ("obsidian daily", "open today's daily note"),
            ('obsidian daily:append content="…"', "add a line to it"),
            ("obsidian open file=<note>", "open a note in the app"),
            ("obsidian backlinks file=<note>", "format=json"),
            ("obsidian orphans · unresolved", "the app's own health checks"),
            ("td today · td upcoming", "what's due"),
            ('td task add "…" --json', "structured add, for agents"),
        ]), foot="<b>obsidian</b>: app running · <b>td</b>: its own login"),
        card("vault", TEAL, "TheVoid · PARA · agent-maintained", "The vault", vault_flow() +
             '<p class="note">Captures land in <b>01_Capture</b>, distill writes linked notes, the capture retires to '
             '<b>05_Archive</b>. <b>00_Memory</b> holds the radar, the DLQ and the run state. <b>Index.md</b>, '
             '<b>Maps/</b> and <b>Now.md</b> are generated, never edited.</p>'),
    ]
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>agentic-toolkit cheat sheet</title>
<style>
@page {{ size: 420mm 297mm; margin: 0; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
html, body {{ width: {PAGE_W}px; height: {PAGE_H}px; }}
html {{ background: {C['bg']}; }}
body {{ background: radial-gradient(ellipse at 72% 18%, {C['bg2']} 0%, {C['bg']} 62%); color: {C['ink']};
       font-family: {SANS}; overflow: hidden; position: relative; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
.hero {{ position: absolute; top: -70px; right: -40px; width: 980px; height: 470px; }}
.hero .graph {{ position: absolute; inset: 0; }}
@media print {{ .card {{ box-shadow: none !important; }} }}
.nl {{ font-family: {SANS}; font-weight: 600; font-size: 17px; fill: {C['ink']}; paint-order: stroke; stroke: {C['bg']}; stroke-width: 5px; }}
.nlsub {{ font-family: {MONO}; font-size: 13px; fill: {C['accent']}; paint-order: stroke; stroke: {C['bg']}; stroke-width: 5px; }}
.tag {{ font-family: {DISPLAY}; font-size: 15px; letter-spacing: 1px; fill: {C['inferred']}; }}
.top {{ position: relative; padding: 40px 56px 0; height: 300px; }}
.eyebrow {{ font-family: {DISPLAY}; font-size: 20px; letter-spacing: 5px; color: {C['accent']}; }}
h1 {{ font-weight: 800; font-size: 66px; letter-spacing: -2px; line-height: 1; margin-top: 12px; }}
h1 em {{ font-style: normal; color: {C['accent']}; }}
.sub {{ font-size: 19px; color: {C['dim']}; margin-top: 14px; max-width: 700px; line-height: 1.4; }}
.meta {{ display: flex; align-items: center; gap: 22px; margin-top: 20px; }}
.url {{ font-family: {MONO}; font-size: 16px; color: {C['accent']}; }}
.pills {{ display: flex; gap: 10px; }}
.pill {{ font-family: {DISPLAY}; font-size: 17px; letter-spacing: 1.5px; padding: 6px 16px 2px; border-radius: 30px;
         border: 2px solid var(--c); color: var(--c); background: {C['bg']}cc; }}
.grid {{ position: absolute; left: 40px; right: 40px; top: 318px; bottom: 44px; display: grid;
         grid-template-columns: repeat(4, 1fr); grid-template-rows: 1fr 1fr; gap: 16px; }}
.card {{ background: linear-gradient(180deg, {C['bg2']}f2 0%, {C['bg']}f2 100%); border: 1px solid {C['line']}55;
         border-top: 3px solid var(--c); border-radius: 16px; padding: 14px 16px 12px; display: flex; flex-direction: column;
         box-shadow: 0 18px 40px #00000066, inset 0 1px 0 #ffffff0d; overflow: hidden; }}
.card header {{ display: flex; gap: 12px; align-items: center; margin-bottom: 8px; }}
.kicker {{ font-size: 11px; color: {C['dim']}; letter-spacing: .3px; }}
h2 {{ font-family: {DISPLAY}; font-weight: 700; font-size: 29px; letter-spacing: 1.2px; color: var(--c); line-height: 1; margin-top: 3px; }}
.body {{ flex: 1; }}
.row {{ display: grid; grid-template-columns: 1fr; padding: 3px 0 3px; border-bottom: 1px dashed {C['line']}33; }}
.row:last-child {{ border-bottom: 0; }}
.row code {{ font-family: {MONO}; font-size: 12.2px; color: {C['ink']}; white-space: pre; }}
.row span {{ font-size: 11.3px; color: {C['dim']}; margin-top: 1px; }}
.foot {{ font-size: 11px; color: {C['dim']}; margin-top: 6px; padding-top: 7px; border-top: 1px solid {C['line']}44; font-family: {MONO}; }}
.foot b {{ color: var(--c); font-weight: 600; }}
.clock {{ display: flex; flex-direction: column; align-items: center; gap: 6px; }}
.clk {{ font-family: {MONO}; font-size: 10px; fill: {C['dim']}; }}
.clkc {{ font-family: {DISPLAY}; font-size: 16px; letter-spacing: 2px; fill: {C['ink']}; }}
.legend {{ width: 100%; }}
.leg {{ display: flex; align-items: center; gap: 8px; font-size: 12.5px; padding: 2px 0; }}
.leg i {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
.leg code {{ font-family: {MONO}; font-size: 11.5px; color: {C['dim']}; margin-left: auto; }}
.legend p {{ font-size: 11px; color: {C['dim']}; margin-top: 6px; line-height: 1.35; }}
.legend p code {{ font-family: {MONO}; color: {C['ink']}; }}
.vf {{ font-family: {MONO}; font-size: 11px; fill: {C['ink']}; }}
.note {{ font-size: 11.5px; color: {C['dim']}; line-height: 1.42; margin-top: 4px; }}
.note b {{ color: {C['ink']}; font-weight: 600; }}
.card .body svg {{ max-width: 100%; height: auto; display: block; margin: 0 auto; }}
.bottom {{ position: absolute; left: 56px; right: 56px; bottom: 14px; display: flex; justify-content: space-between;
           font-size: 11px; color: {C['dim']}; font-family: {MONO}; }}
.bottom b {{ color: {C['accent']}; font-weight: 400; }}
</style></head>
<body>
<div class="hero">{graph_svg(g, 980, 470, 430)}</div>
<div class="top">
  <div class="eyebrow">AGENTIC-TOOLKIT · CHEAT SHEET</div>
  <h1>Your vault is the <em>platform.</em></h1>
  <p class="sub">One front door for you and your agents: <b style="color:{C['ink']}">unisphere</b>, two Rust engines,
  Tavily for the web, and skills you simply ask for.</p>
  <div class="meta"><div class="url">github.com/marsmike/agentic-toolkit</div>
  <div class="pills"><span class="pill" style="--c:{C['accent']}">UNISPHERE</span><span class="pill" style="--c:{VIOLET}">FARSIGHT</span>
  <span class="pill" style="--c:{VIOLET}">GAIAFIELD</span><span class="pill" style="--c:{TEAL}">TVLY</span>
  <span class="pill" style="--c:{PINK}">6 SKILLS · 5 PLUGINS</span></div></div>
</div>
<main class="grid">{''.join(cards)}</main>
<div class="bottom"><span>graph: the example vault, indexed by gaiafield · <b>- - -</b> <span style="color:{C['inferred']}">INFERRED</span>
link suggested by embeddings · gold: a note and its links</span><span>docs/cheatsheet/build.py · rebuilt from the repo</span></div>
</body></html>
"""


def main() -> int:
    out_html = HERE / "cheatsheet.html"
    out_html.write_text(page(), encoding="utf-8")
    chrome = CHROME if Path(CHROME).is_file() else shutil.which("google-chrome") or shutil.which("chromium")
    if not chrome:
        print(f"wrote {out_html}; no Chrome found for the PDF and PNG", file=sys.stderr)
        return 1
    common = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
              "--allow-file-access-from-files", "--run-all-compositor-stages-before-draw", "--virtual-time-budget=4000"]
    subprocess.run([*common, "--no-pdf-header-footer", f"--print-to-pdf={HERE / 'agentic-toolkit-cheatsheet.pdf'}",
                    out_html.as_uri()], check=True, capture_output=True)
    subprocess.run([*common, f"--window-size={PAGE_W},{PAGE_H}", "--force-device-scale-factor=2",
                    f"--screenshot={HERE / 'agentic-toolkit-cheatsheet.png'}", out_html.as_uri()], check=True, capture_output=True)
    for f in ("cheatsheet.html", "agentic-toolkit-cheatsheet.pdf", "agentic-toolkit-cheatsheet.png"):
        print(f"wrote {HERE / f} ({(HERE / f).stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
