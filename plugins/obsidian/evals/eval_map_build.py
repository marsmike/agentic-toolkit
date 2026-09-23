"""Eval: map_build.py writes one map and one canvas per domain, from the notes alone.

In a sandbox copy of the example vault, five notes form a fixture domain `domain/evalhub`: Hub is
linked from three notes, Second from one, Fresh was distilled yesterday and Old 100 days ago; a
config block gives the domain a title, an intro and a "Concepts" section. After a build:

1. hubs      — Start here lists Hub before Second; the unlinked notes are not in it
2. new       — New lists Fresh and not Old
3. grouping  — concepts sit under the config's "Concepts", guides under "Guide"; the intro is there
4. canvas    — every map's canvas is valid JSON Canvas, every file card points at an existing file,
               every edge joins two cards
5. hygiene   — no map links into 00_Memory/ or 01_Capture/; a map this generator wrote for a
               domain that no longer exists is removed
6. idempotent — a second build changes no file
7. untracked — a note git ignores is on no map, not in Index.md, not scanned by lint, and its
               old Index line is not reported as dangling (a clone never has it)
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

NAME = "map_build"
TODAY = "2026-09-23"
NOTES = {
    "Hub": ("concept", "2026-01-10", "The hub everyone links to.", ""),
    "Second": ("concept", "2026-02-01", "Linked once.", "[[Hub]]"),
    "Fresh": ("guide", "2026-09-22", "Distilled yesterday.", "[[Hub]] [[Second]]"),
    "Old": ("guide", "2026-06-15", "Distilled long ago.", "[[Hub]]"),
    "Loner": ("guide", "2026-03-01", "Links nowhere.", ""),
}
CONFIG = """---
description: Map titles, intros and sections per domain
---

## evalhub
title: Eval Hub
The fixture domain for eval_map_build.

- Concepts: concept
"""


def _note(kind: str, when: str, desc: str, body: str) -> str:
    return (f"---\ndescription: {desc}\nkind: {kind}\nstatus: distilled\nprocessed_date: {when}\n"
            f"tags:\n  - domain/evalhub\n---\n\n# Note\n\n{body}\n")


def _section(text: str, heading: str) -> str:
    m = re.search(rf"^## {re.escape(heading)}.*?\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1) if m else ""


def run(vault: Path) -> dict:
    import sys
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import map_build

    problems: list[str] = []
    sandbox, saved = None, os.environ.get("TOOLKIT_VAULT")
    try:
        sandbox = make_sandbox(vault)
        os.environ["TOOLKIT_VAULT"] = str(sandbox)
        folder = sandbox / "04_Resources" / "EvalHub"
        folder.mkdir(parents=True)
        for name, spec in NOTES.items():
            (folder / f"{name}.md").write_text(_note(*spec), encoding="utf-8")
        (sandbox / "Config" / "toolkit" / "maps.md").write_text(CONFIG, encoding="utf-8")
        maps = sandbox / "Maps"
        maps.mkdir(exist_ok=True)
        (maps / "gone.md").write_text("---\ngenerated_by: map_build.py\ndomain: gone\n---\n# Gone\n", encoding="utf-8")
        (maps / "gone.canvas").write_text('{"nodes": [], "edges": []}\n', encoding="utf-8")

        map_build.main(["--today", TODAY])
        text = (maps / "evalhub.md").read_text(encoding="utf-8") if (maps / "evalhub.md").is_file() else ""
        if not text:
            problems.append("no Maps/evalhub.md")

        # 1. hubs
        start = re.findall(r"\|(\w+)\]\]", _section(text, "Start here"))
        if start[:2] != ["Hub", "Second"] or "Loner" in start:
            problems.append(f"phase 1: Start here should open with Hub, Second; got {start}")
        # 2. new
        new = re.findall(r"\|(\w+)\]\]", _section(text, "New"))
        if "Fresh" not in new or "Old" in new:
            problems.append(f"phase 2: New should hold Fresh and not Old; got {new}")
        # 3. grouping
        concepts = re.search(r"^### Concepts\n\n(.*?)(?=^### |^## |\Z)", text, re.M | re.S)
        guides = re.search(r"^### Guide\n\n(.*?)(?=^### |^## |\Z)", text, re.M | re.S)
        if not concepts or "|Hub]]" not in concepts.group(1) or not guides or "|Fresh]]" not in guides.group(1):
            problems.append("phase 3: concepts under the config's 'Concepts', guides under 'Guide'")
        if "# Eval Hub" not in text or "The fixture domain for eval_map_build." not in text:
            problems.append("phase 3: the config's title and intro must head the map")
        # 4. canvas
        for canvas in sorted(maps.glob("*.canvas")):
            try:
                data = json.loads(canvas.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                problems.append(f"phase 4: {canvas.name} is not JSON")
                continue
            ids = {n["id"] for n in data.get("nodes", [])}
            missing = [n["file"] for n in data.get("nodes", []) if n.get("type") == "file" and not (sandbox / n["file"]).is_file()]
            loose = [e["id"] for e in data.get("edges", []) if e.get("fromNode") not in ids or e.get("toNode") not in ids]
            if missing or loose or any(not {"id", "type", "x", "y", "width", "height"} <= n.keys() for n in data.get("nodes", [])):
                problems.append(f"phase 4: {canvas.name}: {len(missing)} cards on missing files, {len(loose)} loose edges")
        # 5. hygiene
        for md in maps.glob("*.md"):
            if re.search(r"\[\[(00_Memory|01_Capture)/", md.read_text(encoding="utf-8")):
                problems.append(f"phase 5: {md.name} links into 00_Memory or 01_Capture")
        if (maps / "gone.md").exists() or (maps / "gone.canvas").exists():
            problems.append("phase 5: a stale generated map must be removed")
        # 6. idempotent
        before = {p.name: p.stat().st_mtime_ns for p in maps.iterdir()}
        files, _ = map_build.build(sandbox, map_build.date.fromisoformat(TODAY))
        changed = map_build.write(sandbox, files)
        after = {p.name: p.stat().st_mtime_ns for p in maps.iterdir()}
        if changed["changed"] or changed["removed"] or before != after:
            problems.append(f"phase 6: a second build changed {changed}")
        # 7. untracked by git: a note git ignores is on no map and not in Index.md
        import subprocess

        import index_build
        from vault_utils import git_ignored
        (sandbox / ".gitignore").write_text("04_Resources/EvalHub/Loner.md\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(sandbox), "init", "-q"], check=False)
        git_ignored.cache_clear()
        map_build.main(["--today", TODAY])
        index_build.main([])
        if "|Loner]]" in (maps / "evalhub.md").read_text(encoding="utf-8") or \
                "EvalHub/Loner|" in (sandbox / "Index.md").read_text(encoding="utf-8"):
            problems.append("phase 7: a git-ignored note must be on no map and not in Index.md")
        import vault_lint
        notes, _, _ = vault_lint.scan_vault(sandbox)
        index = sandbox / "Index.md"
        index.write_text(index.read_text(encoding="utf-8") + "- [[04_Resources/EvalHub/Loner|Loner]] — stale\n", encoding="utf-8")
        drift = vault_lint.find_index_drift(sandbox, notes)
        if "04_Resources/EvalHub/Loner" in notes or any(d["path"].endswith("EvalHub/Loner") for d in drift["dangling"]):
            problems.append("phase 7: lint must neither scan a git-ignored note nor report its old Index line as dangling")
        git_ignored.cache_clear()
    finally:
        if saved is None:
            os.environ.pop("TOOLKIT_VAULT", None)
        else:
            os.environ["TOOLKIT_VAULT"] = saved
        if sandbox is not None:
            teardown_sandbox(sandbox)
    return {"eval": NAME, "pass": not problems,
            "detail": "; ".join(problems) if problems else "hubs, new, config sections, valid canvases, no stale maps, idempotent"}
