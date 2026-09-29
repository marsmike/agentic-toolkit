"""Every uv project in the repo resolves from a committed lock (review-01 SEC-3).

The scheduled pipeline, CI and `install.sh` otherwise resolve the newest versions the `>=`
floors allow at run time: a bad upstream release would run inside the pipeline, with the
owner's keys in its environment, without a commit in this repo.
"""

from __future__ import annotations

import json
import subprocess
import tomllib

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


def test_plugin_scripts_pyproject_version_matches_plugin_json():
    """A plugin's scripts/pyproject.toml stays in lock-step with plugin.json, the same rule
    CONTRIBUTING.md states for marketplace.json (repo audit C1 — obsidian/radar/readwise's
    scripts pyprojects were frozen at 2.x while plugin.json moved through 3.x with nothing to
    catch the drift)."""
    drifted = []
    for project in UV_PROJECTS:
        if not project:
            continue
        plugin = project.split("/")[1]  # plugins/<name>/scripts -> <name>
        plugin_version = json.loads(
            (REPO_ROOT / "plugins" / plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        )["version"]
        pyproject_version = tomllib.loads(
            (REPO_ROOT / project / "pyproject.toml").read_text(encoding="utf-8")
        )["project"]["version"]
        if pyproject_version != plugin_version:
            drifted.append(f"{plugin}: plugin.json={plugin_version} scripts/pyproject.toml={pyproject_version}")
    assert not drifted, f"scripts/pyproject.toml version(s) out of lock-step with plugin.json: {drifted}"
