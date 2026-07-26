"""Shared sandbox helper for evals that write to the vault.

Read-only evals would run directly against the resolved vault; every eval in this plugin
writes (capture creation), so all of them run against a throwaway copy instead —
contract/PROFILE.md's "tests and evals never touch a user's real vault reached via
TOOLKIT_VAULT" rule, enforced structurally rather than by convention. Mirrors
plugins/obsidian/evals/_sandbox.py; copied rather than imported (no cross-plugin imports).
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


def make_sandbox(vault: Path) -> Path:
    """Copy `vault` to a fresh temp directory and return the copy's path."""
    sandbox_root = Path(tempfile.mkdtemp(prefix="readwise-plugin-eval-"))
    dest = sandbox_root / "vault"
    shutil.copytree(
        vault, dest,
        ignore=shutil.ignore_patterns(".git", ".obsidian", ".smart-env", ".search-cache", "__pycache__"),
    )
    return dest


def teardown_sandbox(sandbox_vault: Path) -> None:
    sys_tmp = Path(tempfile.gettempdir()).resolve()
    root = sandbox_vault.parent.resolve()
    if root.name.startswith("readwise-plugin-eval-") or root.is_relative_to(sys_tmp):
        shutil.rmtree(root, ignore_errors=True)
