#!/usr/bin/env bash
# agentic-toolkit bootstrap. What this does, in order:
#   1. Installs `uv` (asking first) if it isn't already on PATH.
#   2. Installs the `toolkit` CLI from GitHub via `uv tool install`.
#   3. Downloads the engine binaries (`toolkit engines install`) — sha256-recorded,
#      size-verified (no published checksum to verify against exists yet).
# Safe to re-run any time — every step below is idempotent. No sudo, ever.
#
# Usage: curl -LsSf https://raw.githubusercontent.com/marsmike/agentic-toolkit/main/install.sh | bash
set -euo pipefail

REPO_URL="https://github.com/marsmike/agentic-toolkit"

echo "== agentic-toolkit bootstrap =="

# uv's own installer and `uv tool install` both default to putting shims in
# ~/.local/bin; make sure this script's own PATH sees them even if the calling shell's
# rc files haven't been re-sourced yet.
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv (the Python package/tool manager this toolkit uses) was not found on PATH."
  read -r -p "Install uv now via the official astral.sh installer? [y/N] " reply
  case "$reply" in
    [yY]|[yY][eE][sS])
      curl -LsSf https://astral.sh/uv/install.sh | sh
      ;;
    *)
      echo "uv is required. Install it yourself, then re-run this script:"
      echo "  https://docs.astral.sh/uv/getting-started/installation/"
      exit 1
      ;;
  esac
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "error: uv still not on PATH after install — open a new shell and re-run this script."
  exit 1
fi

echo "-- installing the toolkit CLI (uv tool install) --"
uv tool install --force "git+${REPO_URL}#subdirectory=core"

echo "-- fetching engine binaries (toolkit engines install) --"
toolkit engines install

cat <<EOF

Done. Try it now:
  toolkit demo

Next step — add the Claude Code plugins:
  claude plugin marketplace add marsmike/agentic-toolkit
  claude plugin install obsidian@agentic-toolkit
EOF
