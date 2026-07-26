"""Shared sandbox helpers for handoff plugin evals.

Two independent sandboxes are needed here, unlike a single-vault-sandbox plugin: a
throwaway **project repo** (where `_handoff/` gets written — never this repo's own
`_handoff/`) and a throwaway **vault** copy (never `./vault` itself, and never a real
vault reached via `TOOLKIT_VAULT` — contract/PROFILE.md's rule, enforced structurally
rather than by convention). Mirrors plugins/readwise/evals/_sandbox.py and
plugins/memory/evals/_sandbox.py; copied rather than imported (no cross-plugin imports).
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path


def make_vault_sandbox(vault: Path) -> Path:
    """Copy `vault` to a fresh temp directory and return the copy's path."""
    sandbox_root = Path(tempfile.mkdtemp(prefix="handoff-plugin-eval-vault-"))
    dest = sandbox_root / "vault"
    shutil.copytree(
        vault, dest,
        ignore=shutil.ignore_patterns(".git", ".obsidian", ".smart-env", ".search-cache", "__pycache__"),
    )
    return dest


def make_repo_sandbox() -> Path:
    """A fresh, throwaway git repo in a temp directory — never this repo's own working
    tree, so `_handoff/` writes here can never touch the real `_handoff/` at the
    toolkit repo's root."""
    root = Path(tempfile.mkdtemp(prefix="handoff-plugin-eval-repo-"))
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "eval@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "handoff eval"], cwd=root, check=True)
    (root / "README.md").write_text("# sandbox repo\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    return root


def teardown_sandbox(path: Path) -> None:
    """Removes a sandbox produced by either helper above. A vault sandbox's returned
    path is the `vault/` subdir, so its temp root is one level up; a repo sandbox's
    returned path IS the temp root."""
    sys_tmp = Path(tempfile.gettempdir()).resolve()
    root = path.parent.resolve() if path.name == "vault" else path.resolve()
    if root.name.startswith("handoff-plugin-eval-") or root.is_relative_to(sys_tmp):
        shutil.rmtree(root, ignore_errors=True)
