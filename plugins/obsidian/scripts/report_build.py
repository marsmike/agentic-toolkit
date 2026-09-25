#!/usr/bin/env python3
"""Build the last run's ingestion report: `00_Memory/last-run-report.html`, one static page.

    uv run scripts/report_build.py [--run "YYYY-MM-DD HH:MM"] [--today YYYY-MM-DD]

A generator in `end`, so it describes the run that is ending: what it imported, where each item
came from (its source and every link ingest expanded), the images it kept, what each became (the
note on GitHub and in Obsidian), every note the run wrote or changed, and the vault's vitals
(notes by PARA folder and domain, distilled per day, the archive, images, highlights, Reader).
A run that imported nothing says so and shows the last run that did. The cloud routine publishes
this file to one Claude artifact after every successful run (`report_artifact_url` in the
profile), so the artifact always holds the latest report. [earned: 2026-09-25, owner's request —
publish the last ingestion report as an artifact, overwritten by each successful run; "more
visual, with stats about the vault"]

The file follows the Artifact page contract: no doctype, html, head or body tags (the publisher
wraps it), a <title> first, every style inline, no script; charts are inline SVG. Every value is
HTML-escaped and only http(s) addresses become links: titles and sources are other people's words.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit

import imports_log
from vault_utils import atomic_write, contained, profile_value, read_frontmatter, require_vault

OUT = Path("00_Memory") / "last-run-report.html"
STATE = Path("00_Memory") / "pipeline-state.json"
ARCHIVED = Path("00_Memory") / "readwise-archived.jsonl"
INGESTED = Path("00_Memory") / "readwise-ingested.jsonl"
MEDIA = Path("04_Resources") / "Attachments" / "Tweets"
NOTE_DIRS = ("02_Projects/", "03_Areas/", "04_Resources/")
PARA = (("02_Projects", "Projects"), ("03_Areas", "Areas"), ("04_Resources", "Resources"))
DAYS = 30
STATUS = {"distilled": "Distilled", "known": "Already in vault", "dropped": "Dropped", "duplicate": "Duplicate",
          "archived": "Archived", "waiting": "Waiting", "missing": "Missing"}

STYLE = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,800&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
:root {
  --paper: #f3f4ef; --sheet: #ffffff; --ink: #10151f; --ink-2: #454d5c; --muted: #7b8290; --rule: #dcdfd6;
  --grid: #e7e9e2; --accent: #2f4bff; --accent-soft: #e6e9ff; --run: #ffb000; --run-ink: #6b4a00;
  --hero: #10151f; --hero-ink: #f3f4ef; --hero-mute: #9aa3b5; --hero-grid: rgba(255,255,255,.06);
  --p1: #2a78d6; --p2: #eb6834; --p3: #1baf7a;
  --good: #1d7a45; --warn: #9a6a00; --bad: #c0281f;
  --display: "Bricolage Grotesque", "Avenir Next", "Segoe UI", system-ui, sans-serif;
  --sans: "Atkinson Hyperlegible", -apple-system, "Segoe UI", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --paper: #0d1118; --sheet: #141a24; --ink: #eef1f6; --ink-2: #b9c0cc; --muted: #858d9b; --rule: #252d3a;
    --grid: #1c232f; --accent: #8a9bff; --accent-soft: #1b2140; --run: #ffc24d; --run-ink: #ffd98a;
    --hero: #151c2a; --hero-ink: #eef1f6; --hero-mute: #8f98aa; --hero-grid: rgba(255,255,255,.05);
    --p1: #3987e5; --p2: #d95926; --p3: #199e70; --good: #5cc28a; --warn: #e0b04a; --bad: #f08a80;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --paper: #0d1118; --sheet: #141a24; --ink: #eef1f6; --ink-2: #b9c0cc; --muted: #858d9b; --rule: #252d3a;
  --grid: #1c232f; --accent: #8a9bff; --accent-soft: #1b2140; --run: #ffc24d; --run-ink: #ffd98a;
  --hero: #151c2a; --hero-ink: #eef1f6; --hero-mute: #8f98aa; --hero-grid: rgba(255,255,255,.05);
  --p1: #3987e5; --p2: #d95926; --p3: #199e70; --good: #5cc28a; --warn: #e0b04a; --bad: #f08a80;
}
body { background: var(--paper); color: var(--ink); font: 15px/1.55 var(--sans); }
.wrap { max-width: 1040px; margin: 0 auto; padding-inline: 16px; padding-block: 20px 56px; display: grid; gap: 22px; }
.num { font-family: var(--mono); font-variant-numeric: tabular-nums; }
a { color: var(--accent); }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }

.hero { background: var(--hero); color: var(--hero-ink); border-radius: 18px; padding: clamp(20px, 4vw, 36px);
  background-image: linear-gradient(var(--hero-grid) 1px, transparent 1px), linear-gradient(90deg, var(--hero-grid) 1px, transparent 1px);
  background-size: 28px 28px; display: grid; gap: 18px; position: relative; overflow: hidden; }
.brand { display: flex; align-items: center; gap: 10px; font: 600 12px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--hero-mute); }
.brand svg { flex: none; }
.brand b { color: var(--hero-ink); font-weight: 600; }
.hero h1 { font: 800 clamp(30px, 6.4vw, 60px)/1.02 var(--display); letter-spacing: -.02em; margin: 0; max-width: 18ch; text-wrap: balance; }
.hero h1 em { font-style: normal; color: var(--run); }
.hero p { margin: 0; color: var(--hero-mute); max-width: 62ch; }
.hero p b { color: var(--hero-ink); font-weight: 700; }
.big { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 14px 24px; margin: 4px 0 0; padding: 0; list-style: none; }
.big li { display: grid; gap: 4px; border-top: 1px solid rgba(255,255,255,.14); padding-top: 10px; }
.big b { font: 600 clamp(26px, 4.4vw, 38px)/1 var(--mono); font-variant-numeric: tabular-nums; }
.big span { font-size: 12.5px; color: var(--hero-mute); }
.big .hot b { color: var(--run); }

h2 { font: 800 clamp(20px, 3vw, 26px)/1.15 var(--display); letter-spacing: -.01em; margin: 0; text-wrap: balance; }
.lede { margin: 2px 0 0; color: var(--ink-2); }
.panel { background: var(--sheet); border: 1px solid var(--rule); border-radius: 14px; padding: 18px; display: grid; gap: 14px; min-width: 0; }
.panel h3 { font: 600 12px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin: 0;
  display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; }
.vitals { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 14px; }
.v-wide { grid-column: span 8; } .v-side { grid-column: span 4; } .v-half { grid-column: span 6; }
@media (max-width: 820px) { .v-wide, .v-side, .v-half { grid-column: span 12; } }
.chart { width: 100%; height: auto; display: block; }
.chart .ax { stroke: var(--grid); stroke-width: 1; }
.chart text { fill: var(--muted); font: 10.5px var(--mono); }
.chart .bar { fill: var(--accent); }
.chart .bar.run { fill: var(--run); }
.legend { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12.5px; color: var(--ink-2); }
.sw { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 6px; vertical-align: -1px; }
.stack { display: flex; height: 14px; border-radius: 7px; overflow: hidden; gap: 2px; background: var(--grid); }
.stack i { display: block; height: 100%; }
.hbars { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.hbars li { display: grid; grid-template-columns: minmax(0, 150px) minmax(0, 1fr) 40px; gap: 10px; align-items: center; font-size: 13px; }
.hbars .n { color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.hbars .t { height: 10px; background: var(--grid); border-radius: 5px; overflow: hidden; }
.hbars .f { display: block; height: 100%; background: var(--accent); border-radius: 5px; }
.hbars .c { text-align: right; color: var(--muted); font: 12px var(--mono); font-variant-numeric: tabular-nums; }
.facts { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px 16px; margin: 0; }
.facts div { display: grid; gap: 2px; }
.facts dt { font-size: 12px; color: var(--muted); order: 2; }
.facts dd { margin: 0; font: 600 22px/1.1 var(--mono); font-variant-numeric: tabular-nums; order: 1; }

.items { list-style: none; margin: 0; padding: 0; display: grid; gap: 12px; }
.item { background: var(--sheet); border: 1px solid var(--rule); border-radius: 14px; padding: 16px 18px; display: grid; gap: 8px; }
.row { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }
.kind { font: 600 10.5px/1 var(--mono); letter-spacing: .07em; text-transform: uppercase; color: var(--ink-2); background: var(--grid); border-radius: 4px; padding: 5px 7px; }
.status { font: 600 10.5px/1 var(--mono); letter-spacing: .07em; text-transform: uppercase; border-radius: 4px; padding: 4px 6px; border: 1px solid currentColor; }
.s-distilled, .s-known { color: var(--good); } .s-waiting, .s-archived, .s-duplicate { color: var(--warn); }
.s-dropped { color: var(--muted); } .s-missing { color: var(--bad); }
.title { font: 700 17px/1.3 var(--sans); color: var(--ink); text-decoration: none; overflow-wrap: anywhere; }
a.title:hover { color: var(--accent); }
.meta { font-size: 13px; color: var(--muted); }
.became { font-size: 14px; color: var(--ink-2); }
.notelinks { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: 14px; }
.notelinks a { font-weight: 700; }
.alt { font-size: 12.5px; color: var(--muted); }
.links { margin: 0; padding: 0; list-style: none; display: grid; gap: 3px; font: 12.5px/1.45 var(--mono); }
.links li { overflow-wrap: anywhere; color: var(--muted); }
.links li::before { content: "↳ "; }
.notes { margin: 0; padding: 0; list-style: none; display: grid; gap: 8px; }
.notes li { display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: baseline; }
.tag { font: 600 10.5px/1 var(--mono); letter-spacing: .06em; text-transform: uppercase; min-width: 64px; }
.tag.new { color: var(--good); } .tag.changed { color: var(--muted); }
.empty { color: var(--ink-2); margin: 0; }
footer { font-size: 13px; color: var(--muted); display: grid; gap: 4px; }
footer b { color: var(--ink-2); }
</style>
"""

MARK = ('<svg width="22" height="22" viewBox="0 0 22 22" aria-hidden="true"><circle cx="11" cy="11" r="9.5" fill="none" '
        'stroke="currentColor" stroke-opacity=".45"/><circle cx="11" cy="11" r="5.5" fill="none" stroke="var(--run)" '
        'stroke-width="2"/><circle cx="11" cy="11" r="1.8" fill="currentColor"/></svg>')


def _git(vault: Path, *args: str) -> str:
    run = subprocess.run(["git", "-C", str(vault), *args], capture_output=True, text=True, check=False)
    return run.stdout if run.returncode == 0 else ""


def _web(url: object) -> str:
    """The address, if it may be a link (http or https only); else ""."""
    u = str(url or "").strip()
    return u if re.match(r"^https?://", u, re.I) else ""


def _github_base(vault: Path) -> str:
    """`https://github.com/<owner>/<repo>/blob/<branch>/` for a GitHub remote, else ""."""
    remote = _git(vault, "remote", "get-url", "origin").strip()
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote)
    branch = _git(vault, "rev-parse", "--abbrev-ref", "HEAD").strip() or "main"
    return f"https://github.com/{m.group(1)}/{m.group(2)}/blob/{branch}/" if m else ""


def _note_link(vault: Path, rel: str, gh: str) -> str:
    rel = rel if rel.endswith(".md") else rel + ".md"
    name = escape(Path(rel).stem.replace("-", " "))
    obsidian = f"obsidian://open?vault={quote(vault.name)}&file={quote(rel.removesuffix('.md'))}"
    head = f'<a href="{escape(gh + quote(rel))}">{name}</a>' if gh else f"<b>{name}</b>"
    return f'<span>{head} <span class="alt">· <a href="{escape(obsidian)}">Obsidian</a></span></span>'


def _host(url: str) -> str:
    try:
        return (urlsplit(url).hostname or url).removeprefix("www.")
    except ValueError:
        return url


def _key(url: str) -> str:
    """One address, however it was written: an X post by its status id, a page by host and path."""
    m = re.search(r"(?:twitter|x)\.com/[^/\s]+/status/(\d+)", url)
    if m:
        return "x:" + m.group(1)
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ""
    return ((parts.hostname or "").removeprefix("www.") + parts.path.rstrip("/")).lower()


def _notes(vault: Path) -> list[tuple[str, dict]]:
    """(vault path, frontmatter) of every note in the PARA folders, never through a link out of the vault."""
    out = []
    for d in NOTE_DIRS:
        for p in contained(sorted((vault / d).rglob("*.md")), vault):
            if p.is_file():
                fm, _ = read_frontmatter(p)
                out.append((p.relative_to(vault).as_posix(), fm))
    return out


def notes_by_source(notes: list[tuple[str, dict]]) -> dict[str, list[str]]:
    """Source address → the notes that cite it in `source` or `sources`: an item's notes even when its
    manifest line names them in prose rather than as wikilinks."""
    index: dict[str, list[str]] = {}
    for rel, fm in notes:
        cited = [fm.get("source")] + list(fm.get("sources") or [])
        for k in {_key(str(c)) for c in cited if _web(c)} - {""}:
            index.setdefault(k, []).append(rel)
    return index


def vault_stats(vault: Path, notes: list[tuple[str, dict]], runs: list[dict], today: date) -> dict:
    per_day: Counter = Counter()
    domains: Counter = Counter()
    kinds: Counter = Counter()
    para: Counter = Counter()
    since = (today - timedelta(days=DAYS - 1)).isoformat()
    for rel, fm in notes:
        para[rel.split("/", 1)[0]] += 1
        tags = fm.get("tags") or []
        for t in tags if isinstance(tags, list) else []:
            if isinstance(t, str) and t.startswith("domain/"):
                domains[t.removeprefix("domain/")] += 1
        kinds[str(fm.get("kind") or "unsorted")] += 1
        day = str(fm.get("processed_date") or "")[:10]
        if re.match(r"\d{4}-\d{2}-\d{2}$", day) and day >= since and fm.get("processed_date_estimated") is not True:
            per_day[day] += 1
    archive = sum(1 for p in contained((vault / "05_Archive").glob("*/*--FULLCAPTURE.md"), vault) if p.is_file())
    media = sum(1 for p in contained((vault / MEDIA).glob("*"), vault) if p.is_file()) if (vault / MEDIA).is_dir() else 0
    inbox = sum(1 for p in contained((vault / "01_Capture").glob("*.md"), vault) if p.is_file())
    reader = 0
    if (vault / ARCHIVED).is_file():
        reader = sum(1 for line in (vault / ARCHIVED).read_text(encoding="utf-8").splitlines() if '"archived"' in line)
    highlights = 0
    if (vault / INGESTED).is_file():
        highlights = sum(1 for line in (vault / INGESTED).read_text(encoding="utf-8").splitlines() if '"highlight_of"' in line)
    items = [it for r in runs for it in r["items"]]
    week = sum(n for d, n in per_day.items() if d >= (today - timedelta(days=6)).isoformat())
    return {"notes": len(notes), "para": para, "domains": domains, "kinds": kinds, "per_day": per_day, "week": week,
            "archive": archive, "media": media, "inbox": inbox, "reader": reader, "runs": len(runs),
            "imported": len(items), "highlights": highlights,
            "tweets": sum(1 for it in items if it.get("category") == "tweet")}


def _columns(per_day: Counter, today: date, run_day: str) -> str:
    """Distilled per day, the last 30 days, as inline SVG; the run's own day in the run colour."""
    days = [(today - timedelta(days=DAYS - 1 - i)).isoformat() for i in range(DAYS)]
    top = max([per_day.get(d, 0) for d in days] + [4])
    step = 5 if top <= 25 else 10 if top <= 60 else 25
    top = -(-top // step) * step
    w, h, left, bottom, gap = 640, 170, 30, 22, 3
    bw = (w - left) / DAYS
    out = [f'<svg class="chart" viewBox="0 0 {w} {h}" role="img" aria-label="Notes distilled per day, last {DAYS} days">']
    for v in range(0, top + 1, step):
        y = 8 + (h - bottom - 8) * (1 - v / top)
        out.append(f'<line class="ax" x1="{left}" x2="{w}" y1="{y:.1f}" y2="{y:.1f}"/>'
                   f'<text x="{left - 6}" y="{y + 3.5:.1f}" text-anchor="end">{v}</text>')
    for i, d in enumerate(days):
        n = per_day.get(d, 0)
        bh = (h - bottom - 8) * n / top
        x = left + i * bw + gap / 2
        cls = "bar run" if d == run_day else "bar"
        if n:
            out.append(f'<rect class="{cls}" x="{x:.1f}" y="{h - bottom - bh:.1f}" width="{bw - gap:.1f}" height="{bh:.1f}" rx="2">'
                       f"<title>{d}: {n} note{'s' if n != 1 else ''}</title></rect>")
        if i % 7 == 2 or d == days[-1]:
            label = "today" if d == today.isoformat() else f"{d[8:]}.{d[5:7]}"
            anchor, lx = ("end", x + bw - gap) if d == days[-1] else ("middle", x + (bw - gap) / 2)
            out.append(f'<text x="{lx:.1f}" y="{h - 6}" text-anchor="{anchor}">{label}</text>')
    return "".join(out) + "</svg>"


def _hbars(counter: Counter, limit: int) -> str:
    rows = counter.most_common(limit)
    top = max([n for _, n in rows] + [1])
    return '<ul class="hbars">' + "".join(
        f'<li><span class="n" title="{escape(k)}">{escape(k)}</span><span class="t"><span class="f" style="width:{max(2, 100 * n / top):.1f}%"></span></span>'
        f'<span class="c">{n}</span></li>' for k, n in rows) + "</ul>"


def _para(para: Counter) -> str:
    total = sum(para.values()) or 1
    segs = "".join(f'<i style="width:{100 * para.get(k, 0) / total:.2f}%;background:var(--p{i + 1})" title="{label}: {para.get(k, 0)}"></i>'
                   for i, (k, label) in enumerate(PARA))
    legend = "".join(f'<span><span class="sw" style="background:var(--p{i + 1})"></span>{label} <b class="num">{para.get(k, 0)}</b></span>'
                     for i, (k, label) in enumerate(PARA))
    return f'<div class="stack">{segs}</div><div class="legend">{legend}</div>'


def _capture_facts(vault: Path, capture: str) -> tuple[list[str], int]:
    path = imports_log._capture_file(vault, capture)
    if not path:
        return [], 0
    fm, _ = read_frontmatter(path)
    return [u for u in (fm.get("links") or []) if _web(u)], len(fm.get("media") or [])


def _item_html(vault: Path, it: dict, gh: str, by_source: dict[str, list[str]]) -> str:
    f = it["fate"]
    kind = imports_log.LABEL.get(str(it.get("category") or ""), str(it.get("category") or "Item").capitalize())
    title = escape(it.get("title") or it.get("capture") or it.get("found") or it.get("doc_id", "?"))
    src = _web(it.get("source"))
    head = f'<a class="title" href="{escape(src)}">{title}</a>' if src else f'<span class="title">{title}</span>'
    links, media = _capture_facts(vault, it.get("capture", ""))
    meta = [escape(x) for x in (it.get("author"), _host(src) if src else None, it.get("via"),
                                f"enrichment {it['enrichment']}" if it.get("enrichment") else None) if x]
    if media:
        meta.append(f"{media} image{'s' if media != 1 else ''} kept")
    found = list(dict.fromkeys([n if n.endswith(".md") else n + ".md" for n in f["notes"]] + by_source.get(_key(src), [])))
    notes = [_note_link(vault, n, gh) for n in found if (vault / n).is_file()]
    out = [f'<li class="item"><div class="row"><span class="kind">{escape(kind)}</span>'
           f'<span class="status s-{f["status"]}">{STATUS.get(f["status"], f["status"])}</span></div>{head}']
    if meta:
        out.append(f'<div class="meta">{" · ".join(meta)}</div>')
    out.append(f'<div class="became">→ {escape(f["detail"])}</div>')
    if notes:
        out.append(f'<div class="notelinks">{"".join(notes)}</div>')
    if links:
        out.append('<ul class="links">' + "".join(f'<li><a href="{escape(u)}">{escape(u)}</a></li>' for u in links) + "</ul>")
    return "".join(out) + "</li>"


def changed_notes(vault: Path) -> list[tuple[str, str]]:
    """(A|M, path) for every note this run added or changed: the working tree against HEAD, which
    `end` has not committed yet when the generators run."""
    rows = []
    for line in _git(vault, "status", "--porcelain", "--untracked-files=all", "--", *NOTE_DIRS).splitlines():
        code, path = line[:2], line[3:].strip().strip('"')
        if path.endswith(".md"):
            rows.append(("A" if "?" in code or "A" in code else "M", path))
    return sorted(rows, key=lambda r: (r[0], r[1].lower()))


def _headline(latest: dict | None, shown: dict | None, last: dict) -> tuple[str, str]:
    n_in = len((latest or {}).get("items") or [])
    n_out = int(last.get("distilled") or 0)
    if latest and n_in:
        return (f"<em>{n_in}</em> clipping{'s' if n_in != 1 else ''} in, <em>{n_out}</em> distilled.",
                "Read, linked, filed. Nobody had to press a button.")
    if shown:
        return ("Quiet run. <em>The inbox is clear.</em>",
                f"Nothing new since the last run, so here is the last haul: "
                f"<b>{len(shown['items'])} clipping{'s' if len(shown['items']) != 1 else ''}</b> on {escape(shown['run'])} UTC.")
    return ("First run. <em>Nothing logged yet.</em>", "The next run with new clippings fills this page.")


def render(vault: Path, run: str | None = None, today: date | None = None) -> str:
    today = today or date.today()
    runs = imports_log.resolved(vault)
    gh = _github_base(vault)
    latest = next((r for r in runs if r["run"] == run), None) if run else (runs[0] if runs else None)
    shown = latest if latest and latest["items"] else next((r for r in runs if r["items"]), None)
    try:
        last = json.loads((vault / STATE).read_text(encoding="utf-8")).get("last_run") or {}
    except (OSError, json.JSONDecodeError):
        last = {}
    when = (latest or {}).get("run") or run or datetime.now().strftime("%Y-%m-%d %H:%M")
    notes = _notes(vault)
    stats = vault_stats(vault, notes, runs, today)
    items = (shown or {}).get("items") or []
    by_source = notes_by_source(notes) if items else {}
    counts = {s: sum(1 for it in items if it["fate"]["status"] == s) for s in STATUS}
    written = changed_notes(vault)
    h1, sub = _headline(latest, shown, last)

    big = [("hot", stats["notes"], "notes in the vault"), ("", stats["week"], "distilled in the last 7 days"),
           ("", stats["imported"], "clippings logged"), ("", stats["media"], "images kept")]
    out = [f"<title>Last Pipeline Run</title>{STYLE}<div class=\"wrap\">",
           f'<header class="hero"><div class="brand">{MARK}<span><b>agentic-toolkit</b> · run report · The Void</span></div>',
           f"<h1>{h1}</h1><p>{sub}</p>",
           f'<p>Run <b class="num">{escape(when)} UTC</b> · {last.get("distilled", 0)} distilled, {last.get("dropped", 0)} dropped, '
           f'{last.get("failed", 0)} failed · <b class="num">{stats["inbox"]}</b> waiting in the inbox</p>',
           '<ul class="big">' + "".join(f'<li class="{c}"><b>{v:,}</b><span>{label}</span></li>' for c, v, label in big) + "</ul></header>"]

    out.append('<section style="display:grid;gap:12px"><div><h2>Vault vitals</h2>'
               '<p class="lede">The knowledge base, by the numbers, as of this run.</p></div><div class="vitals">')
    out.append(f'<div class="panel v-wide"><h3><span>Distilled per day</span><span>last {DAYS} days</span></h3>'
               f'{_columns(stats["per_day"], today, when[:10])}'
               '<div class="legend"><span><span class="sw" style="background:var(--accent)"></span>notes distilled</span>'
               '<span><span class="sw" style="background:var(--run)"></span>this run\'s day</span></div></div>')
    facts = [(stats["archive"], "clippings kept whole"), (stats["reader"], "archived in Reader"),
             (stats["highlights"], "Reader highlights kept"), (stats["runs"], "runs logged")]
    out.append('<div class="panel v-side"><h3><span>Provenance</span></h3><dl class="facts">' + "".join(
        f"<div><dt>{label}</dt><dd>{v:,}</dd></div>" for v, label in facts) + "</dl></div>")
    out.append(f'<div class="panel v-half"><h3><span>Where notes live</span><span>{stats["notes"]:,}</span></h3>{_para(stats["para"])}'
               f'<h3 style="margin-top:6px"><span>Kinds</span></h3>{_hbars(stats["kinds"], 6)}</div>')
    out.append(f'<div class="panel v-half"><h3><span>Domains</span><span>top 8</span></h3>{_hbars(stats["domains"], 8)}</div>')
    out.append("</div></section>")

    if items:
        title = "What came in this run" if shown is latest else f"What came in on {escape(shown['run'])} UTC"
        tally = " · ".join(f"{n} {STATUS[s].lower()}" for s, n in counts.items() if n)
        out.append(f'<section style="display:grid;gap:12px"><div><h2>{title}</h2><p class="lede">{len(items)} '
                   f'item{"s" if len(items) != 1 else ""}: {tally}. Each with its source, the links it pointed at, and the notes it became.</p></div>'
                   '<ul class="items">' + "".join(_item_html(vault, it, gh, by_source) for it in items) + "</ul></section>")
    out.append(f'<section class="panel"><h3><span>Notes this run wrote</span><span>{len(written)}</span></h3>')
    if written:
        out.append('<ul class="notes">' + "".join(
            f'<li><span class="tag {"new" if c == "A" else "changed"}">{"new" if c == "A" else "changed"}</span>{_note_link(vault, p, gh)}</li>'
            for c, p in written) + "</ul>")
    else:
        out.append('<p class="empty">None this time. The vault was already up to date.</p>')
    out.append("</section>")
    every = " · ".join(f'<a href="{escape(gh + p)}">{p}</a>' if gh else p for p in ("Imports.md", "Dashboard.html", "Index.md"))
    out.append(f"<footer><span><b>agentic-toolkit</b> reads, links and files, so the vault keeps up without you.</span>"
               f"<span>Rebuilt and republished after every successful run; the previous report is replaced. "
               f"The long view: {every}.</span></footer></div>")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", help="the run to report (default: the latest in the imports log)")
    ap.add_argument("--today", help="YYYY-MM-DD (default: today)")
    args = ap.parse_args()
    vault = require_vault()
    atomic_write(vault / OUT, render(vault, args.run, date.fromisoformat(args.today) if args.today else None))
    url = profile_value(vault, "report_artifact_url")
    print(f"{OUT}: written" + (f"; publish to {url}" if url else "; no report_artifact_url set"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
