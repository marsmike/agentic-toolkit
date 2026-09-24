#!/usr/bin/env python3
"""Capture the README newcomer commands, verbatim, in a clean empty HOME.

Usage: capture.py [--new-revision] PATH...   (no PATH: list the paths)

Exit status: the number of commands whose exit code differs from what
RECORDED expects (from-source's `add .` is expected to fail), or 2 when it
refuses: an unknown path, a HOME it did not create, or main having moved
past the revision a folder records (--new-revision overrides that one).

For each path: delete and recreate the throwaway HOME, record the starting
state (OS, tool versions, empty `ls -A $HOME`) in <path>/env.txt, then run
each README command in `env -i` and record it with record.py into
<path>/NN-<name>.cast, plus its final screen as NN-<name>.txt. The commands are copied from README.md; if the README
changes, change them here and re-capture.

Only the `claude` binary is taken from this machine: PREREQ_BIN holds a
symlink to it and nothing else, so no installed toolkit leaks onto PATH.
"""
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

# Paths recorded as ONE continuous interactive shell session (`/bin/sh -i`,
# prompt "$ "): the commands are typed in order, so `cd` happens once and
# nothing resets between steps. The typed lines are saved as commands.txt.
SESSIONS = {
    # README "From source" journey on main 0dd21a7 (the README now includes
    # the engines step and `add ./`).
    "from-source-main-0dd21a7": [
        f"git clone {REPO}",
        "cd agentic-toolkit",
        "uv run toolkit engines install",
        "uv run toolkit demo",
        "claude plugin marketplace add ./",
    ],
}


# What each folder records: the main revision it was captured at, and the
# exit codes it is expected to have (step number -> code; default 0).
# `from-source` records the README's broken From-source line at 72bb351, so
# its `add .` step failing is the finding, not a capture error.
RECORDED = {
    "headline": {"rev": "72bb351503a1b0e30646c53016188b54180bdadf"},
    "from-source": {"rev": "72bb351503a1b0e30646c53016188b54180bdadf", "exits": {3: 1}},
    "from-source-fixed": {"rev": "72bb351503a1b0e30646c53016188b54180bdadf"},
    "from-source-main-0dd21a7": {"rev": "0dd21a7f29ce736b53b3f8dded14035491b4599d"},
}


def run(cmd: str) -> str:
    r = subprocess.run(cmd, shell=True, env=ENV, cwd=HOME, capture_output=True, text=True)
    return (r.stdout + r.stderr).strip()


OWNER_NOTE = "created by agentic-toolkit video/capture/capture.py; deleted and recreated on every capture"


class NotOurs(Exception):
    pass


def _identity(path: Path) -> str:
    st = path.lstat()
    return f"{st.st_dev}:{st.st_ino}"


def fresh_home(home: Path = HOME) -> None:
    """Delete and recreate the throwaway HOME, but only the one this script made.

    Ownership is a marker file beside the directory (HOME itself must start
    empty) holding the device and inode of the directory it created, so a
    directory removed and replaced by anyone else no longer matches. A path
    that exists without a matching marker, or is a symlink, is someone
    else's: refuse rather than delete it.
    """
    marker = home.with_name(home.name + ".capture-owned")
    if home.is_symlink() or marker.is_symlink():
        raise NotOurs(f"{home} (or its marker) is a symlink; refusing to touch it")
    if home.exists():
        owned = marker.is_file() and marker.read_text() == f"{OWNER_NOTE}\n{_identity(home)}\n"
        if not owned:
            raise NotOurs(
                f"{home} exists and is not the directory capture.py created (no matching {marker.name}); "
                "remove it yourself if it is disposable, then re-run"
            )
        shutil.rmtree(home)
    home.mkdir(parents=True)
    marker.write_text(f"{OWNER_NOTE}\n{_identity(home)}\n")


def record_session(out: Path, commands: list[str]) -> int:
    typed = out / "commands.txt"
    typed.write_text("\n".join(commands) + "\n")
    cast = out / "session.cast"
    code = subprocess.run(
        [sys.executable, str(HERE / "record.py"), str(cast), str(COLS), str(ROWS),
         "--session", str(typed), "--", "/bin/sh", "-i"],
        env={**ENV, "PS1": "$ "}, cwd=HOME,
    ).returncode
    convert(cast)
    print(f"[exit {code}]")
    return 0 if code == RECORDED.get(out.name, {}).get("exits", {}).get(1, 0) else 1


def capture(name: str) -> int:
    fresh_home()  # first: if HOME is not ours, stop before deleting anything
    out = HERE / name
    out.mkdir(exist_ok=True)
    for old in [*out.glob("*.cast"), *out.glob("*.txt")]:
        old.unlink()
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
    if name in SESSIONS:
        env_lines.append('session: one interactive /bin/sh -i, prompt "$ ", commands typed from commands.txt')
    (out / "env.txt").write_text("\n".join(env_lines) + "\n")
    print("\n".join(env_lines))

    failed = 0
    if name in SESSIONS:
        failed = record_session(out, SESSIONS[name])
    for i, (step, cmd) in enumerate(PATHS.get(name, []), 1):
        print(f"\n$ {cmd}", flush=True)
        cast = out / f"{i:02d}-{step}.cast"
        code = subprocess.run(
            [sys.executable, str(HERE / "record.py"), str(cast), str(COLS), str(ROWS),
             "--", "/bin/sh", "-c", cmd],
            env=ENV, cwd=HOME,
        ).returncode
        convert(cast)
        expected = RECORDED.get(name, {}).get("exits", {}).get(i, 0)
        print(f"[exit {code}{'' if code == expected else f', expected {expected}'}]")
        if code != expected:
            failed += 1
    clone = HOME / "agentic-toolkit"
    if clone.is_dir():
        rev = run("git -C agentic-toolkit rev-parse HEAD")
        with open(out / "env.txt", "a") as f:
            f.write(f"source revision: {rev}\n")
    return failed


def main() -> int:
    args = sys.argv[1:]
    new_revision = "--new-revision" in args
    names = [a for a in args if a != "--new-revision"]
    if not names:
        print(__doc__, file=sys.stderr)
        for name in [*PATHS, *SESSIONS]:
            print(f"  {name:28} recorded at main {RECORDED[name]['rev'][:7]}", file=sys.stderr)
        return 2
    unknown = [n for n in names if n not in PATHS and n not in SESSIONS]
    if unknown:
        print(f"unknown path(s): {', '.join(unknown)}", file=sys.stderr)
        return 2
    if not (PREREQ_BIN / "claude").exists():
        print(f"missing {PREREQ_BIN}/claude: symlink the claude binary there first", file=sys.stderr)
        return 2
    # Every path installs or clones main as it is now. Re-capturing a folder
    # recorded at another revision would overwrite that evidence, so it needs
    # --new-revision (and then RECORDED and the folder name need updating).
    main_rev = subprocess.run(["git", "ls-remote", REPO, "refs/heads/main"],
                              capture_output=True, text=True, check=True).stdout.split()[0]
    stale = [n for n in names if RECORDED[n]["rev"] != main_rev]
    if stale and not new_revision:
        print(f"refusing: main is now {main_rev[:7]}, but {', '.join(stale)} recorded "
              f"{', '.join(sorted({RECORDED[n]['rev'][:7] for n in stale}))}; re-capturing would replace that "
              "evidence. Pass --new-revision to do it anyway.", file=sys.stderr)
        return 2
    try:
        return sum(capture(n) for n in names)
    except NotOurs as e:
        print(f"refusing: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
