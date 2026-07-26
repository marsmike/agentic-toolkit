"""Eval: save -> resume round-trip preserves the narrative and reports the correct
latest pointer.

Also checks read-compatibility against a real handoff file written minutes before this
port started (this repo's own `_handoff/HANDOFF-toolkit-rebuild-01.md`, via the legacy
v1 script) — copied read-only into a throwaway sandbox repo, never the original. The
new script must never break resume on a handoff file that predates it.
"""
from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from argparse import Namespace
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _sandbox  # noqa: E402

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"


def _load_handoff_module(name: str):
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / "handoff.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _check_profile_phase(vault: Path, hf) -> tuple[bool, str]:
    """Profile-scan coverage (zero eval coverage previously): `autosnapshot: no` must
    actually disable the PreCompact snapshot write (not just resolve falsy in
    isolation), a quoted `index_path` with a trailing inline `# comment` must resolve to
    the clean path rather than a literal string carrying the quotes/comment, and an env
    override must beat the profile note. Runs against its own throwaway repo + vault
    copy (never `./vault`, never this repo's own `_handoff/`) — see `evals/_sandbox.py`.
    """
    profile_repo = None
    profile_vault = None
    try:
        profile_repo = _sandbox.make_repo_sandbox()
        profile_vault = _sandbox.make_vault_sandbox(vault)
        note_dir = profile_vault / "Config" / "toolkit"
        note_dir.mkdir(parents=True, exist_ok=True)
        (note_dir / "handoff.md").write_text(
            "---\n"
            "autosnapshot: no\n"
            'index_path: "00_Memory/handoffs/index.md" # trailing comment must not leak in\n'
            "default_visibility: commit\n"
            "---\n",
            encoding="utf-8",
        )

        old_toolkit_vault = os.environ.get("TOOLKIT_VAULT")
        old_project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
        old_env_override = os.environ.get("TOOLKIT_HANDOFF_INDEX_PATH")
        os.environ["TOOLKIT_VAULT"] = str(profile_vault)
        os.environ["CLAUDE_PROJECT_DIR"] = str(profile_repo)
        os.environ.pop("TOOLKIT_HANDOFF_INDEX_PATH", None)
        try:
            resolved_index = hf.profile_value(profile_vault, "index_path", hf.DEFAULT_INDEX_PATH)
            if resolved_index != "00_Memory/handoffs/index.md":
                return False, f"index_path with inline comment resolved to {resolved_index!r}, expected the clean path"

            snap_path = profile_repo / "_handoff" / ".autosnapshot.md"
            hf.cmd_snapshot(Namespace())
            if snap_path.exists():
                return False, "autosnapshot: no did not disable the PreCompact snapshot write"

            os.environ["TOOLKIT_HANDOFF_INDEX_PATH"] = "env/overridden/index.md"
            resolved_env = hf.profile_value(profile_vault, "index_path", hf.DEFAULT_INDEX_PATH)
            if resolved_env != "env/overridden/index.md":
                return False, f"env override did not win over profile note: got {resolved_env!r}"

            return True, (
                "autosnapshot: no disabled the PreCompact hook, a quoted index_path with a "
                "trailing comment resolved to the clean path, and an env override beat the note"
            )
        finally:
            os.environ.pop("TOOLKIT_HANDOFF_INDEX_PATH", None)
            if old_env_override is not None:
                os.environ["TOOLKIT_HANDOFF_INDEX_PATH"] = old_env_override
            if old_toolkit_vault is None:
                os.environ.pop("TOOLKIT_VAULT", None)
            else:
                os.environ["TOOLKIT_VAULT"] = old_toolkit_vault
            if old_project_dir is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_project_dir
    finally:
        if profile_repo is not None:
            _sandbox.teardown_sandbox(profile_repo)
        if profile_vault is not None:
            _sandbox.teardown_sandbox(profile_vault)


def run(vault: Path) -> dict:
    name = "save_resume_roundtrip"
    repo = None
    vault_sandbox = None
    legacy_repo = None
    try:
        repo = _sandbox.make_repo_sandbox()
        vault_sandbox = _sandbox.make_vault_sandbox(vault)
        hf = _load_handoff_module("handoff_under_test_roundtrip")

        old_toolkit_vault = os.environ.get("TOOLKIT_VAULT")
        old_project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
        os.environ["TOOLKIT_VAULT"] = str(vault_sandbox)
        os.environ["CLAUDE_PROJECT_DIR"] = str(repo)
        try:
            narrative = "## Goal\n\nRoundtrip eval.\n\n## Next Step\n\nCheck this survives resume.\n"
            draft = repo / "_handoff" / ".draft.md"
            draft.parent.mkdir(exist_ok=True)
            draft.write_text(narrative, encoding="utf-8")

            save_out = StringIO()
            with redirect_stdout(save_out):
                hf.cmd_save(Namespace(stream="rt-eval", title="Roundtrip eval", body_file=str(draft)))
            save_text = save_out.getvalue()

            latest_path = repo / "_handoff" / "HANDOFF.md"
            if "Latest pointer:" not in save_text or str(latest_path) not in save_text:
                return {"eval": name, "pass": False, "detail": f"save output missing correct latest pointer: {save_text!r}"}

            resume_out = StringIO()
            with redirect_stdout(resume_out):
                hf.cmd_resume(Namespace())
            resume_text = resume_out.getvalue()

            if "Roundtrip eval." not in resume_text or "Check this survives resume." not in resume_text:
                return {"eval": name, "pass": False, "detail": "resume output lost narrative content"}

            # Legacy read-compat: a real v1-format handoff, copied (never the original).
            legacy_src = Path(__file__).resolve().parents[3] / "_handoff" / "HANDOFF-toolkit-rebuild-01.md"
            if legacy_src.is_file():
                legacy_repo = _sandbox.make_repo_sandbox()
                (legacy_repo / "_handoff").mkdir(exist_ok=True)
                shutil.copy(legacy_src, legacy_repo / "_handoff" / legacy_src.name)
                os.environ["CLAUDE_PROJECT_DIR"] = str(legacy_repo)
                legacy_out = StringIO()
                with redirect_stdout(legacy_out):
                    hf.cmd_resume(Namespace())
                legacy_text = legacy_out.getvalue()
                if "RESUMING FROM" not in legacy_text or "toolkit-rebuild" not in legacy_text:
                    return {"eval": name, "pass": False, "detail": "legacy-format handoff file did not resume cleanly from a copy"}

            profile_ok, profile_detail = _check_profile_phase(vault, hf)
            if not profile_ok:
                return {"eval": name, "pass": False, "detail": f"profile phase: {profile_detail}"}

            return {
                "eval": name,
                "pass": True,
                "detail": "save->resume round-trip preserved the narrative and reported the correct "
                "latest pointer; a copy of the pre-existing legacy-format handoff file resumed cleanly too; "
                f"profile phase: {profile_detail}",
            }
        finally:
            if old_toolkit_vault is None:
                os.environ.pop("TOOLKIT_VAULT", None)
            else:
                os.environ["TOOLKIT_VAULT"] = old_toolkit_vault
            if old_project_dir is None:
                os.environ.pop("CLAUDE_PROJECT_DIR", None)
            else:
                os.environ["CLAUDE_PROJECT_DIR"] = old_project_dir
    except Exception as exc:
        return {"eval": name, "pass": False, "detail": f"eval raised {type(exc).__name__}: {exc}"}
    finally:
        if repo is not None:
            _sandbox.teardown_sandbox(repo)
        if vault_sandbox is not None:
            _sandbox.teardown_sandbox(vault_sandbox)
        if legacy_repo is not None:
            _sandbox.teardown_sandbox(legacy_repo)
