#!/usr/bin/env python3
"""Vault normalization — audit and fix note inconsistencies.

    uv run scripts/vault_normalize.py --check tags --scope 04_Resources --fix --dry-run

Rule-based checks (links) need no LLM. Description/tag/source/summary generation calls
the LLM backend configured in the vault's profile (Config/toolkit/obsidian.md, see
profile.example.md) and skips cleanly — reporting why, not crashing — when no
inference_model is configured. Always run --fix --dry-run before --fix.
"""
from __future__ import annotations

import argparse
import importlib
import subprocess
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from checks import FixResult, Issue
from vault_utils import (
    CHECK_MARK,
    WARNING,
    UnparseableFrontmatter,
    discover_notes,
    read_frontmatter,
    require_vault,
    update_index_markers,
    write_dlq_note,
    write_frontmatter,
)

CHECK_NAMES = ("frontmatter", "tags", "source", "links", "summary")


def _load_check(name: str) -> Any:
    return importlib.import_module(f"checks.{name}")


def run_audit(
    vault: Path, checks: list[str] | None = None, scope: str | None = None,
    exclude: list[str] | None = None, since: str | None = None, distilled_only: bool = False,
) -> list[Issue]:
    """Run audit across vault notes, returning all issues found."""
    modules = [_load_check(name) for name in (checks or CHECK_NAMES)]
    notes = discover_notes(vault, scope=scope, exclude=exclude, since=since, distilled_only=distilled_only)
    issues: list[Issue] = []
    for idx, note in enumerate(notes, 1):
        if idx % 50 == 0 or idx == 1:
            print(f"  [{idx}/{len(notes)}] Auditing {note.name}...", file=sys.stderr)
        fm, body = read_frontmatter(note)
        for mod in modules:
            issues.extend(mod.audit(note, fm, body, vault))
    return issues


def run_fix(
    vault: Path, checks: list[str] | None = None, scope: str | None = None, dry_run: bool = False,
    exclude: list[str] | None = None, since: str | None = None, distilled_only: bool = False,
) -> list[FixResult]:
    """Run fixes across vault notes, returning all results."""
    modules = [_load_check(name) for name in (checks or CHECK_NAMES)]
    notes = discover_notes(vault, scope=scope, exclude=exclude, since=since, distilled_only=distilled_only)
    all_results: list[FixResult] = []
    marker_updates: dict[str, str] = {}

    for idx, note in enumerate(notes, 1):
        if idx % 50 == 0 or idx == 1:
            print(f"  [{idx}/{len(notes)}] Processing {note.name}...", file=sys.stderr)

        # Refuse to write to a note whose frontmatter exists but doesn't parse — lenient
        # parsing would return {}, every check would then report every field missing, and
        # write_frontmatter would emit a SECOND `---` block above the first (Obsidian
        # reads only the first, so the note silently loses its real metadata).
        try:
            fm, body = read_frontmatter(note, strict=True)
        except UnparseableFrontmatter as exc:
            all_results.append(FixResult(
                note=note, check="frontmatter", applied=False,
                description=f"SKIPPED — frontmatter present but invalid YAML; fix by hand then re-run. ({str(exc).split(':')[-1].strip()[:80]})",
            ))
            write_dlq_note(
                vault, slug=f"unparseable-frontmatter-{note.stem[:40]}",
                title=f"Unparseable frontmatter: {note.name}",
                what_happened=f"vault_normalize.py --fix skipped {note.relative_to(vault)} rather than risk duplicating its frontmatter block.",
                why_recorded="Writing through a lenient parse would silently drop the note's real metadata behind a second, shadowing frontmatter block — a corruption, not a skip, if left unrecorded.",
                resolution="Fix the YAML by hand (usually an unquoted value containing ': '), then re-run vault_normalize.py --fix.",
                confidence="high",
            )
            continue

        modified = False
        note_results: list[FixResult] = []
        for mod in modules:
            fm, body, results = mod.fix(note, fm, body, vault, None)
            note_results.extend(results)
            if any(r.applied for r in results):
                modified = True
        all_results.extend(note_results)

        if modified and not dry_run:
            write_frontmatter(note, fm, body)

        if not dry_run and modified:
            fm2, body2 = read_frontmatter(note)
            remaining = [i for mod in modules for i in mod.audit(note, fm2, body2, vault)]
            rel = note.relative_to(vault).with_suffix("").as_posix()
            marker_updates[rel] = CHECK_MARK if not remaining else WARNING

    if not dry_run and marker_updates:
        update_index_markers(vault / "Index.md", marker_updates)

    return all_results


def format_audit_report(issues: list[Issue], notes_scanned: int) -> str:
    lines = ["=== Vault Normalize Audit ===", ""]
    by_check: dict[str, list[Issue]] = {}
    for issue in issues:
        by_check.setdefault(issue.check, []).append(issue)
    for check_name, check_issues in sorted(by_check.items()):
        lines.append(f"{check_name} ({len(check_issues)} issues)")
        for issue in check_issues:
            lines.append(f"  {issue.severity.upper():7s}  {issue.note.name} — {issue.description}")
        lines.append("")
    total = len(issues)
    breakdown = ", ".join(f"{count} {check}" for check, count in sorted(Counter(i.check for i in issues).items()))
    summary = f"Summary: {notes_scanned} notes scanned, {total} issues found"
    if breakdown:
        summary += f" ({breakdown})"
    lines.append(summary)
    return "\n".join(lines)


def format_fix_report(results: list[FixResult]) -> str:
    lines = ["=== Vault Normalize Fix ===", ""]
    for r in results:
        lines.append(f"{'FIXED' if r.applied else 'SKIP '}  {r.note.name} — {r.description}")
    lines.append("")
    applied = sum(1 for r in results if r.applied)
    skipped = sum(1 for r in results if not r.applied)
    summary = f"Summary: {applied} fixes applied"
    if skipped:
        summary += f", {skipped} skipped (manual review needed)"
    lines.append(summary)
    return "\n".join(lines)


def _log_action(vault: Path, title: str) -> None:
    log_script = Path(__file__).resolve().parent / "log_vault.py"
    subprocess.run([sys.executable, str(log_script), "normalize", title], check=False)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vault normalization — audit and fix note inconsistencies")
    parser.add_argument("--check", action="append", dest="checks", choices=CHECK_NAMES, help="Run only specific check(s). Repeatable.")
    parser.add_argument("--scope", default=None, help="Limit to a single PARA folder (e.g. 04_Resources).")
    parser.add_argument("--exclude", action="append", dest="exclude", default=None, metavar="PREFIX", help="Vault-relative path prefix to skip (repeatable) — private content that must never reach an LLM.")
    parser.add_argument("--since", default=None, metavar="YYYY-MM-DD")
    parser.add_argument("--distilled-only", action="store_true")
    parser.add_argument("--fix", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--log", default=None, help="Write report to this path (default: vault/normalize-report-<mode>-<ts>.md).")
    args = parser.parse_args(argv)

    vault = require_vault()
    checks = args.checks or list(CHECK_NAMES)

    if args.fix:
        results = run_fix(vault, checks, args.scope, args.dry_run, exclude=args.exclude, since=args.since, distilled_only=args.distilled_only)
        report = format_fix_report(results)
        print(report)
        if not args.dry_run and any(r.applied for r in results):
            _log_action(vault, f"{sum(1 for r in results if r.applied)} fixes applied")
    else:
        notes = discover_notes(vault, scope=args.scope, exclude=args.exclude, since=args.since, distilled_only=args.distilled_only)
        issues = run_audit(vault, checks, args.scope, exclude=args.exclude, since=args.since, distilled_only=args.distilled_only)
        report = format_audit_report(issues, len(notes))
        print(report)

    log_path = Path(args.log) if args.log else vault / f"normalize-report-{'fix-dry-run' if (args.fix and args.dry_run) else 'fix' if args.fix else 'audit'}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.md"
    log_path.write_text(report + "\n", encoding="utf-8")
    print(f"\nReport saved to: {log_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
