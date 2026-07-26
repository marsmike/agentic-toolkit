#!/usr/bin/env bash
# PreCompact hook -- thin launcher. All logic lives in scripts/handoff.py's `snapshot`
# subcommand (stdlib-only Python: no venv, no `uv`, no `jq` required). Always exits 0 --
# a hook must never block compaction or break the session it's attached to, regardless
# of what the worker does.
set -uo pipefail
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/handoff.py" snapshot >/dev/null 2>&1 || true
exit 0
