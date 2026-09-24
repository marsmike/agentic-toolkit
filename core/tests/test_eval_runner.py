"""plugins/obsidian/evals/run.py keeps stdout for its results alone, so `run.py --json` parses
[earned: 2026-09-24 review GLM-9 — in-process builders printed ahead of the JSON array]."""

from __future__ import annotations

import subprocess
import sys

from conftest import REPO_ROOT

PROBE = """
import subprocess, sys
sys.path.insert(0, {evals!r})
import run
with run._stdout_to_stderr():
    print("from python")
    subprocess.run([sys.executable, "-c", "print('from a subprocess')"], check=True)
print("results")
"""


def test_eval_progress_goes_to_stderr():
    evals = str(REPO_ROOT / "plugins" / "obsidian" / "evals")
    proc = subprocess.run([sys.executable, "-c", PROBE.format(evals=evals)],
                          capture_output=True, text=True, check=True)
    assert proc.stdout == "results\n"
    assert "from python" in proc.stderr and "from a subprocess" in proc.stderr
