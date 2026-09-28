"""`toolkit link`: put `toolkit`, the engines and Obsidian's CLI on PATH.

`toolkit` becomes a small shell shim that runs this checkout through `uv` (so a `git pull` is the
whole update), carrying a default TOOLKIT_VAULT that an exported one still overrides. The engines
and Obsidian's bundled CLI become symlinks, so `toolkit engines update` or an Obsidian update is
picked up without linking again. A file that is neither our shim nor a symlink is never replaced
without `--force`. [earned: 2026-09-28 — `gaiafield` and `toolkit` were "command not found" on
the owner's Mac while the plugins used them fine through the install directory]
"""

from __future__ import annotations

import os
from pathlib import Path

from toolkit_core import engines
from toolkit_core.status import OBSIDIAN_APP_CLI

SHIM_MARKER = "# Written by `toolkit link`"


def default_bin_dir() -> Path:
    return Path.home() / ".local" / "bin"


def shim_text(repo_root: Path, vault_path: Path | None) -> str:
    lines = [
        "#!/bin/sh",
        f"{SHIM_MARKER} — the agentic-toolkit CLI from {repo_root}. Run `toolkit link` again to change it.",
    ]
    if vault_path is not None:
        lines.append(f'if [ -z "${{TOOLKIT_VAULT:-}}" ]; then TOOLKIT_VAULT="{vault_path}"; export TOOLKIT_VAULT; fi')
    lines.append(f'exec uv run --quiet --locked --project "{repo_root}" toolkit "$@"')
    return "\n".join(lines) + "\n"


def _ours(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return SHIM_MARKER in path.read_text(encoding="utf-8", errors="replace")[:400]
    except OSError:
        return False


def _place(dest: Path, force: bool, write) -> dict:
    if dest.exists() or dest.is_symlink():
        if not force and not _ours(dest):
            return {"path": str(dest), "action": "skipped", "note": "exists and is not ours — rerun with --force to replace"}
        dest.unlink()
        action = "updated"
    else:
        action = "created"
    write(dest)
    return {"path": str(dest), "action": action}


def link(repo_root: Path, bin_dir: Path, vault_path: Path | None, force: bool = False) -> dict:
    bin_dir.mkdir(parents=True, exist_ok=True)
    results = []

    def write_shim(dest: Path) -> None:
        dest.write_text(shim_text(repo_root, vault_path), encoding="utf-8")
        dest.chmod(0o755)

    results.append({"name": "toolkit", **_place(bin_dir / "toolkit", force, write_shim)})

    targets = {name: engines.binary_path(name) for name in engines.ENGINES}
    if OBSIDIAN_APP_CLI.is_file():
        targets["obsidian"] = OBSIDIAN_APP_CLI
    for name, target in targets.items():
        if not target.is_file():
            results.append({"name": name, "path": str(bin_dir / name), "action": "skipped",
                            "note": f"{target} not found" + (" — toolkit engines install" if name in engines.ENGINES else "")})
            continue
        results.append({"name": name, "target": str(target),
                        **_place(bin_dir / name, force, lambda dest, t=target: dest.symlink_to(t))})

    on_path = str(bin_dir) in os.environ.get("PATH", "").split(os.pathsep)
    return {
        # Obsidian's CLI is optional: without it everything the toolkit owns is still linked.
        "ok": not any(r["action"] == "skipped" and r["name"] != "obsidian" for r in results),
        "bin_dir": str(bin_dir),
        "on_path": on_path,
        "vault": str(vault_path) if vault_path else None,
        "links": results,
    }
