"""`unisphere link`: put `unisphere`, the engines and Obsidian's CLI on PATH.

`unisphere` becomes a small shell shim that runs this checkout through `uv` (so a `git pull` is the
whole update), carrying a default TOOLKIT_VAULT that an exported one still overrides. The engines and Obsidian's bundled CLI become symlinks, so `unisphere engines update`
or an Obsidian update is picked up without linking again. Nothing is replaced that this command did
not write — our shim, or a symlink already pointing where we would point it — without `--force`.
[earned: 2026-09-28 — `gaiafield` and `toolkit` were "command not found" on the owner's Mac while
the plugins used them fine through the install directory]
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from toolkit_core import engines
from toolkit_core.status import OBSIDIAN_APP_CLI

SHIM_MARKER = "# Written by `unisphere link`"
LEGACY_SHIM_MARKER = "# Written by `toolkit link`"  # what shims from before the rename carry


def default_bin_dir() -> Path:
    return Path.home() / ".local" / "bin"


def shim_text(repo_root: Path, vault_path: Path | None) -> str:
    # Paths are shell-quoted: a vault path with $(…), quotes or backslashes must stay data.
    # [earned: PR #71 review]
    lines = [
        "#!/bin/sh",
        f"{SHIM_MARKER} — the agentic-toolkit CLI from {repo_root}. Run `unisphere link` again to change it.",
    ]
    if vault_path is not None:
        lines.append(f'if [ -z "${{TOOLKIT_VAULT:-}}" ]; then TOOLKIT_VAULT={shlex.quote(str(vault_path))}; export TOOLKIT_VAULT; fi')
    lines.append(f'exec uv run --quiet --locked --project {shlex.quote(str(repo_root))} unisphere "$@"')
    return "\n".join(lines) + "\n"


def _ours(path: Path, target: Path | None) -> bool:
    """Our shim, or a symlink that already points at `target`. A foreign symlink is not ours:
    replacing it would silently redirect someone else's command. [earned: PR #71 review]"""
    if path.is_symlink():
        return target is not None and Path(os.readlink(path)) == target
    try:
        head = path.read_text(encoding="utf-8", errors="replace")[:400]
    except OSError:
        return False
    return SHIM_MARKER in head or LEGACY_SHIM_MARKER in head


def _unchanged(dest: Path, target: Path | None, expected_text: str | None) -> bool:
    """Would `write` actually change `dest`? A symlink already pointing at `target` (checked by
    `_ours` before we ever get here) needs no re-link; a shim whose on-disk text already matches
    what we'd write needs no rewrite. [battle-test 2026-09-28: `unisphere link` run twice with
    nothing changed reported "updated" for every link, not "unchanged"]"""
    if target is not None:
        return dest.is_symlink() and Path(os.readlink(dest)) == target
    if expected_text is not None:
        try:
            return not dest.is_symlink() and dest.read_text(encoding="utf-8", errors="replace") == expected_text
        except OSError:
            return False
    return False


def _place(dest: Path, force: bool, write, target: Path | None = None, expected_text: str | None = None) -> dict:
    if dest.exists() or dest.is_symlink():
        if not force and not _ours(dest, target):
            return {"path": str(dest), "action": "skipped", "note": "exists and is not ours — rerun with --force to replace"}
        if _unchanged(dest, target, expected_text):
            return {"path": str(dest), "action": "unchanged"}
        dest.unlink()
        action = "updated"
    else:
        action = "created"
    write(dest)
    return {"path": str(dest), "action": action}


def link(repo_root: Path, bin_dir: Path, vault_path: Path | None, force: bool = False) -> dict:
    try:
        bin_dir.mkdir(parents=True, exist_ok=True)
    except (FileExistsError, NotADirectoryError):
        # A parent OSError subclass, so cli.py's generic `except OSError: str(exc)` still catches
        # this — but str() on a plain message (vs. one built from an errno) never shows
        # "[Errno 17] File exists: '…'". [battle-test 2026-09-28: `--bin-dir` naming a file gave
        # the raw Python errno text instead of a plain sentence]
        raise OSError(f"{bin_dir} exists and is not a directory — pass a different --bin-dir")
    except PermissionError:
        raise OSError(f"{bin_dir} is not writable — check its permissions or pass a different --bin-dir")
    results = []

    shim_content = shim_text(repo_root, vault_path)

    def write_shim(dest: Path) -> None:
        dest.write_text(shim_content, encoding="utf-8")
        dest.chmod(0o755)

    shim = bin_dir / "unisphere"
    results.append({"name": "unisphere", **_place(shim, force, write_shim, expected_text=shim_content)})

    targets = {name: engines.binary_path(name) for name in engines.ENGINES}
    if OBSIDIAN_APP_CLI.is_file():
        targets["obsidian"] = OBSIDIAN_APP_CLI
    for name, target in targets.items():
        if not target.is_file():
            results.append({"name": name, "path": str(bin_dir / name), "action": "skipped",
                            "note": f"{target} not found" + (" — unisphere engines install" if name in engines.ENGINES else "")})
            continue
        results.append({"name": name, "target": str(target),
                        **_place(bin_dir / name, force, lambda dest, t=target: dest.symlink_to(t), target)})

    # The CLI was `toolkit` until 2026-09-28: remove the shim or alias an earlier link wrote there,
    # never a `toolkit` someone else put on PATH.
    old = bin_dir / "toolkit"
    if (old.exists() or old.is_symlink()) and _ours(old, shim):
        old.unlink()
        results.append({"name": "toolkit", "path": str(old), "action": "removed", "note": "renamed to unisphere"})

    on_path = str(bin_dir) in os.environ.get("PATH", "").split(os.pathsep)
    return {
        # Obsidian's CLI is optional: without it everything the toolkit owns is still linked.
        "ok": not any(r["action"] == "skipped" and r["name"] != "obsidian" for r in results),
        "bin_dir": str(bin_dir),
        "on_path": on_path,
        "vault": str(vault_path) if vault_path else None,
        "links": results,
    }
