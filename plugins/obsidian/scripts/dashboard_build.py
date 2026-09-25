#!/usr/bin/env python3
"""Build Dashboard.html: the last twelve weeks of distilling, in one self-contained page.

    uv run scripts/dashboard_build.py [--dry-run] [--json] [--today YYYY-MM-DD]

Deterministic, no model call, no network. The page embeds its data as JSON and filters in the
browser (today, yesterday, 7 / 30 / 84 days, domain, kind, source, search), so "today" is the
viewer's today even when the file was built hours earlier. Open it in a browser; each note links
back into Obsidian (`obsidian://open`).

    notes    every note in 02-04 (and root active notes) whose processed_date is a real date in the
             window; `processed_date_estimated: true` notes (a backfilled legacy date) are left out
    source   what the note came from, by its `source` address: tweet, article, video, paper, repo,
             podcast, or own (no address)
    radar    what the feeds brought (radar_ledger): worth-or-strong items, per-interest counts, strong per
             ISO week, rising interests; the page filters them by the same range as the notes
    runs     the pipeline's commits in the window (`git log --grep=^pipeline`), with their counts and
             what each imported and what became of it (imports_log.py, the data behind Imports.md)
    inbox    captures waiting in 01_Capture/

Note text reaches the page only as JSON and is rendered with textContent, never as HTML: a clip's
description is someone else's words.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import imports_log
import radar_ledger
from map_build import _date, _one_line, _tags
from vault_utils import atomic_write, contained, discover_notes, profile_value, read_frontmatter, require_vault

OUT = "Dashboard.html"
TEMPLATE = Path(__file__).resolve().parent / "dashboard_template.html"
WINDOW_DAYS = 84
DESC_CHARS = 280
RUN = re.compile(r"(\d+) distilled, (\d+) dropped, (\d+) failed")
SOURCE_HOSTS = (  # first match wins
    ("tweet", ("x.com", "twitter.com")),
    ("video", ("youtube.com", "youtu.be", "vimeo.com")),
    ("paper", ("arxiv.org", "doi.org", "openreview.net", "aclanthology.org", "biorxiv.org", "semanticscholar.org")),
    ("repo", ("github.com", "gitlab.com", "huggingface.co", "codeberg.org")),
    ("podcast", ("podcasts.apple.com", "open.spotify.com", "share.snipd.com", "overcast.fm", "pca.st")),
)


def source_type(source: object) -> str:
    url = str(source or "").strip()
    if not url.startswith("http"):
        return "own"
    host = (urlsplit(url).hostname or "").removeprefix("www.").removeprefix("m.")
    for kind, hosts in SOURCE_HOSTS:
        if any(host == h or host.endswith("." + h) for h in hosts):
            return kind
    return "paper" if url.lower().endswith(".pdf") else "article"


def notes(vault: Path, since: str) -> list[dict]:
    out = []
    for p in discover_notes(vault):
        fm, _ = read_frontmatter(p)
        day = _date(fm.get("processed_date"))
        if not day or day < since or fm.get("processed_date_estimated") is True:
            continue
        rel = p.relative_to(vault).as_posix()
        tags = _tags(fm)
        source = fm.get("source") if isinstance(fm.get("source"), str) else ""
        out.append({
            "title": p.stem,
            "path": rel,
            "day": day,
            "desc": _one_line(fm.get("description") or "", DESC_CHARS),
            "kind": str(fm.get("kind") or "").strip() or "unsorted",
            "domains": sorted({t.removeprefix("domain/") for t in tags if t.startswith("domain/")}),
            "folder": rel.split("/", 1)[0] if "/" in rel else "",
            "source": source if source.startswith("http") else "",
            "type": source_type(source),
            "author": _one_line(fm.get("author") or "", 60),
        })
    return sorted(out, key=lambda n: (n["day"], n["title"].lower()), reverse=True)


def _item(it: dict) -> dict:
    f = it["fate"]
    return {"title": _one_line(it.get("title") or it.get("capture") or it.get("found") or it.get("doc_id", ""), 140),
            "source": it.get("source") or "", "type": str(it.get("category") or ""), "via": it.get("via") or "",
            "status": f["status"], "detail": _one_line(f["detail"], 220), "notes": f["notes"][:4]}


def runs(vault: Path, since: str, imports: list[dict]) -> list[dict]:
    imported = {r["run"]: [_item(it) for it in r["items"]] for r in imports}
    if not (vault / ".git").exists():
        return []
    git = subprocess.run(["git", "-C", str(vault), "log", f"--since={since}", "--grep=^pipeline",
                          "--format=%cI%x09%h%x09%s"], capture_output=True, text=True, check=False)
    out = []
    for line in git.stdout.splitlines():
        when, sha, subject = (line.split("\t", 2) + ["", ""])[:3]
        m = RUN.search(subject)
        if m:
            key = imports_log.RUN_SUBJECT.match(subject)
            out.append({"at": when, "sha": sha, "distilled": int(m.group(1)), "dropped": int(m.group(2)),
                        "failed": int(m.group(3)), "summary": subject.split(": ", 1)[-1][:300],
                        "run": key.group(1) if key else "", "items": imported.get(key.group(1), []) if key else []})
    return out


def inbox(vault: Path) -> int:
    return sum(1 for p in contained((vault / "01_Capture").glob("*.md"), vault) if p.is_file())


def build(vault: Path, today: date) -> dict:
    since = (today - timedelta(days=WINDOW_DAYS - 1)).isoformat()
    imports = imports_log.resolved(vault)
    return {"vault": vault.name, "built": datetime.now().astimezone().isoformat(timespec="minutes"),
            "today": today.isoformat(), "window": WINDOW_DAYS, "inbox": inbox(vault),
            "report": str(profile_value(vault, "report_artifact_url") or ""),
            "notes": notes(vault, since), "runs": runs(vault, since, imports),
            "missing": sum(1 for r in imports for it in r["items"] if it["fate"]["status"] == "missing"),
            "radar": radar_ledger.load(vault, since, today)}


def render(data: dict) -> str:
    # No raw `<` in the payload, so no description can end (or open) a script element.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true", help="print the embedded data instead of a summary")
    ap.add_argument("--today", help="YYYY-MM-DD (default: today)")
    args = ap.parse_args()
    vault = require_vault()
    today = date.fromisoformat(args.today) if args.today else date.today()
    data = build(vault, today)
    if args.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    if not args.dry_run:
        atomic_write(vault / OUT, render(data))
    if not args.json:
        print(f"{OUT}: {len(data['notes'])} notes, {len(data['runs'])} runs in {WINDOW_DAYS} days"
              + (" (dry run)" if args.dry_run else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
