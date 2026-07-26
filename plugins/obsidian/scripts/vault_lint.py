#!/usr/bin/env python3
"""Vault health check — orphans, stale pages, missing concepts, Index.md drift.

Report-only, no LLM required, no embeddings store required. Run:

    uv run scripts/vault_lint.py [--stale-days 180] [--json]

Vault resolution: TOOLKIT_VAULT env var, else ./vault relative to the repo root
(contract/PROFILE.md). Scope: 02_Projects/03_Areas/04_Resources only — 00_Memory,
01_Capture, 05_Archive are never scanned or reported (contract/VAULT_SCHEMA.md).
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from vault_utils import ACTIVE_CONTENT_FOLDERS, EXCLUDE_DIRS, require_vault

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
INDEX_ENTRY_RE = re.compile(r"^\s*-\s*\[\[([^\]|]+)(?:\|[^\]]+)?\]\]\s*—\s*(.*?)\s*$")


def scan_vault(vault: Path) -> tuple[dict[str, Path], dict[str, set[str]], dict[str, set[str]]]:
    """Return (rel_path->path, rel_path->outbound target names, target name->inbound rel_paths).

    Keyed to match Obsidian's own wikilink resolution: by basename, not full path — a
    `[[Name]]` link resolves to any note named `Name` regardless of folder.
    """
    notes: dict[str, Path] = {}
    outbound: dict[str, set[str]] = defaultdict(set)
    inbound: dict[str, set[str]] = defaultdict(set)

    for folder in ACTIVE_CONTENT_FOLDERS:
        folder_path = vault / folder
        if not folder_path.exists():
            continue
        for md_file in folder_path.rglob("*.md"):
            if any(part in EXCLUDE_DIRS for part in md_file.relative_to(vault).parts[:-1]):
                continue
            rel_key = md_file.relative_to(vault).with_suffix("").as_posix()
            notes[rel_key] = md_file
            content = md_file.read_text(encoding="utf-8", errors="replace")
            for match in WIKILINK_RE.finditer(content):
                target_basename = match.group(1).strip().rsplit("/", 1)[-1]
                outbound[rel_key].add(target_basename)
                inbound[target_basename].add(rel_key)
    return notes, outbound, inbound


def find_orphans(notes: dict[str, Path], inbound: dict[str, set[str]]) -> list[dict]:
    orphans = []
    for rel_key, path in sorted(notes.items()):
        sources = inbound.get(path.stem, set()) - {rel_key}
        if not sources:
            created = datetime.fromtimestamp(path.stat().st_ctime).strftime("%Y-%m-%d")
            orphans.append({"name": path.stem, "path": str(path), "created": created})
    return orphans


def find_stale(notes: dict[str, Path], inbound: dict[str, set[str]], stale_days: int) -> list[dict]:
    cutoff = datetime.now() - timedelta(days=stale_days)
    stale = []
    for rel_key, path in sorted(notes.items()):
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--format=%aI", "--", str(path)],
                capture_output=True, text=True, cwd=path.parent, timeout=5, check=False,
            )
            if result.returncode == 0 and result.stdout.strip():
                modified = datetime.fromisoformat(result.stdout.strip()).replace(tzinfo=None)
            else:
                modified = datetime.fromtimestamp(path.stat().st_mtime)
        except (subprocess.TimeoutExpired, OSError, FileNotFoundError):
            modified = datetime.fromtimestamp(path.stat().st_mtime)

        if modified < cutoff:
            link_count = len(inbound.get(path.stem, set()) - {rel_key})
            stale.append({
                "name": path.stem, "path": str(path),
                "modified": modified.strftime("%Y-%m-%d"), "inbound_links": link_count,
            })
    stale.sort(key=lambda s: (s["inbound_links"], s["modified"]))
    return stale


def find_missing_concepts(notes: dict[str, Path], outbound: dict[str, set[str]]) -> list[dict]:
    note_names = {p.stem for p in notes.values()}
    ref_sources: dict[str, set[str]] = defaultdict(set)
    for source_rel, targets in outbound.items():
        for target in targets:
            if target not in note_names:
                ref_sources[target].add(source_rel)

    missing = []
    for term, source_rels in sorted(ref_sources.items()):
        if len(source_rels) >= 2:
            sources = sorted({rel.rsplit("/", 1)[-1] for rel in source_rels})
            missing.append({"term": term, "count": len(source_rels), "sources": sources[:5]})
    missing.sort(key=lambda m: m["count"], reverse=True)
    return missing


def find_index_drift(vault: Path, notes: dict[str, Path]) -> dict:
    index_path = vault / "Index.md"
    if not index_path.exists():
        return {"dangling": [], "missing": [], "bootstrap_count": 0, "index_exists": False}

    entries: dict[str, bool] = {}
    for line in index_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = INDEX_ENTRY_RE.match(line)
        if m:
            entries[m.group(1).strip()] = COG_MARK in m.group(2)

    active = {rel_key: p for rel_key, p in notes.items()}
    dangling = [
        {"name": rel.rsplit("/", 1)[-1], "path": rel, "reason": "file not found"}
        for rel in sorted(entries) if rel not in active
    ]
    missing = [
        {"name": rel.rsplit("/", 1)[-1], "path": str(active[rel])}
        for rel in sorted(active) if rel not in entries
    ]
    return {
        "dangling": dangling, "missing": missing,
        "bootstrap_count": sum(1 for v in entries.values() if v),
        "index_exists": True,
    }


COG_MARK = "⚙"


def format_text(orphans: list, stale: list, missing: list, drift: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"Vault Lint — {now}", ""]

    lines.append(f"Orphans ({len(orphans)}):")
    lines += [f"  - [[{o['name']}]] (created {o['created']})" for o in orphans] or ["  (none)"]
    lines.append("")

    lines.append(f"Stale ({len(stale)}):")
    lines += [f"  - [[{s['name']}]] (modified {s['modified']}, {s['inbound_links']} inbound links)" for s in stale] or ["  (none)"]
    lines.append("")

    lines.append(f"Missing Concepts ({len(missing)}):")
    lines += [
        f"  - \"{m['term']}\" — mentioned in {m['count']} notes ({', '.join(f'[[{s}]]' for s in m['sources'])})"
        for m in missing
    ] or ["  (none)"]
    lines.append("")

    drift_issues = 0
    if not drift["index_exists"]:
        lines.append("Index Drift: no Index.md found")
    else:
        drift_issues = len(drift["dangling"]) + len(drift["missing"])
        lines.append(f"Index Drift ({drift_issues} issues):")
        lines.append(f"  Dangling ({len(drift['dangling'])}):")
        lines += [f"    - {d['path']} — {d['reason']}" for d in drift["dangling"]] or ["    (none)"]
        lines.append(f"  Missing ({len(drift['missing'])}):")
        lines += [f"    - {m['path']} — no index entry" for m in drift["missing"]] or ["    (none)"]
        lines.append(f"  Bootstrap quality: {drift['bootstrap_count']} entries still marked {COG_MARK}")
    lines.append("")

    total = len(orphans) + len(stale) + len(missing) + drift_issues
    lines.append(f"Total: {total} items need attention")
    return "\n".join(lines)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            pass

    parser = argparse.ArgumentParser(description="Vault health check")
    parser.add_argument("--stale-days", type=int, default=180)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    vault = require_vault()
    notes, outbound, inbound = scan_vault(vault)
    orphans = find_orphans(notes, inbound)
    stale = find_stale(notes, inbound, args.stale_days)
    missing = find_missing_concepts(notes, outbound)
    drift = find_index_drift(vault, notes)

    if args.json:
        print(json.dumps({
            "orphans": orphans, "stale": stale, "missing_concepts": missing, "index_drift": drift,
        }, indent=2))
    else:
        print(format_text(orphans, stale, missing, drift))
    return 0


if __name__ == "__main__":
    sys.exit(main())
