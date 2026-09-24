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
    assert selected(".github/workflows/ci.yml") == set(filters)


def test_ci_runs_every_plugin_eval_suite():
    steps = workflow("ci.yml")["jobs"]["evals"]["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)
    scheduled = set(re.findall(r"uv run python (plugins/[^ /]+/evals/run\.py)\b", commands))
    available = {str(path.relative_to(ROOT)) for path in ROOT.glob("plugins/*/evals/run.py")}
    assert scheduled == available
