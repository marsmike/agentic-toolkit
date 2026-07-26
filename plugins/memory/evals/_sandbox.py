"""Shared sandbox helper for evals that write to the vault.

Every eval in this plugin writes (a session record, a memory note), so every eval runs
against a throwaway copy of the resolved `./vault` rather than the real thing —
contract/PROFILE.md's "tests and evals never touch a user's real vault reached via
TOOLKIT_VAULT" rule, enforced structurally rather than by convention. Mirrors
plugins/obsidian/evals/_sandbox.py; duplicated rather than imported, since plugins
never import a sibling plugin (contract/KNOWLEDGE_API.md).
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path


def make_sandbox(vault: Path) -> Path:
    """Copy `vault` to a fresh temp directory and return the copy's path.

    Excludes .git, .obsidian, .smart-env, and any pre-existing search cache — none of
    which an eval needs and all of which can be large or machine-specific.
    """
    sandbox_root = Path(tempfile.mkdtemp(prefix="memory-plugin-eval-"))
    dest = sandbox_root / "vault"
    shutil.copytree(
        vault, dest,
        ignore=shutil.ignore_patterns(".git", ".obsidian", ".smart-env", ".search-cache", "__pycache__"),
    )
    return dest


def teardown_sandbox(sandbox_vault: Path) -> None:
    sys_tmp = Path(tempfile.gettempdir()).resolve()
    root = sandbox_vault.parent.resolve()
    if root.name.startswith("memory-plugin-eval-") or root.is_relative_to(sys_tmp):
        shutil.rmtree(root, ignore_errors=True)
