#!/usr/bin/env python3
"""Build the last run's ingestion report: `00_Memory/last-run-report.html`, one static page.

    uv run scripts/report_build.py [--run "YYYY-MM-DD HH:MM"]

A generator in `end`, so it describes the run that is ending: what it imported, where each item
came from (its source and every link ingest expanded), the images it kept, what each became (the
note on GitHub and in Obsidian), and every note the run wrote or changed. A run that imported
nothing says so and shows the last run that did. The cloud routine publishes this file to one
Claude artifact after every successful run (`report_artifact_url` in the profile), so the artifact
always holds the latest report. [earned: 2026-09-25, owner's request — publish the last ingestion
report as an artifact, overwritten by each successful run]

The file follows the Artifact page contract: no doctype, html, head or body tags (the publisher
wraps it), a <title> first, every style inline, no script. Every value is HTML-escaped: titles and
sources are other people's words.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit

import imports_log
from vault_utils import atomic_write, profile_value, read_frontmatter, require_vault

OUT = Path("00_Memory") / "last-run-report.html"
STATE = Path("00_Memory") / "pipeline-state.json"
NOTE_DIRS = ("02_Projects/", "03_Areas/", "04_Resources/")
STATUS = {"distilled": "Distilled", "known": "Already in vault", "dropped": "Dropped", "duplicate": "Duplicate",
          "archived": "Archived", "waiting": "Waiting", "missing": "Missing"}

STYLE = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=JetBrains+Mono:wght@400;600&family=Newsreader:opsz,wght@6..72,500;6..72,650&display=swap">
<style>
:root {
  --paper: #f7f8f6; --sheet: #ffffff; --ink: #1c2230; --ink-2: #4a5263; --muted: #7a8292; --rule: #dde1e6;
  --accent: #1f5f8b; --accent-soft: #e4eef5; --good: #1d7a45; --warn: #9a6a00; --bad: #b3261e;
  --chip: #eef1f4;
  --serif: "Newsreader", Georgia, "Times New Roman", serif;
  --sans: "Atkinson Hyperlegible", -apple-system, "Segoe UI", system-ui, sans-serif;
  --mono: "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --paper: #12161d; --sheet: #181d26; --ink: #e8ebf0; --ink-2: #b7bdc8; --muted: #858c99; --rule: #2a313d;
    --accent: #7db4dc; --accent-soft: #1d2a36; --good: #5cc28a; --warn: #e0b04a; --bad: #f08a80; --chip: #222935;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --paper: #12161d; --sheet: #181d26; --ink: #e8ebf0; --ink-2: #b7bdc8; --muted: #858c99; --rule: #2a313d;
  --accent: #7db4dc; --accent-soft: #1d2a36; --good: #5cc28a; --warn: #e0b04a; --bad: #f08a80; --chip: #222935;
}
body { background: var(--paper); color: var(--ink); font: 15px/1.55 var(--sans); }
.wrap { max-width: 880px; margin: 0 auto; padding-inline: 16px; padding-block: 28px 56px; display: grid; gap: 28px; }
header { display: grid; gap: 6px; }
section { display: grid; gap: 12px; } section h2 { margin: 0; }
.eyebrow { font: 600 11.5px/1 var(--mono); letter-spacing: .08em; text-transform: uppercase; color: var(--accent); }
h1 { font: 650 clamp(26px, 5vw, 34px)/1.15 var(--serif); margin: 0; text-wrap: balance; }
h2 { font: 650 20px/1.25 var(--serif); margin: 0 0 12px; text-wrap: balance; }
.sub { color: var(--ink-2); margin: 0; }
.summary { font: 13px/1.5 var(--mono); color: var(--ink-2); background: var(--sheet); border: 1px solid var(--rule);
  border-radius: 8px; padding: 10px 12px; overflow-wrap: anywhere; }
.counts { display: flex; flex-wrap: wrap; gap: 8px 22px; margin: 0; padding: 0; list-style: none; }
.counts li { display: grid; gap: 2px; }
.counts b { font: 600 22px/1 var(--mono); font-variant-numeric: tabular-nums; }
.counts span { font-size: 12.5px; color: var(--muted); }
.items { list-style: none; margin: 0; padding: 0; display: grid; gap: 0; }
.item { display: grid; gap: 6px; padding: 14px 0; border-top: 1px solid var(--rule); }
.item:first-child { border-top: 0; padding-top: 0; }
.row { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 10px; }
.kind { font: 600 10.5px/1 var(--mono); letter-spacing: .07em; text-transform: uppercase; color: var(--ink-2);
  background: var(--chip); border-radius: 4px; padding: 4px 6px; }
.status { font: 600 10.5px/1 var(--mono); letter-spacing: .07em; text-transform: uppercase; border-radius: 4px; padding: 4px 6px;
  border: 1px solid currentColor; }
.s-distilled, .s-known { color: var(--good); } .s-waiting, .s-archived, .s-duplicate { color: var(--warn); }
.s-dropped { color: var(--muted); } .s-missing { color: var(--bad); }
.title { font-weight: 700; color: var(--ink); text-decoration: none; overflow-wrap: anywhere; }
a { color: var(--accent); }
a.title:hover, a.title:focus-visible { color: var(--accent); text-decoration: underline; }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; border-radius: 2px; }
.meta { font-size: 13px; color: var(--muted); }
.became { font-size: 14px; color: var(--ink-2); }
.became a { font-weight: 700; }
.links { margin: 0; padding: 0; list-style: none; display: grid; gap: 3px; font: 12.5px/1.45 var(--mono); }
.links li { overflow-wrap: anywhere; color: var(--muted); }
.links li::before { content: "↳ "; color: var(--muted); }
.card { background: var(--sheet); border: 1px solid var(--rule); border-radius: 10px; padding: 18px; }
.notes { margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; }
.notes li { display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: baseline; }
.tag { font: 600 10.5px/1 var(--mono); letter-spacing: .06em; text-transform: uppercase; color: var(--muted); min-width: 64px; }
.alt { font-size: 12.5px; color: var(--muted); }
.empty { color: var(--ink-2); margin: 0; }
footer { font-size: 12.5px; color: var(--muted); }
@media (prefers-reduced-motion: reduce) { * { scroll-behavior: auto; } }
</style>
"""


def _git(vault: Path, *args: str) -> str:
    run = subprocess.run(["git", "-C", str(vault), *args], capture_output=True, text=True, check=False)
    return run.stdout if run.returncode == 0 else ""


def _github_base(vault: Path) -> str:
    """`https://github.com/<owner>/<repo>/blob/<branch>/` for a GitHub remote, else ""."""
    remote = _git(vault, "remote", "get-url", "origin").strip()
    m = re.search(r"github\.com[:/]([^/]+)/([^/]+?)(?:\.git)?$", remote)
    branch = _git(vault, "rev-parse", "--abbrev-ref", "HEAD").strip() or "main"
    return f"https://github.com/{m.group(1)}/{m.group(2)}/blob/{branch}/" if m else ""


def _note_links(vault: Path, rel: str, gh: str) -> str:
    rel = rel if rel.endswith(".md") else rel + ".md"
    name = escape(Path(rel).stem.replace("-", " "))
    obsidian = f"obsidian://open?vault={quote(vault.name)}&file={quote(rel.removesuffix('.md'))}"
    head = f'<a href="{escape(gh + quote(rel))}">{name}</a>' if gh else f"<b>{name}</b>"
    return f'{head} <span class="alt">· <a href="{escape(obsidian)}">open in Obsidian</a></span>'


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


def notes_by_source(vault: Path) -> dict[str, list[str]]:
    """Source address → the notes that cite it in `source` or `sources`: an item's notes even when its
    manifest line names them in prose rather than as wikilinks."""
    index: dict[str, list[str]] = {}
    for d in NOTE_DIRS:
        for p in sorted((vault / d).rglob("*.md")):
            fm, _ = read_frontmatter(p)
            cited = [fm.get("source")] + list(fm.get("sources") or [])
            for u in {_key(str(c)) for c in cited if isinstance(c, str) and c.startswith("http")} - {""}:
                index.setdefault(u, []).append(p.relative_to(vault).as_posix())
    return index


def _capture_links(vault: Path, capture: str) -> tuple[list[str], int]:
    path = imports_log._capture_file(vault, capture)
    if not path:
        return [], 0
    fm, _ = read_frontmatter(path)
    links = [u for u in (fm.get("links") or []) if isinstance(u, str)]
    return links, len(fm.get("media") or [])


def _item_html(vault: Path, it: dict, gh: str, by_source: dict[str, list[str]]) -> str:
    f = it["fate"]
    kind = imports_log.LABEL.get(str(it.get("category") or ""), str(it.get("category") or "Item").capitalize())
    title = escape(it.get("title") or it.get("capture") or it.get("found") or it.get("doc_id", "?"))
    src = str(it.get("source") or "")
    head = f'<a class="title" href="{escape(src)}">{title}</a>' if src.startswith("http") else f'<span class="title">{title}</span>'
    meta = " · ".join(escape(x) for x in (it.get("author"), _host(src) if src.startswith("http") else None,
                                          it.get("via"), f"enrichment {it['enrichment']}" if it.get("enrichment") else None) if x)
    links, media = _capture_links(vault, it.get("capture", ""))
    if media:
        meta += (" · " if meta else "") + f"{media} image{'s' if media != 1 else ''} kept"
    found = list(dict.fromkeys([n if n.endswith(".md") else n + ".md" for n in f["notes"]]
                               + by_source.get(_key(src), [])))
    notes = " · ".join(_note_links(vault, n, gh) for n in found if (vault / n).is_file())
    became = escape(f["detail"]) + (f"<br>{notes}" if notes else "")
    out = [f'<li class="item"><div class="row"><span class="kind">{escape(kind)}</span>'
           f'<span class="status s-{f["status"]}">{STATUS.get(f["status"], f["status"])}</span>{head}</div>']
    if meta:
        out.append(f'<div class="meta">{meta}</div>')
    out.append(f'<div class="became">→ {became}</div>')
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


def render(vault: Path, run: str | None = None) -> str:
    runs = imports_log.resolved(vault)
    gh = _github_base(vault)
    latest = next((r for r in runs if r["run"] == run), None) if run else (runs[0] if runs else None)
    shown = latest if latest and latest["items"] else next((r for r in runs if r["items"]), None)
    try:
        last = json.loads((vault / STATE).read_text(encoding="utf-8")).get("last_run") or {}
    except (OSError, json.JSONDecodeError):
        last = {}
    when = (latest or {}).get("run") or run or datetime.now().strftime("%Y-%m-%d %H:%M")
    items = (shown or {}).get("items") or []
    counts = {s: sum(1 for it in items if it["fate"]["status"] == s) for s in STATUS}
    notes = changed_notes(vault)
    by_source = notes_by_source(vault) if items else {}
    body = [f"<title>Last Pipeline Run</title>{STYLE}<div class=\"wrap\">",
            '<header><div class="eyebrow">The Void · ingestion report</div>',
            f"<h1>Pipeline run {escape(when)} UTC</h1>",
            f'<p class="sub">{last.get("distilled", 0)} distilled, {last.get("dropped", 0)} dropped, '
            f'{last.get("failed", 0)} failed. Rebuilt and republished after every successful run.</p></header>']
    if latest is shown and shown:
        body.append(f"<section><h2>Imported in this run ({len(items)})</h2>")
    elif shown:
        body.append('<section><p class="empty">This run imported nothing new. Below is the last run that did.</p>'
                    f"<h2>Imported on {escape(shown['run'])} UTC ({len(items)})</h2>")
    else:
        body.append('<section><p class="empty">No imports recorded yet.</p>')
    if items:
        body.append('<ul class="counts">' + "".join(
            f"<li><b>{n}</b><span>{STATUS[s].lower()}</span></li>" for s, n in counts.items() if n) + "</ul>")
        body.append('<ul class="items" style="margin-top:16px">' + "".join(_item_html(vault, it, gh, by_source) for it in items) + "</ul>")
    body.append("</section>")
    body.append(f'<section class="card"><h2>Notes written this run ({len(notes)})</h2>')
    if notes:
        body.append('<ul class="notes">' + "".join(
            f'<li><span class="tag">{"new" if c == "A" else "changed"}</span>{_note_links(vault, p, gh)}</li>' for c, p in notes) + "</ul>")
    else:
        body.append('<p class="empty">None.</p>')
    body.append("</section>")
    links = [f'<a href="{escape(gh + "Imports.md")}">Imports.md</a>' if gh else "Imports.md",
             f'<a href="{escape(gh + "Dashboard.html")}">Dashboard.html</a>' if gh else "Dashboard.html"]
    body.append(f"<footer>Generated by report_build.py from {escape(vault.name)}. Every run: {' · '.join(links)}. "
                "Obsidian links open on a device with the vault.</footer></div>")
    return "\n".join(body) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run", help="the run to report (default: the latest in the imports log)")
    args = ap.parse_args()
    vault = require_vault()
    atomic_write(vault / OUT, render(vault, args.run))
    url = profile_value(vault, "report_artifact_url")
    print(f"{OUT}: written" + (f"; publish to {url}" if url else "; no report_artifact_url set"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
