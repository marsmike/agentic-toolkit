#!/usr/bin/env python3
"""Capture the README newcomer commands, verbatim, in a clean empty HOME.

Usage: capture.py [headline|from-source|from-source-fixed ...]   (default: all)

For each path: delete and recreate the throwaway HOME, record the starting
state (OS, tool versions, empty `ls -A $HOME`) in <path>/env.txt, then run
each README command in `env -i` and record it with record.py into
<path>/NN-<name>.cast, plus its final screen as NN-<name>.txt. The commands are copied from README.md; if the README
changes, change them here and re-capture.

Only the `claude` binary is taken from this machine: PREREQ_BIN holds a
symlink to it and nothing else, so no installed toolkit leaks onto PATH.
"""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from cast_text import convert

HOME = Path("/private/tmp/newcomer")
PREREQ_BIN = Path("/private/tmp/prereq-bin")
HERE = Path(__file__).resolve().parent
COLS, ROWS = 120, 32

# $HOME/.local/bin is where `uv tool install` puts `toolkit` (what
# `uv tool update-shell` adds for a newcomer).
PATH = f"{HOME}/.local/bin:{PREREQ_BIN}:/usr/bin:/bin:/opt/homebrew/bin"
ENV = {"HOME": str(HOME), "PATH": PATH, "TERM": "xterm-256color", "LANG": "en_US.UTF-8"}

REPO = "https://github.com/marsmike/agentic-toolkit"
PATHS = {
    # README "New here" block.
    "headline": [
        ("install", f"uv tool install git+{REPO}#subdirectory=core"),
        ("engines", "toolkit engines install"),
        ("plugins", "claude plugin marketplace add marsmike/agentic-toolkit"),
        ("demo", "toolkit demo"),
    ],
    # README "From source" line.
    "from-source": [
        ("clone", f"git clone {REPO}"),
        ("demo", "cd agentic-toolkit && uv run toolkit demo"),
        ("plugins", "cd agentic-toolkit && claude plugin marketplace add ."),
    ],
    # NOT in the README: From source plus the two fixes the verbatim run
    # needed (demo stops at step 1 without engines; `add .` is rejected,
    # `add ./` is the accepted local form). Evidence for decision D6.
    "from-source-fixed": [
        ("clone", f"git clone {REPO}"),
        ("engines", "cd agentic-toolkit && uv run toolkit engines install"),
        ("demo", "cd agentic-toolkit && uv run toolkit demo"),
        ("plugins", "cd agentic-toolkit && claude plugin marketplace add ./"),
    ],
}


def run(cmd: str) -> str:
    r = subprocess.run(cmd, shell=True, env=ENV, cwd=HOME, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


def fresh_home() -> None:
    if HOME.exists():
        shutil.rmtree(HOME)
    HOME.mkdir(parents=True)


def capture(name: str) -> int:
    out = HERE / name
    out.mkdir(exist_ok=True)
    for old in [*out.glob("*.cast"), *out.glob("*.txt")]:
        old.unlink()
    fresh_home()
    env_lines = [
        f"path: {name}",
        f"os: macOS {platform.mac_ver()[0]} {platform.machine()}",
        f"uv: {run('uv --version')}",
        f"claude: {run('claude --version')}",
        f"git: {run('git --version')}",
        f"HOME: {HOME}",
        f"PATH: {PATH}",
        f"ls -A $HOME: [{run('ls -A')}]",
    ]
    (out / "env.txt").write_text("\n".join(env_lines) + "\n")
    print("\n".join(env_lines))

    failed = 0
    for i, (step, cmd) in enumerate(PATHS[name], 1):
        print(f"\n$ {cmd}", flush=True)
        cast = out / f"{i:02d}-{step}.cast"
        code = subprocess.run(
            [sys.executable, str(HERE / "record.py"), str(cast), str(COLS), str(ROWS),
             "--", "/bin/sh", "-c", cmd],
            env=ENV, cwd=HOME,
        ).returncode
        convert(cast)
        print(f"[exit {code}]")
        if code:
            failed += 1
    clone = HOME / "agentic-toolkit"
    if clone.is_dir():
        rev = run("git -C agentic-toolkit rev-parse HEAD")
        with open(out / "env.txt", "a") as f:
            f.write(f"source revision: {rev}\n")
    return failed


def main() -> int:
    names = sys.argv[1:] or list(PATHS)
    if not (PREREQ_BIN / "claude").exists():
        print(f"missing {PREREQ_BIN}/claude: symlink the claude binary there first", file=sys.stderr)
        return 2
    return sum(capture(n) for n in names)


if __name__ == "__main__":
    sys.exit(main())
