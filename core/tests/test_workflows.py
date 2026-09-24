"""Regression checks for workflow routing and release input boundaries."""

import fnmatch
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def workflow(name):
    return yaml.safe_load((ROOT / ".github/workflows" / name).read_text())


def test_ci_routes_lock_and_workflow_changes_to_required_checks():
    jobs = workflow("ci.yml")["jobs"]
    filter_step = next(step for step in jobs["changes"]["steps"] if step.get("id") == "filter")
    filters = yaml.safe_load(filter_step["with"]["filters"])

    def selected(path):
        return {name for name, patterns in filters.items() if any(fnmatch.fnmatchcase(path, p) for p in patterns)}

    assert selected("Cargo.lock") == {"rust"}
    assert "python" in selected("uv.lock")
    assert selected(".github/workflows/ci.yml") == set(filters)
    assert "python" in selected(".github/workflows/release-binaries.yml")


def test_ci_runs_every_plugin_eval_suite():
    steps = workflow("ci.yml")["jobs"]["evals"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    scheduled = set(re.findall(r"uv run python (plugins/[^ /]+/evals/run\.py)\b", commands))
    available = {str(path.relative_to(ROOT)) for path in ROOT.glob("plugins/*/evals/run.py")}
    assert scheduled == available


def test_ci_sync_rejects_stale_dependency_locks():
    jobs = workflow("ci.yml")["jobs"]
    for job_name in ("python", "contract-consistency", "evals"):
        commands = [step["run"] for step in jobs[job_name]["steps"] if "run" in step]
        sync = next(command for command in commands if command.startswith("uv sync "))
        assert "--locked" in sync.split()


def test_ci_routes_video_changes_and_checks_committed_sources():
    jobs = workflow("ci.yml")["jobs"]
    filter_step = next(step for step in jobs["changes"]["steps"] if step.get("id") == "filter")
    filters = yaml.safe_load(filter_step["with"]["filters"])

    assert "video" in filters
    assert "python" in filters
    assert any(fnmatch.fnmatchcase("video/capture/capture.py", p) for p in filters["python"])
    assert any(fnmatch.fnmatchcase("video/src/Explainer.tsx", p) for p in filters["video"])
    assert not any(fnmatch.fnmatchcase("README.md", p) for p in filters["video"])

    video = jobs["video"]
    assert video["needs"] == "changes"
    assert video["permissions"] == {"contents": "read"}
    assert video["defaults"]["run"]["working-directory"] == "video"
    assert [step["run"] for step in video["steps"] if "run" in step] == [
        "npm ci --ignore-scripts", "npm test", "npm run typecheck"
    ]
