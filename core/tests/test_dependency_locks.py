"""Every uv project in the repo resolves from a committed lock (review-01 SEC-3).

The scheduled pipeline, CI and `install.sh` otherwise resolve the newest versions the `>=`
floors allow at run time: a bad upstream release would run inside the pipeline, with the
owner's keys in its environment, without a commit in this repo.
"""

from __future__ import annotations

import subprocess

from conftest import REPO_ROOT

UV_PROJECTS = ("", "plugins/obsidian/scripts", "plugins/radar/scripts", "plugins/readwise/scripts")


def test_every_uv_project_is_listed_here():
    found = {p.parent.relative_to(REPO_ROOT).as_posix() for p in REPO_ROOT.glob("**/pyproject.toml")
             if not {".venv", ".claude", "target"} & set(p.relative_to(REPO_ROOT).parts)}
    # core/ is a member of the root workspace and shares its lock.
    assert found - {"core"} == {p or "." for p in UV_PROJECTS}


def test_every_uv_project_has_a_lock_that_git_does_not_ignore():
    for project in UV_PROJECTS:
        lock = REPO_ROOT / project / "uv.lock"
        assert lock.is_file(), f"{lock.relative_to(REPO_ROOT)} is missing: run `uv lock --project {project or '.'}`"
        ignored = subprocess.run(["git", "check-ignore", "-q", str(lock)], cwd=REPO_ROOT, check=False)
        assert ignored.returncode == 1, f"{lock.relative_to(REPO_ROOT)} is git-ignored"
