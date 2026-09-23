"""Throwaway copies of ./vault for evals that write (same rule as plugins/obsidian/evals/_sandbox.py:
evals never touch a vault reached via TOOLKIT_VAULT)."""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

PREFIX = "radar-plugin-eval-"


def make_sandbox(vault: Path) -> Path:
    dest = Path(tempfile.mkdtemp(prefix=PREFIX)) / "vault"
    shutil.copytree(vault, dest, ignore=shutil.ignore_patterns(".git", ".obsidian", ".smart-env", "__pycache__"))
    return dest


def teardown_sandbox(sandbox_vault: Path) -> None:
    root = sandbox_vault.parent.resolve()
    if root.name.startswith(PREFIX):
        shutil.rmtree(root, ignore_errors=True)


def snapshot(vault: Path) -> dict[str, tuple[int, int]]:
    return {p.relative_to(vault).as_posix(): (p.stat().st_size, p.stat().st_mtime_ns)
            for p in vault.rglob("*") if p.is_file()}
