"""Shared sandbox helper for evals that write to the vault.

Every eval that only reads (vault-lint's link check, distill's placement heuristic) runs
directly against the resolved vault. Every eval that writes (retrieval-verification's
report, the DLQ acceptance criterion) runs against a throwaway copy under the system
temp dir instead — contract/PROFILE.md's "tests and evals never touch a user's real
vault reached via TOOLKIT_VAULT" rule, enforced structurally rather than by convention.
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
    sandbox_root = Path(tempfile.mkdtemp(prefix="obsidian-plugin-eval-"))
    dest = sandbox_root / "vault"
    shutil.copytree(
        vault, dest,
        ignore=shutil.ignore_patterns(".git", ".obsidian", ".smart-env", ".search-cache", "__pycache__"),
    )
    return dest


def teardown_sandbox(sandbox_vault: Path) -> None:
    sys_tmp = Path(tempfile.gettempdir()).resolve()
    root = sandbox_vault.parent.resolve()
    if root.name.startswith("obsidian-plugin-eval-") or root.is_relative_to(sys_tmp):
        shutil.rmtree(root, ignore_errors=True)
