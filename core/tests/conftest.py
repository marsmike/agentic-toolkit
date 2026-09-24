from __future__ import annotations

import os
from pathlib import Path

import pytest
from toolkit_core import vault

REPO_ROOT = vault.find_repo_root(Path(__file__).resolve().parent)
assert REPO_ROOT is not None, "tests must run from inside the agentic-toolkit repo"

EXAMPLE_VAULT = REPO_ROOT / "vault"
AGENTS_MD_TEMPLATE = REPO_ROOT / "contract" / "templates" / "VAULT_AGENTS.md"

# No test reads the developer's key file (vault_utils.secret falls back to ~/.env).
os.environ["TOOLKIT_KEYS_FILE"] = os.devnull


def example_vault_note_count() -> int:
    if not EXAMPLE_VAULT.is_dir():
        return 0
    return len(list(EXAMPLE_VAULT.rglob("*.md")))


def skip_if_example_vault_empty() -> None:
    if example_vault_note_count() == 0:
        pytest.skip(
            "./vault is empty — the example-vault agent hasn't populated it yet; "
            "integration will re-run this test once it has."
        )


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def agents_md_template() -> Path:
    return AGENTS_MD_TEMPLATE
