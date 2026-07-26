#!/usr/bin/env python3
"""SessionEnd hook worker — archives a lightweight, deterministic session record into
`$VAULT/00_Memory/sessions/`.

Deliberately mechanical, not an LLM summary: project name, human-turn count, a short
first-message snippet, a tool-usage tally, and files touched, all extracted by parsing
the transcript JSONL directly. v1's memory plugin did this via a `claude -p` subprocess
call on every session end — an automatic, silent LLM spend on a hook path is a surprise
this port deliberately removes (see plugins/memory/README.md). The archive is the
"zero-cost" (no API spend) half of the mechanism; turning archived sessions into
judgment-based durable notes is the on-demand `distill-memory` skill's job.

Contract:
- No vault resolvable (contract/PROFILE.md: TOOLKIT_VAULT env var, else ./vault) ->
  silent no-op. A hook must never nudge or error for a user without a vault.
- Any other failure -> a DLQ note under 00_Memory/dlq/ instead of raising. This
  process must always exit 0; it must never break the session it's attached to.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import memory_vault as mv  # noqa: E402

DEFAULT_MAX_TRANSCRIPT_BYTES = 2_000_000
DEFAULT_MIN_HUMAN_TURNS_TO_ARCHIVE = 1


def iter_transcript(path: Path, max_bytes: int):
    """Yield parsed JSON objects from a JSONL transcript, reading at most `max_bytes`
    characters so a pathologically large transcript can't blow the hook's timeout."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            data = f.read(max_bytes)
    except OSError:
        return
    lines = data.split("\n")
    if lines and not data.endswith("\n"):
        lines = lines[:-1]  # drop a possibly-truncated final line
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except json.JSONDecodeError:
            continue


def summarize_transcript(path: Path, max_bytes: int) -> dict:
    human_turns = 0
    tools_used: dict[str, int] = {}
    files_touched: set[str] = set()
    first_user_snippet: str | None = None

    for obj in iter_transcript(path, max_bytes):
        typ = obj.get("type")
        if typ == "user":
            content = obj.get("message", {}).get("content")
            if isinstance(content, str):
                human_turns += 1
                if first_user_snippet is None:
                    snippet = content.strip()
                    first_user_snippet = snippet[:300] + ("…" if len(snippet) > 300 else "")
        elif typ == "assistant":
            content = obj.get("message", {}).get("content", [])
            if not isinstance(content, list):
                continue
            for part in content:
                if not isinstance(part, dict) or part.get("type") != "tool_use":
                    continue
                name = part.get("name") or "tool"
                tools_used[name] = tools_used.get(name, 0) + 1
                fp = (part.get("input") or {}).get("file_path")
                if isinstance(fp, str):
                    files_touched.add(Path(fp).name)

    return {
        "human_turns": human_turns,
        "tools_used": tools_used,
        "files_touched": sorted(files_touched),
        "first_user_snippet": first_user_snippet or "",
    }


def capture_session(hook_input: dict, vault: Path) -> Path | None:
    """Write one session record. Returns the note's path, or None if the session had
    too few human turns to be worth archiving (per the `min_human_turns_to_archive`
    profile tunable)."""
    session_id = str(hook_input.get("session_id") or "unknown-session")
    transcript_path = hook_input.get("transcript_path")
    cwd = hook_input.get("cwd") or ""
    reason = hook_input.get("reason") or "unknown"

    max_bytes = mv.profile_value(vault, "max_transcript_bytes", DEFAULT_MAX_TRANSCRIPT_BYTES)
    min_turns = mv.profile_value(vault, "min_human_turns_to_archive", DEFAULT_MIN_HUMAN_TURNS_TO_ARCHIVE)

    stats = {"human_turns": 0, "tools_used": {}, "files_touched": [], "first_user_snippet": ""}
    if transcript_path and Path(transcript_path).is_file():
        stats = summarize_transcript(Path(transcript_path), max_bytes)

    if stats["human_turns"] < min_turns:
        return None

    today = time.strftime("%Y-%m-%d")
    now = time.strftime("%H:%M")
    project = mv.project_name(cwd)
    slug = mv.slugify(f"{project}-{session_id[:8]}")
    sessions_dir = Path(vault) / "00_Memory" / "sessions"
    dest = mv.unique_path(sessions_dir, f"{today}-{slug}")

    turn_word = "turn" if stats["human_turns"] == 1 else "turns"
    frontmatter = {
        "description": f"Session archive: {project} — {stats['human_turns']} {turn_word}",
        "kind": "session",
        "status": "archived",
        "created": today,
        "source": transcript_path or "",
        "session_id": session_id,
        "project": project,
        "end_reason": reason,
        "turns": stats["human_turns"],
        "distilled": False,
        "tags": ["agent/session", "domain/toolkit-meta"],
    }

    tool_lines = "\n".join(f"- {name} × {count}" for name, count in sorted(stats["tools_used"].items(), key=lambda x: -x[1]))
    file_lines = "\n".join(f"- {name}" for name in stats["files_touched"])
    body = (
        f"# Session — {project} — {today} {now}\n\n"
        f"**First message:** {stats['first_user_snippet'] or '(none captured)'}\n\n"
        "## Tool usage\n"
        f"{tool_lines or '- (none recorded)'}\n\n"
        "## Files touched\n"
        f"{file_lines or '- (none recorded)'}\n\n"
        "## Transcript\n"
        f"Full transcript: `{transcript_path or '(not provided)'}` — not copied into the "
        "vault, pointer only. Read it directly for the judgment work the `distill-memory` "
        "skill's Phase 1 (analyze) needs.\n"
    )
    mv.write_note(dest, frontmatter, body)
    return dest


def main() -> int:
    try:
        raw = sys.stdin.read()
    except Exception:
        return 0

    try:
        hook_input = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        hook_input = {}

    vault = mv.resolve_vault()
    if vault is None:
        return 0  # no vault configured — silent no-op, per contract/PROFILE.md

    session_id = hook_input.get("session_id")
    transcript_path = hook_input.get("transcript_path")
    if not session_id or not transcript_path:
        return 0  # nothing usable in the hook payload; not an error

    try:
        capture_session(hook_input, vault)
    except Exception as exc:
        try:
            mv.write_dlq_note(
                vault,
                slug="session-capture-failure",
                title=f"Session-capture hook failed for session {str(session_id)[:8]}",
                what_happened=f"hooks/lib/session_capture.py raised {type(exc).__name__}: {exc}",
                why_recorded=(
                    "A SessionEnd hook must never break a session; rather than raising, "
                    "the failure is recorded here for manual follow-up."
                ),
            )
        except Exception:
            pass  # even the DLQ write failing must not propagate out of a hook

    return 0


if __name__ == "__main__":
    sys.exit(main())
