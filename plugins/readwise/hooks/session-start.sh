#!/usr/bin/env bash
# SessionStart hook: report Readwise sync status if configured, otherwise stay silent.
#
# Rewritten from v1: the old version printed "READWISE: No READWISE_TOKEN in ~/.env —
# plugin disabled" on EVERY session for EVERY user, including users who don't use
# Readwise at all — an error banner for people who never opted in. That's the exact
# failure this rewrite fixes: no READWISE_TOKEN means exit 0 with zero output, full stop.
# Only a user who has configured Readwise sees any output at all.
set -euo pipefail

[[ -f "$HOME/.env" ]] && source "$HOME/.env"

# Silent no-op — never an error banner for users without Readwise configured.
if [[ -z "${READWISE_TOKEN:-}" ]]; then
  exit 0
fi

# Vault resolution mirrors contract/PROFILE.md: TOOLKIT_VAULT env var, else ./vault
# relative to the repo root (found by walking up for .claude-plugin/marketplace.json).
VAULT="${TOOLKIT_VAULT:-}"
if [[ -z "$VAULT" ]]; then
  dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  while [[ "$dir" != "/" ]]; do
    if [[ -f "$dir/.claude-plugin/marketplace.json" ]]; then
      VAULT="$dir/vault"
      break
    fi
    dir="$(dirname "$dir")"
  done
fi

# No resolvable vault is also a silent no-op — a hook has no good way to surface an
# error usefully here, and guessing a path is worse than saying nothing.
if [[ -z "$VAULT" || ! -d "$VAULT" ]]; then
  exit 0
fi

STATE_FILE="$VAULT/00_Memory/readwise-state.md"
if [[ -f "$STATE_FILE" ]]; then
  last_sync=$(grep "lastSyncedAt:" "$STATE_FILE" 2>/dev/null | sed 's/lastSyncedAt: *//' | tr -d '"' || echo "never")
  echo "READWISE: Ready (last sync: $last_sync)"
else
  echo "READWISE: Ready (never synced — run /readwise-process)"
fi
