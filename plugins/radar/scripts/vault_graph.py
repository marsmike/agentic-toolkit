"""The owner's knowledge graph as a signal: how firmly a named thing is anchored in what the owner
already knows, and where his graph is growing this week.

Two parts, both through gaiafield's CLI (`contract/KNOWLEDGE_API.md`: JSON out, never its
database directly), after an incremental `gaiafield index`:
- **Anchors.** Every content note (02–04) is indexed by the entity keys of its H1, its filename
  and its specific tags, from any date. A named thing's anchors are the notes with its key; their
  depth-1 neighbourhood says how connected it is, and the neighbours most of them share are its
  hubs ("connects to"). A thing with no anchor is a blind spot, whatever the week brought.
- **Growing hubs.** The notes each of this week's new notes links to, counted against the mean of
  the four weeks before: the places the graph is thickening now.

Without a gaiafield binary the anchors still come from the files, the neighbourhood is empty and
the status says `skipped`. Nothing is written to the vault except gaiafield's own ignored index
(`.gaiafield/`), which the pipeline builds anyway. Nothing leaves the machine.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import entities
from vault_utils import UnparseableFrontmatter, contained, read_frontmatter

CONTENT_DIRS = ("02_Projects", "03_Areas", "04_Resources")
MAX_ANCHORS = 8          # notes asked about per named thing
MAX_GROWTH_NOTES = 400   # notes asked about for growing hubs, newest first
INDEX_TIMEOUT = 300
CALL_TIMEOUT = 30
_H1 = re.compile(r"^#\s+(.+)$", re.M)
_NOISE_TAG = re.compile(r"^(domain|readwise|status|source|via|kind|maturity)/|^w\d{2}-\d{4}$|^\d{4}")


def binary() -> str | None:
    """Mirrors the obsidian plugin's `graph.gaiafield_binary` (plugins stay self-contained):
    `TOOLKIT_GAIAFIELD_BIN`, then PATH, then the `toolkit engines install` directory."""
    env = os.environ.get("TOOLKIT_GAIAFIELD_BIN")
    if env:
        return env
    found = shutil.which("gaiafield")
    if found:
        return found
    xdg = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    path = base / "agentic-toolkit" / "bin" / ("gaiafield.exe" if os.name == "nt" else "gaiafield")
    return str(path) if path.is_file() else None


def _run(args: list[str], timeout: int = CALL_TIMEOUT) -> Any:
    """The one call out to gaiafield. Evals replace it with a stub. Raises on any failure."""
    exe = binary()
    if exe is None:
        raise FileNotFoundError("gaiafield")
    proc = subprocess.run([exe, *args, "--json"], capture_output=True, text=True, timeout=timeout, check=True)
    return json.loads(proc.stdout)


class Graph:
    """Neighbour lookups with a cache; `ok` is False when the engine is absent or failed."""

    def __init__(self, vault: Path):
        self.vault = vault
        self.cache: dict[tuple[str, str], list[dict]] = {}
        self.status: dict[str, Any] = {"status": "ok", "detail": ""}
        try:
            idx = _run(["index", "--vault", str(vault)], INDEX_TIMEOUT)
            stats = _run(["stats", "--vault", str(vault)])
            self.status.update(nodes=stats.get("nodes"), edges=stats.get("edges"), indexed=idx.get("total_nodes"))
            self.in_degree = {r["path"]: r.get("in_degree", 0) for r in stats.get("top_linked") or []}
            self.ok = True
        except FileNotFoundError:
            self.status = {"status": "skipped", "detail": "no gaiafield binary (toolkit engines install)"}
            self.ok = False
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError) as e:
            self.status = {"status": "failed", "detail": str(e)[:200]}
            self.ok = False

    def neighbors(self, path: str, direction: str = "both") -> list[dict]:
        if not self.ok:
            return []
        k = (path, direction)
        if k not in self.cache:
            try:
                rows = _run(["neighbors", path, "--vault", str(self.vault), "--depth", "1", "--direction", direction])
                self.cache[k] = [r for r in rows if isinstance(r, dict) and r.get("path")]
            except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
                self.cache[k] = []
        return self.cache[k]


def _date(fm: dict) -> str | None:
    for field in ("created", "processed_date"):
        v = str(fm.get(field) or "")[:10]
        try:
            date.fromisoformat(v)
            return v
        except ValueError:
            continue
    return None


def note_index(vault: Path) -> tuple[dict[str, list[str]], dict[str, dict]]:
    """(entity key -> note paths, note path -> {title, created}), over every content note."""
    by_key: dict[str, list[str]] = defaultdict(list)
    notes: dict[str, dict] = {}
    for top in CONTENT_DIRS:
        root = vault / top
        if not root.is_dir():
            continue
        for path in contained(sorted(root.rglob("*.md")), vault):
            rel = path.relative_to(vault).as_posix()
            try:
                fm, body = read_frontmatter(path)
            except (UnparseableFrontmatter, OSError, UnicodeDecodeError):
                continue
            m = _H1.search(body)
            title = m.group(1).strip() if m else path.stem
            notes[rel] = {"title": title, "created": _date(fm)}
            tags = fm.get("tags") or []
            tags = [str(t) for t in (tags if isinstance(tags, list) else [tags])]
            keys = {entities.key(n) for n in entities.from_title(title) + entities.from_title(path.stem.replace("-", " "))}
            keys |= {entities.key(t) for t in tags if not _NOISE_TAG.search(t.casefold())}
            for k in keys:
                if len(k) >= 3 and k not in entities.GENERIC:
                    by_key[k].append(rel)
    return by_key, notes


def anchor(graph: Graph, notes: dict[str, dict], paths: list[str]) -> dict[str, Any]:
    """How firmly a thing sits in the graph: its notes, their joint neighbourhood, shared hubs."""
    paths = sorted(paths, key=lambda p: notes.get(p, {}).get("created") or "", reverse=True)[:MAX_ANCHORS]
    hood: set[str] = set()
    hubs: Counter = Counter()
    for p in paths:
        for n in graph.neighbors(p):
            if n["path"] in paths:
                continue
            hood.add(n["path"])
            hubs[n["path"]] += 1
    top = sorted(hubs, key=lambda h: (-hubs[h], -graph.in_degree.get(h, 0) if graph.ok else 0, h))[:4] if graph.ok else []
    return {
        "notes": [{"title": notes[p]["title"], "path": p} for p in paths if p in notes],
        "neighborhood": len(hood),
        "hubs": [{"title": notes.get(h, {}).get("title") or Path(h).stem, "path": h, "shared": hubs[h]} for h in top],
    }


def growing_hubs(graph: Graph, notes: dict[str, dict], today: date, limit: int = 10) -> list[dict]:
    """Hubs this week's new notes link to, against the mean week of the four before."""
    if not graph.ok:
        return []
    week_from = (today - timedelta(days=6)).isoformat()
    base_from = (today - timedelta(days=34)).isoformat()
    recent = sorted(((n["created"], p) for p, n in notes.items() if n["created"] and n["created"] >= base_from),
                    reverse=True)[:MAX_GROWTH_NOTES]
    now_c: Counter = Counter()
    base_c: Counter = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    for created, p in recent:
        for n in graph.neighbors(p, "out"):
            if created >= week_from:
                now_c[n["path"]] += 1
                if len(examples[n["path"]]) < 3:
                    examples[n["path"]].append(p)
            else:
                base_c[n["path"]] += 1
    rows = []
    for hub, c in now_c.items():
        base = base_c[hub] / 4
        if c < 2 or c < 2 * base + 1:
            continue
        rows.append({"title": notes.get(hub, {}).get("title") or Path(hub).stem, "path": hub, "this_week": c,
                     "baseline": round(base, 2), "new": base == 0,
                     "examples": [{"title": notes[e]["title"], "path": e} for e in examples[hub] if e in notes]})
    rows.sort(key=lambda r: (-(r["this_week"] - r["baseline"]), r["path"]))
    return rows[:limit]


def build(vault: Path, now: datetime) -> tuple[Graph, dict[str, list[str]], dict[str, dict], dict[str, Any]]:
    """(graph, key -> notes, notes, the page's `graph` section)."""
    graph = Graph(vault)
    by_key, notes = note_index(vault)
    section = {**graph.status, "notes": len(notes), "growing_hubs": growing_hubs(graph, notes, now.date())}
    return graph, by_key, notes, section
