#!/usr/bin/env python3
"""Digest today's new Readwise captures from `01_Capture/` (stdout only).

Python port of v1's `readwise-daily.sh`. Deliberately does not write to Log.md or any
other obsidian-plugin-owned file directly — that was a cross-plugin import in v1
(shelling out to `../obsidian/scripts/log_vault.py`), which contract/KNOWLEDGE_API.md's
"no cross-plugin imports" rule rules out here. Composition across plugins happens through
vault notes, not a direct call into another plugin's script; if a durable log entry is
wanted, the invoking skill/agent writes it itself. See README.md's dropped-components table.
"""
from __future__ import annotations

import argparse
import time
from collections import defaultdict
from pathlib import Path

from vault_utils import UnparseableFrontmatter, iter_captures, read_frontmatter


def build_digest(vault: Path, target_date: str) -> str:
    capture_dir = vault / "01_Capture"
    if not capture_dir.is_dir():
        return f"ERROR: capture directory not found: {capture_dir}"

    grouped: dict[str, list[str]] = defaultdict(list)
    count = 0
    for path in iter_captures(vault):
        try:
            fm, body = read_frontmatter(path)
        except UnparseableFrontmatter:
            continue
        created = str(fm.get("created") or fm.get("saved_at") or "")[:10]
        mtime_date = time.strftime("%Y-%m-%d", time.localtime(path.stat().st_mtime))
        if created != target_date and mtime_date != target_date:
            continue
        count += 1
        category = fm.get("category", "other")
        summary_line = _first_prose_line(body)
        entry = f"- [[{path.stem}]]"
        if summary_line:
            entry += f"\n  > {summary_line}"
        grouped[category].append(entry)

    if count == 0:
        return f"No new Readwise captures for {target_date} in {capture_dir}"

    lines = [f"## Readwise ({target_date})", "", f"{count} new capture(s) in 01_Capture/:"]
    for category, entries in sorted(grouped.items()):
        lines += ["", f"### {category.capitalize()}", *entries]
    return "\n".join(lines)


def _first_prose_line(body: str, max_len: int = 150) -> str:
    in_summary = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Readwise summary") or stripped.startswith("## Synthesis"):
            in_summary = True
            continue
        if stripped.startswith("## "):
            in_summary = False
            continue
        if in_summary and stripped and not stripped.startswith(("#", ">", "*", "-")):
            return stripped[:max_len - 3] + "..." if len(stripped) > max_len else stripped
    return ""


def _main() -> int:
    from vault_utils import require_vault

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--date", default=time.strftime("%Y-%m-%d"))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    vault = require_vault()
    print(build_digest(vault, args.date))
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(_main())
