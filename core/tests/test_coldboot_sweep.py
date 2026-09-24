"""`scripts/coldboot.sh` removes work dirs a killed run left behind (review-01 SEC-7): stage 4
writes the Claude OAuth credential into its work dir, and a SIGKILL skips the EXIT trap."""

from __future__ import annotations

import os
import shutil
import subprocess
import time

import pytest
from conftest import REPO_ROOT

COLDBOOT = REPO_ROOT / "scripts" / "coldboot.sh"


@pytest.mark.skipif(shutil.which("bash") is None, reason="needs bash")
def test_sweep_removes_stale_coldboot_dirs_and_keeps_fresh_ones(tmp_path):
    stale = tmp_path / "toolkit-coldboot.stale123"
    (stale / "claude-config").mkdir(parents=True)
    (stale / "claude-config" / ".credentials.json").write_text("{}")
    three_hours_ago = time.time() - 3 * 3600
    os.utime(stale, (three_hours_ago, three_hours_ago))
    fresh = tmp_path / "toolkit-coldboot.fresh456"
    fresh.mkdir()
    unrelated = tmp_path / "something-else"
    unrelated.mkdir()
    os.utime(unrelated, (three_hours_ago, three_hours_ago))

    run = subprocess.run(["bash", str(COLDBOOT), "--sweep-only"], env={**os.environ, "TMPDIR": str(tmp_path)},
                         capture_output=True, text=True, timeout=30, check=False)

    assert run.returncode == 0, run.stderr
    assert not stale.exists(), "a stale work dir (with a credential file) survived the sweep"
    assert fresh.exists(), "the sweep removed a work dir a run in progress could own"
    assert unrelated.exists(), "the sweep removed a dir that is not a coldboot work dir"
