"""Exercise curl-pipe installation with an isolated HOME and fake installers."""

import fcntl
import os
import pty
import select
import subprocess
import termios
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "install.sh"


@pytest.fixture
def installer_env(tmp_path):
    bindir = tmp_path / "bin"
    bindir.mkdir()
    home = tmp_path / "home"
    (home / ".local/bin").mkdir(parents=True)
    (bindir / "cat").symlink_to("/bin/cat")
    (bindir / "sh").symlink_to("/bin/sh")
    stubs = {
        "curl": """#!/bin/sh
printf '%s\\n' '/bin/cp "$STUB_UV" "$HOME/.local/bin/uv"'
""",
        "toolkit": '#!/bin/sh\nprintf "toolkit %s\\n" "$*" >> "$INSTALL_LOG"\n',
        "uv-stub": '#!/bin/sh\nprintf "uv %s\\n" "$*" >> "$INSTALL_LOG"\n',
    }
    for name, content in stubs.items():
        path = bindir / name
        path.write_text(content)
        path.chmod(0o755)
    return {
        "HOME": str(home),
        "PATH": str(bindir),
        "STUB_UV": str(bindir / "uv-stub"),
        "INSTALL_LOG": str(tmp_path / "calls"),
    }


@pytest.mark.parametrize("answer", ["yes", "no"])
def test_piped_installer_reads_answer_from_terminal(installer_env, answer):
    master, slave = pty.openpty()

    def attach_terminal():
        os.setsid()
        fcntl.ioctl(slave, termios.TIOCSCTTY, 0)

    proc = subprocess.Popen(
        ["/bin/bash"], stdin=subprocess.PIPE, stdout=slave, stderr=slave,
        env=installer_env, preexec_fn=attach_terminal,
    )
    os.close(slave)
    output = b""
    try:
        proc.stdin.write(SCRIPT.read_bytes())
        proc.stdin.close()
        deadline = time.monotonic() + 5
        while b"[y/N]" not in output and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    output += os.read(master, 8192)
                except OSError:
                    break
        assert b"[y/N]" in output, output.decode()
        os.write(master, (answer + "\n").encode())
        # Drain output while the child exits; macOS waits for PTY output to drain.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    chunk = os.read(master, 8192)
                except OSError:
                    break
                if not chunk:
                    break
                output += chunk
            elif proc.poll() is not None:
                break
        proc.wait(timeout=5)
        if answer == "yes":
            assert proc.returncode == 0, output.decode()
            calls = Path(installer_env["INSTALL_LOG"]).read_text()
            assert "uv tool install --force git+https://github.com/marsmike/agentic-toolkit#subdirectory=core" in calls
            assert "toolkit engines install" in calls
        else:
            assert proc.returncode == 1
            assert not Path(installer_env["INSTALL_LOG"]).exists()
    finally:
        os.close(master)
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)


def test_piped_installer_without_terminal_declines_cleanly(installer_env):
    result = subprocess.run(
        ["/bin/bash"], input=SCRIPT.read_text(), capture_output=True, text=True,
        env=installer_env, start_new_session=True, timeout=5,
    )
    assert result.returncode == 1
    assert "uv is required. Install it yourself" in result.stdout
    assert not Path(installer_env["INSTALL_LOG"]).exists()
