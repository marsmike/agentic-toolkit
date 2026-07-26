#!/usr/bin/env bash
# SessionEnd hook — thin wrapper. All logic lives in hooks/lib/session_capture.py
# (stdlib-only Python: no venv, no `uv`, no `jq` required). Always exits 0 — a hook
# must never break the session it's attached to, regardless of what the worker does.
set -uo pipefail
python3 "${CLAUDE_PLUGIN_ROOT}/hooks/lib/session_capture.py"
exit 0
