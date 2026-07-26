"""Eval: the SessionStart hook degrades silently when READWISE_TOKEN is not set — zero
stdout, zero stderr, exit 0. This is the acceptance criterion the task brief called out
explicitly: v1's hook printed "READWISE: No READWISE_TOKEN in ~/.env — plugin disabled" on
every session for every user, including people who don't use Readwise at all. The rewrite
in hooks/session-start.sh must produce no output at all in that state.

Runs the real hook script as a subprocess with a scratch HOME (so a real ~/.env on the
machine running this eval can't leak READWISE_TOKEN in) and READWISE_TOKEN explicitly
absent from the environment. Doesn't touch the vault — included for interface parity with
the other evals in this suite (run.py calls every eval the same way).
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path


def run(vault: Path) -> dict:  # noqa: ARG001 - vault unused, kept for run.py's uniform interface
    hook_path = Path(__file__).resolve().parent.parent / "hooks" / "session-start.sh"
    if not hook_path.is_file():
        return {"eval": "hook_silent_noop", "pass": False, "detail": f"hook script not found: {hook_path}"}

    with tempfile.TemporaryDirectory(prefix="readwise-hook-eval-home-") as scratch_home:
        env = {k: v for k, v in os.environ.items() if k not in ("READWISE_TOKEN", "TOOLKIT_VAULT")}
        env["HOME"] = scratch_home
        result = subprocess.run(
            ["bash", str(hook_path)],
            capture_output=True, text=True, timeout=10, env=env,
        )

    problems = []
    if result.returncode != 0:
        problems.append(f"expected exit 0, got {result.returncode}")
    if result.stdout.strip():
        problems.append(f"expected empty stdout, got: {result.stdout.strip()!r}")
    if result.stderr.strip():
        problems.append(f"expected empty stderr, got: {result.stderr.strip()!r}")

    if problems:
        return {"eval": "hook_silent_noop", "pass": False, "detail": "; ".join(problems)}
    return {"eval": "hook_silent_noop", "pass": True, "detail": "hook produced no output and exited 0 with no READWISE_TOKEN set"}
