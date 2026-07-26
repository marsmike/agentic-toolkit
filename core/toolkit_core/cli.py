"""The `toolkit` CLI: vault init, doctor, profile. JSON output on --json."""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from collections.abc import Callable
from pathlib import Path

from toolkit_core import profile, vault


def _json_default(obj):
    """Frontmatter can carry YAML-native date/datetime values; render them as ISO strings."""
    if isinstance(obj, (datetime.date, datetime.datetime)):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _dumps(result: dict) -> str:
    return json.dumps(result, indent=2, default=_json_default)


def _emit(result: dict, as_json: bool, render_text: Callable[[dict], str]) -> None:
    if as_json:
        print(_dumps(result))
    else:
        print(render_text(result))


# --- vault init --------------------------------------------------------------------


def _vault_claude_template_path(repo_root: Path | None) -> Path | None:
    if repo_root is None:
        return None
    candidate = repo_root / "contract" / "templates" / "VAULT_CLAUDE.md"
    return candidate if candidate.is_file() else None


def cmd_vault_init(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    repo_root = vault.find_repo_root(Path.cwd()) or vault.find_repo_root(Path(__file__).resolve().parent)
    template_path = _vault_claude_template_path(repo_root)

    if template_path is None:
        result = {
            "ok": False,
            "error": "could not locate contract/templates/VAULT_CLAUDE.md (repo root not found)",
        }
        _emit(result, args.json, lambda r: f"error: {r['error']}")
        return 1

    try:
        vault.scaffold_vault(target, template_path, force=args.force)
    except vault.VaultInitError as exc:
        result = {"ok": False, "error": str(exc)}
        _emit(result, args.json, lambda r: f"error: {r['error']}")
        return 1

    result = {"ok": True, "path": str(target)}
    _emit(result, args.json, lambda r: f"initialized vault at {r['path']}")
    return 0


# --- doctor --------------------------------------------------------------------------


def _render_doctor_text(result: dict) -> str:
    lines = [f"vault: {result['vault_path']} (via {result['vault_source']})"]
    if not result["vault_exists"]:
        lines.append("  vault directory does not exist yet")
        return "\n".join(lines)

    lines.append("PARA folders:")
    for folder, present in result["para_folders"].items():
        mark = "ok" if present else "MISSING"
        count = result["note_counts"].get(folder, 0)
        lines.append(f"  {folder:<12} {mark:<8} {count} note(s)")

    errors = result["frontmatter_parse_errors"]
    lines.append(f"frontmatter parse errors: {len(errors)}")
    for err in errors:
        lines.append(f"  {err['path']}: {err['error']}")

    lines.append("profiles:")
    if result["profiles"]:
        for plugin_name, present in result["profiles"].items():
            lines.append(f"  {plugin_name:<12} {'present' if present else 'missing'}")
    else:
        lines.append("  (no known plugins)")

    dlq = result["dlq"]
    lines.append(f"DLQ: {dlq['note']}")
    return "\n".join(lines)


def cmd_doctor(args: argparse.Namespace) -> int:
    resolution = vault.resolve_vault()
    if resolution.path is None:
        result = {
            "ok": False,
            "error": "no vault found: set TOOLKIT_VAULT, or run from inside the agentic-toolkit repo",
        }
        _emit(result, args.json, lambda r: f"error: {r['error']}")
        return 1

    vault_path = resolution.path
    exists = vault_path.is_dir()

    para_status = vault.para_folder_status(vault_path) if exists else dict.fromkeys(vault.PARA_FOLDERS, False)
    counts = vault.note_counts(vault_path) if exists else dict.fromkeys(vault.PARA_FOLDERS, 0)
    parse_errors = vault.frontmatter_parse_errors(vault_path) if exists else []
    dlq = vault.dlq_status(vault_path) if exists else {"present": False, "count": 0, "note": "no DLQ entries"}

    repo_root = resolution.repo_root or vault.find_repo_root(Path(__file__).resolve().parent)
    plugin_names = profile.known_plugins(repo_root)
    profile_status = {name: profile.profile_note_path(vault_path, name).is_file() for name in plugin_names} if exists else {}

    result = {
        "ok": True,
        "vault_path": str(vault_path),
        "vault_source": resolution.source,
        "vault_exists": exists,
        "para_folders": para_status,
        "note_counts": counts,
        "frontmatter_parse_errors": parse_errors,
        "profiles": profile_status,
        "dlq": dlq,
    }
    _emit(result, args.json, _render_doctor_text)
    return 0


# --- profile ---------------------------------------------------------------------------


def cmd_profile(args: argparse.Namespace) -> int:
    resolution = vault.resolve_vault()
    if resolution.path is None:
        print(_dumps({"ok": False, "error": "no vault found"}))
        return 1

    merged = profile.resolve_profile(resolution.path, args.plugin)
    result = {"ok": True, "plugin": args.plugin, "vault_path": str(resolution.path), "profile": merged}
    # `toolkit profile` always prints JSON: it's a data command, not a status report.
    print(_dumps(result))
    return 0


# --- argument parsing ------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="emit JSON output")

    parser = argparse.ArgumentParser(prog="toolkit", parents=[common])
    subparsers = parser.add_subparsers(dest="command", required=True)

    vault_parser = subparsers.add_parser("vault", parents=[common])
    vault_subparsers = vault_parser.add_subparsers(dest="vault_command", required=True)
    init_parser = vault_subparsers.add_parser("init", parents=[common])
    init_parser.add_argument("path")
    init_parser.add_argument("--force", action="store_true", help="init into a non-empty directory")

    subparsers.add_parser("doctor", parents=[common])

    profile_parser = subparsers.add_parser("profile", parents=[common])
    profile_parser.add_argument("plugin")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "vault" and args.vault_command == "init":
        return cmd_vault_init(args)
    if args.command == "doctor":
        return cmd_doctor(args)
    if args.command == "profile":
        return cmd_profile(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
