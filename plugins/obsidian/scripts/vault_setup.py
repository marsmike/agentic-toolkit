#!/usr/bin/env python3
"""Install the toolkit's static Obsidian files into a vault — files only, no settings touched.

    uv run scripts/vault_setup.py [--dry-run] [--json]

Copies `plugins/obsidian/obsidian/` into the vault: `Vault.base` (the live views Now.md embeds),
`.obsidian/snippets/toolkit.css` (the dashboard and map styles) and `Templates/toolkit/` (the
Templater capture templates). A file already identical is left alone; a changed one is replaced,
because these files belong to the toolkit, not to the vault. Obsidian's own settings stay
untouched, so the script ends by printing the clicks only Mike can make.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from vault_utils import require_vault

SOURCE = Path(__file__).resolve().parent.parent / "obsidian"
CLICKS = (
    "Settings → Appearance → CSS snippets: turn on 'toolkit'.",
    "Settings → Homepage: open 'Now' on startup, in reading view.",
    "Settings → Templater: template folder 'Templates' (the toolkit's are in Templates/toolkit/).",
    "Settings → Obsidian Git: auto-commit off, pull on startup on, push manual (the pipeline commits and pushes).",
)


def plan(vault: Path) -> list[tuple[Path, Path, str]]:
    """(source, destination, action) for every shipped file; action is new, update or same."""
    out = []
    for src in sorted(p for p in SOURCE.rglob("*") if p.is_file()):
        rel = src.relative_to(SOURCE)
        dest = vault / (Path(".obsidian") / rel if rel.parts[0] == "snippets" else rel)
        action = "new" if not dest.exists() else "same" if dest.read_bytes() == src.read_bytes() else "update"
        out.append((src, dest, action))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Install the toolkit's static Obsidian files")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    vault = require_vault()
    steps = plan(vault)
    if not args.dry_run:
        for src, dest, action in steps:
            if action != "same":
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(src, dest)
    result = {"files": [{"path": d.relative_to(vault).as_posix(), "action": a} for _, d, a in steps],
              "dry_run": args.dry_run, "clicks": list(CLICKS)}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for f in result["files"]:
            print(f"{'would ' if args.dry_run and f['action'] != 'same' else ''}{f['action']:>6}  {f['path']}")
        print("\nIn Obsidian, once:")
        print("\n".join(f"  - {c}" for c in CLICKS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
