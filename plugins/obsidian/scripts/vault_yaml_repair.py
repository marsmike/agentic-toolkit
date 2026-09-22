#!/usr/bin/env python3
"""Make every note's YAML frontmatter parse, with the smallest edit that does it.

    uv run scripts/vault_yaml_repair.py              # report only
    uv run scripts/vault_yaml_repair.py --apply      # write the repairs
    uv run scripts/vault_yaml_repair.py --apply --include-archive

A note whose frontmatter does not parse is invisible to every other check (vault_normalize.py
refuses it and writes a DLQ entry, rightly: writing through a block it cannot read would
duplicate it). The causes on a real vault are few and mechanical, so this repairs them and
reports anything else untouched:

  1. an unquoted scalar containing `: `, ` #`, a Templater `{{…}}`, or starting with a reserved
     character (`@`, `&`, `*`, `!`, `%`, backtick)                     -> double-quote it
  2. a corrupted opening delimiter (junk around the first `---`)       -> restore `---`

Only lines inside the frontmatter change; a `"` inside a newly quoted value becomes `'`. The
archive is frozen by contract, so it is skipped unless asked for; quoting changes no content.
[earned: 2026-09-22 — 81 notes on a real vault, 25 active and 56 archived, all one of these two]
"""
from __future__ import annotations

import argparse
import json
import re
import sys

import yaml
from vault_utils import require_vault

# A value opening a real flow sequence/mapping or a block scalar is left alone; `{{` is a Templater
# placeholder, not a mapping, so it is quoted like any other scalar.
NEEDS_QUOTE = re.compile(r"^(?P<key>[A-Za-z_][\w-]*):\s+(?P<val>(?![\"'\[|>])(?!\{(?!\{))(?:[&*!%@`].*|.*(?:: |\s#|\{\{).*))$")
SKIP_PARTS = {".obsidian", ".trash", ".smart-env", ".git"}


def repair(text: str) -> tuple[str | None, str]:
    """(new text or None when nothing to do / not repairable, reason)."""
    lines = text.split("\n")
    if not lines:
        return None, ""
    first = lines[0].strip()
    cause = None
    if first != "---" and first.endswith("---") and len(first) <= 12:
        lines[0] = "---"
        cause = "delimiter"
    elif lines[0] != "---":
        return None, ""
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None, "no closing delimiter"
    try:
        yaml.safe_load("\n".join(lines[1:end]))
        if cause is None:
            return None, ""
    except yaml.YAMLError:
        pass
    quoted = []
    for i in range(1, end):
        m = NEEDS_QUOTE.match(lines[i])
        if m:
            lines[i] = f'{m.group("key")}: "{m.group("val").rstrip().replace(chr(34), chr(39))}"'
            quoted.append(m.group("key"))
    try:
        yaml.safe_load("\n".join(lines[1:end]))
    except yaml.YAMLError as e:
        return None, "unrepairable: " + str(e).splitlines()[0][:80]
    return "\n".join(lines), cause or "quoted " + ",".join(quoted)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Repair frontmatter YAML that does not parse")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--include-archive", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    vault = require_vault()
    skip = SKIP_PARTS | (set() if args.include_archive else {"05_Archive"})
    fixed, reported = [], []
    for path in sorted(vault.rglob("*.md")):
        if any(part in skip for part in path.relative_to(vault).parts):
            continue
        new, why = repair(path.read_text(encoding="utf-8", errors="replace"))
        rel = path.relative_to(vault).as_posix()
        if new is not None:
            fixed.append({"path": rel, "fix": why})
            if args.apply:
                path.write_text(new, encoding="utf-8")
        elif why:
            reported.append({"path": rel, "problem": why})

    if args.json:
        print(json.dumps({"applied": args.apply, "fixed": fixed, "unrepaired": reported}, indent=2))
    else:
        print(f"{'repaired' if args.apply else 'would repair'} {len(fixed)}; left for a human {len(reported)}")
        for f in fixed:
            print(f"  fix   {f['path']}  [{f['fix']}]")
        for r in reported:
            print(f"  SKIP  {r['path']}  [{r['problem']}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
