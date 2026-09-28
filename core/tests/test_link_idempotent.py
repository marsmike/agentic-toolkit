"""`unisphere link` battle-test fixes, kept in their own file (not test_cli_interface.py) so this
lands as an isolated change alongside another agent's concurrent work there. [earned: 2026-09-28]

Bug #4: an OSError from `bin_dir.mkdir()` used to reach the CLI's `except OSError: str(exc)`
handler verbatim, so a `--bin-dir` that collides with an existing file showed the raw Python
errno text ("[Errno 17] File exists: '/…'") instead of a plain sentence.

Bug #5: `unisphere link` run a second time with nothing to change reported every link as
"updated" — `_place` always unlinked-and-rewrote once something existed and was ours, with no
check for whether the write would actually change anything.
"""

from __future__ import annotations

import os

import pytest
from conftest import REPO_ROOT
from toolkit_core import link as linker

requires_non_root = pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="root bypasses permission bits, so nothing is unwritable"
)


def test_link_run_twice_with_nothing_changed_reports_unchanged(tmp_path, monkeypatch):
    monkeypatch.setattr(linker, "OBSIDIAN_APP_CLI", tmp_path / "no-obsidian")
    bin_dir = tmp_path / "bin"
    vault_path = tmp_path / "MyVault"

    first = linker.link(REPO_ROOT, bin_dir, vault_path)
    assert first["links"][0]["action"] == "created"

    again = linker.link(REPO_ROOT, bin_dir, vault_path)
    assert again["links"][0] == {"name": "unisphere", "path": str(bin_dir / "unisphere"), "action": "unchanged"}
    for row in again["links"][1:]:
        assert row["action"] in ("unchanged", "skipped")

    # A real change (a different vault path) is still picked up and reported as "updated".
    changed = linker.link(REPO_ROOT, bin_dir, tmp_path / "OtherVault")
    assert changed["links"][0]["action"] == "updated"


def test_link_bin_dir_is_a_file_gives_a_plain_error(tmp_path, monkeypatch):
    monkeypatch.setattr(linker, "OBSIDIAN_APP_CLI", tmp_path / "no-obsidian")
    not_a_dir = tmp_path / "not-a-dir"
    not_a_dir.write_text("", encoding="utf-8")

    with pytest.raises(OSError) as excinfo:
        linker.link(REPO_ROOT, not_a_dir, None)
    message = str(excinfo.value)
    assert "Errno" not in message
    assert str(not_a_dir) in message and "not a directory" in message


@requires_non_root
def test_link_unwritable_bin_dir_gives_a_plain_error(tmp_path, monkeypatch):
    monkeypatch.setattr(linker, "OBSIDIAN_APP_CLI", tmp_path / "no-obsidian")
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)  # read + execute, no write
    try:
        with pytest.raises(OSError) as excinfo:
            linker.link(REPO_ROOT, locked / "bin", None)
    finally:
        locked.chmod(0o700)
    message = str(excinfo.value)
    assert "Errno" not in message
    assert "not writable" in message
