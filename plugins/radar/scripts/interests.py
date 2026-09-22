"""What the radar judges against: the owner's interests.

Two sources, merged:
- the interests note (profile key `interests_note`, default `03_Areas/Trend Radar Profile.md`):
  frontmatter `interests:`, a list of `{name, gloss, tags, queries}`. `gloss` is one sentence
  saying what the interest *is*; `queries` are search strings for discovery;
- Portfolio epics through the `td` CLI, when `todoist_project_id` is set: top-level open tasks in
  the sections named by `todoist_sections` (default Doing, Next, Waiting), the first sentence of
  the description's `What:` line as gloss. Off when the key is unset or `td` is absent.

Only `name` and `gloss` ever enter a judgment's state; `queries` drive sources, never judgments.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from vault_utils import UnparseableFrontmatter, profile_value, read_frontmatter

DEFAULT_INTERESTS_NOTE = "03_Areas/Trend Radar Profile.md"
DEFAULT_TODOIST_SECTIONS = "Doing,Next,Waiting"
TD_TIMEOUT = 60


@dataclass(frozen=True)
class Interest:
    id: str
    name: str
    gloss: str = ""
    queries: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    todoist_task_id: str | None = None

    def state(self) -> dict[str, str]:
        """The only part of an interest a judgment backend sees."""
        return {"name": self.name, "gloss": self.gloss}


def slug(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-") or "interest"


def _unique(interests: list[Interest]) -> list[Interest]:
    seen: set[str] = set()
    out = []
    for it in interests:
        iid, n = it.id, 2
        while iid in seen:
            iid, n = f"{it.id}-{n}", n + 1
        seen.add(iid)
        out.append(it if iid == it.id else Interest(iid, it.name, it.gloss, it.queries, it.tags, it.todoist_task_id))
    return out


def from_note(vault: Path) -> list[Interest]:
    rel = str(profile_value(vault, "interests_note", DEFAULT_INTERESTS_NOTE))
    path = vault / rel
    if not path.is_file():
        return []
    try:
        fm, _ = read_frontmatter(path, strict=True)
    except UnparseableFrontmatter:
        return []
    out = []
    for entry in fm.get("interests") or []:
        if not isinstance(entry, dict) or not str(entry.get("name") or "").strip():
            continue
        name = str(entry["name"]).strip()
        out.append(Interest(
            id=slug(name),
            name=name,
            gloss=str(entry.get("gloss") or "").strip(),
            queries=tuple(str(q) for q in entry.get("queries") or []),
            tags=tuple(str(t) for t in entry.get("tags") or []),
        ))
    return out


def _run_td(args: list[str]) -> list[dict]:
    """The one call out to `td`. Evals replace it with a stub."""
    if not shutil.which("td"):
        raise FileNotFoundError("td")
    proc = subprocess.run(["td", *args, "--json"], capture_output=True, text=True, timeout=TD_TIMEOUT, check=True)
    data = json.loads(proc.stdout or "[]")
    return data.get("results", []) if isinstance(data, dict) else data


def _what_sentence(description: str) -> str:
    m = re.search(r"^\s*What:\s*(.+)$", description or "", re.M)
    if not m:
        return ""
    first = re.split(r"(?<=[.!?])\s", m.group(1).strip(), maxsplit=1)[0]
    return first.strip()


def from_todoist(vault: Path) -> list[Interest]:
    project = str(profile_value(vault, "todoist_project_id", "") or "").strip()
    if not project:
        return []
    wanted = {s.strip().lower() for s in str(profile_value(vault, "todoist_sections", DEFAULT_TODOIST_SECTIONS)).split(",")}
    try:
        sections = {s["id"] for s in _run_td(["section", "list", f"id:{project}"]) if str(s.get("name", "")).lower() in wanted}
        tasks = _run_td(["task", "list", "--project", f"id:{project}", "--full", "--all"])
    except (subprocess.SubprocessError, OSError, json.JSONDecodeError, KeyError):
        return []
    out = []
    for t in tasks:
        if t.get("parentId") or t.get("checked") or t.get("sectionId") not in sections:
            continue
        name = str(t.get("content") or "").strip()
        if name:
            out.append(Interest(id="epic-" + slug(name, 34), name=name,
                                gloss=_what_sentence(str(t.get("description") or "")), todoist_task_id=str(t["id"])))
    return out


def load(vault: Path) -> list[Interest]:
    return _unique(from_note(vault) + from_todoist(vault))
