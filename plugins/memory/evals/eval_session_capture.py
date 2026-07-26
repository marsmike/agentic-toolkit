"""Eval: the SessionEnd hook's capture logic produces a schema-conformant session
record in 00_Memory/sessions/ given a fixture transcript.

Fixture-driven, no network, no real session data: a synthetic two-turn JSONL transcript
built inline below, matching Claude Code's transcript shape (type=user/assistant lines,
tool_use parts) closely enough to exercise the parser. Writes, so runs against a
sandbox copy of ./vault.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from _sandbox import make_sandbox, teardown_sandbox

REQUIRED_FIELDS = (
    "description", "kind", "status", "created", "source",
    "session_id", "project", "end_reason", "turns", "distilled", "tags",
)

FIXTURE_TRANSCRIPT = [
    {"type": "user", "message": {"content": "Can you check why the build is failing?"}},
    {
        "type": "assistant",
        "message": {
            "content": [
                {"type": "text", "text": "Sure, let me look."},
                {"type": "tool_use", "name": "Bash", "input": {"command": "make build"}},
            ]
        },
    },
    {"type": "user", "message": {"content": "Thanks, that fixed it."}},
    {
        "type": "assistant",
        "message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/repo/src/build.py"}}]},
    },
]


def run(vault: Path) -> dict:
    hooks_lib = Path(__file__).resolve().parent.parent / "hooks" / "lib"
    if str(hooks_lib) not in sys.path:
        sys.path.insert(0, str(hooks_lib))
    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    import memory_vault as mv
    import session_capture as sc

    sandbox_vault = make_sandbox(vault)
    transcript_file = tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    )
    try:
        for obj in FIXTURE_TRANSCRIPT:
            transcript_file.write(json.dumps(obj) + "\n")
        transcript_file.close()

        hook_input = {
            "session_id": "fixture-session-00010203",
            "transcript_path": transcript_file.name,
            "cwd": "/repo/home-lab-migration",
            "reason": "clear",
        }
        dest = sc.capture_session(hook_input, sandbox_vault)

        problems = []
        if dest is None:
            problems.append("capture_session returned None for a two-human-turn fixture")
            return {"eval": "session_capture", "pass": False, "detail": "; ".join(problems)}

        if dest.parent.name != "sessions" or dest.parent.parent.name != "00_Memory":
            problems.append(f"note written outside 00_Memory/sessions/: {dest}")

        fm, body = mv.read_note(dest)
        missing = [f for f in REQUIRED_FIELDS if f not in fm]
        if missing:
            problems.append(f"missing frontmatter fields: {missing}")
        if fm.get("kind") != "session":
            problems.append(f"expected kind=session, got {fm.get('kind')!r}")
        if fm.get("status") != "archived":
            problems.append(f"expected status=archived, got {fm.get('status')!r}")
        if fm.get("distilled") is not False:
            problems.append(f"expected distilled=false on a fresh capture, got {fm.get('distilled')!r}")
        if fm.get("turns") != 2:
            problems.append(f"expected turns=2, got {fm.get('turns')!r}")
        if fm.get("project") != "home-lab-migration":
            problems.append(f"expected project=home-lab-migration, got {fm.get('project')!r}")
        if not isinstance(fm.get("tags"), list) or "agent/session" not in fm["tags"]:
            problems.append(f"expected 'agent/session' in tags, got {fm.get('tags')!r}")
        if not body.strip():
            problems.append("empty body")
        if "Bash" not in body or "Edit" not in body:
            problems.append("tool-usage tally missing expected tool names in body")

        if problems:
            return {"eval": "session_capture", "pass": False, "detail": "; ".join(problems)}
        return {"eval": "session_capture", "pass": True, "detail": f"session note written: {dest.relative_to(sandbox_vault)}"}
    finally:
        teardown_sandbox(sandbox_vault)
        Path(transcript_file.name).unlink(missing_ok=True)
