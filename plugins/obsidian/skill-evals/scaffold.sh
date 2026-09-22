#!/bin/bash
# Fresh example vault in the run's workspace, plus the marketplace marker vault_utils uses
# to resolve the vault when TOOLKIT_VAULT is not set (EVAL_* is the only env that gets in).
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
mkdir -p .claude-plugin
echo '{"name":"eval-workspace","plugins":[]}' > .claude-plugin/marketplace.json
rm -rf vault && cp -R "$repo/vault" vault
rm -rf vault/.gaiafield vault/00_Memory/.search-cache
# The sandbox has no network and a fresh HOME, so `uv run --project .../scripts` cannot
# create the scripts' environment inside it. Build it here, on the host, where it can.
uv sync --project "$here/../scripts" --quiet
# Jev as the judge: the check's preservation and findability findings need the judgment
# backend, and only EVAL_* env reaches the sandbox. A project settings file in the workspace
# is read by the child session and carries the key for the run only (never committed; the
# workspace is thrown away). Skipped silently when ~/.env has no key: the case then runs the
# no-backend path and the soft findings are absent.
# The harness runs this with a throwaway HOME, so ~ is not the user's home; ask the passwd db.
real_home="$(eval echo "~$(id -un)")"
key="$( (grep -E '^(export )?OPENROUTER_API_KEY=' "$real_home/.env" 2>/dev/null || true) | head -1 | cut -d= -f2- | tr -d '"' | tr -d "'")"
if [ -n "$key" ]; then
  mkdir -p .claude
  printf '{"env":{"OPENROUTER_API_KEY":"%s"}}\n' "$key" > .claude/settings.json
fi
