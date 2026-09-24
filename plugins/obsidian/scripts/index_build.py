#!/usr/bin/env python3
"""Build Index.md from the notes' own descriptions — deterministic, no model call.

    uv run scripts/index_build.py [--dry-run] [--json]

One line per active note (02_Projects, 03_Areas, 04_Resources, plus root-level notes with
`status: active` — the set vault_lint.py checks for drift), grouped `## <PARA folder>` /
`### <first subfolder>`, root notes first under `## Vault root`:

    - [[path/without/extension|Name]] — <summary> <markers>

The summary is the note's `description`, collapsed to one line. A note without one keeps its
previous Index.md summary if it had one, else gets its first prose line, and is marked ⚙
("needs a description" — improve the note, not the index line). Retrieval-verification markers
(✓ ⚠) carry over from the previous Index.md. The description is the curated one-liner search
already weights; generating a second, separate summary per note (the v1 Gemma pass) made two
texts drift apart. [earned: 2026-09-22, a 1,221-entry index with 278 bootstrap lines, 148
entries for deleted notes and 73 notes missing]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

from vault_utils import (
    _FRONTMATTER_RE,
    ACTIVE_CONTENT_FOLDERS,
    CHECK_MARK,
    COG,
    EXCLUDE_DIRS,
    WARNING,
    UnparseableFrontmatter,
    atomic_write,
    git_ignored,
    parse_existing_index,
    read_frontmatter,
    require_vault,
    root_active_notes,
)

MAX_SUMMARY = 240
ROOT = "Vault root"  # heading for root-level `status: active` notes (contract/VAULT_SCHEMA.md)
SKIP_LINE = re.compile(r"^\s*(#|>|\||!\[|```|---|\*Source:|\*\*Source|<)")


def _one_line(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text)).strip()
    return text if len(text) <= MAX_SUMMARY else text[: MAX_SUMMARY - 1].rstrip() + "…"


def _first_prose_line(body: str) -> str:
    for line in body.splitlines():
        if line.strip() and not SKIP_LINE.match(line):
            return _one_line(re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", line.strip("-* ")))
    return ""


def collect(vault: Path) -> dict[str, Path]:
    notes: dict[str, Path] = {}
    ignored = git_ignored(vault)
    for folder in ACTIVE_CONTENT_FOLDERS:
        root = vault / folder
        if not root.exists():
            continue
        for md in root.rglob("*.md"):
            if any(part in EXCLUDE_DIRS for part in md.relative_to(vault).parts[:-1]):
                continue
            if md.relative_to(vault).as_posix() in ignored:
                continue
            notes[md.relative_to(vault).with_suffix("").as_posix()] = md
    for md in root_active_notes(vault):
        if md.name not in ignored:
            notes[md.stem] = md
    return notes


def build(vault: Path) -> tuple[str, dict]:
    previous = parse_existing_index(vault / "Index.md")
    groups: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    stats = {"entries": 0, "from_description": 0, "kept_previous": 0, "first_line": 0, "empty": 0,
             "unparseable": []}
    for rel, path in sorted(collect(vault).items(), key=lambda kv: kv[0].casefold()):
        try:
            fm, body = read_frontmatter(path, strict=True)
        except UnparseableFrontmatter:
            # Its metadata lines are not prose; summarise from what follows the block.
            text = path.read_text(encoding="utf-8", errors="replace")
            fm, body = {}, text[_FRONTMATTER_RE.match(text).end():]
            stats["unparseable"].append(rel)
        prev_summary, prev_markers = previous.get(rel, ("", ""))
        markers = "".join(m for m in prev_markers if m in (CHECK_MARK, WARNING))
        desc = fm.get("description")
        if isinstance(desc, str) and desc.strip():
            summary = _one_line(desc)
            stats["from_description"] += 1
        else:
            markers = COG + markers
            if prev_summary:
                summary = prev_summary
                stats["kept_previous"] += 1
            elif first := _first_prose_line(body):
                summary = first
                stats["first_line"] += 1
            else:
                summary = "(empty note)"
                stats["empty"] += 1
        parts = rel.split("/")
        section = parts[1] if len(parts) > 2 else ""
        suffix = f" {markers}" if markers else ""
        groups[parts[0] if len(parts) > 1 else ROOT][section].append(f"- [[{rel}|{path.stem}]] — {summary}{suffix}")
        stats["entries"] += 1

    needs = stats["entries"] - stats["from_description"]
    out = ["# Vault Index", "",
           f"*Last rebuild: {date.today().isoformat()} · {stats['entries']} entries · {needs} without a description ({COG})*", ""]
    for folder in (ROOT, *ACTIVE_CONTENT_FOLDERS):
        if folder not in groups:
            continue
        out += [f"## {folder}", ""]
        sections = groups[folder]
        if "" in sections:
            out += sections[""] + [""]
        for name in sorted((s for s in sections if s), key=str.casefold):
            out += [f"### {name}"] + sections[name] + [""]
    return "\n".join(out).rstrip() + "\n", stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build Index.md from note descriptions")
    ap.add_argument("--dry-run", action="store_true", help="report what would be written, write nothing")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    vault = require_vault()
    text, stats = build(vault)
    previous = parse_existing_index(vault / "Index.md")
    current = {m.group(1) for m in re.finditer(r"^- \[\[([^\]|]+)\|", text, re.M)}
    stats["dropped"] = len(set(previous) - current)
    stats["added"] = len(current - set(previous))
    if not args.dry_run:
        atomic_write(vault / "Index.md", text)
        log_script = Path(__file__).resolve().parent / "log_vault.py"
        subprocess.run([sys.executable, str(log_script), "index", f"Index.md rebuilt ({stats['entries']} entries)"], check=False)
    print(json.dumps(stats, indent=2) if args.json else
          f"{'would write' if args.dry_run else 'wrote'} Index.md: {stats['entries']} entries "
          f"({stats['from_description']} from descriptions, {stats['entries'] - stats['from_description']} {COG}); "
          f"+{stats['added']} new, -{stats['dropped']} dropped")
    if stats["unparseable"] and not args.json:
        print(f"{len(stats['unparseable'])} notes with unparseable frontmatter (run vault_yaml_repair.py):")
        for rel in stats["unparseable"]:
            print(f"  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
