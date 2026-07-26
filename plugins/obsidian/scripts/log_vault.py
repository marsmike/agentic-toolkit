#!/usr/bin/env python3
"""Append one line to the vault's Log.md recording a plugin action.

    uv run scripts/log_vault.py distill "Note Title"
    uv run scripts/log_vault.py lint "12 items need attention"

Creates Log.md at the vault root if absent. Vault resolved via TOOLKIT_VAULT / ./vault.
"""
from __future__ import annotations

import socket
import sys
from datetime import datetime

from vault_utils import require_vault

VALID_ACTIONS = {"distill", "lint", "normalize", "search", "retrieval-verification", "file-insight"}


def main() -> int:
    if len(sys.argv) < 3:
        print(f"Usage: log_vault.py <action> <title>\nactions: {', '.join(sorted(VALID_ACTIONS))}", file=sys.stderr)
        return 1

    action, title = sys.argv[1], sys.argv[2]
    if action not in VALID_ACTIONS:
        print(f"Warning: unrecognized action '{action}' (expected one of {sorted(VALID_ACTIONS)}) — logging anyway.", file=sys.stderr)

    vault = require_vault()
    log_path = vault / "Log.md"
    host = socket.gethostname().split(".")[0]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = f"- {ts} [{host}] {action} | {title}\n"

    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
