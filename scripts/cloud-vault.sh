#!/usr/bin/env bash
# Work on the real vault from a session in this repo (a Claude cloud task, or any machine):
#
#   scripts/cloud-vault.sh open                 clone (or update) the vault into .vault-live/
#   export TOOLKIT_VAULT="$PWD/.vault-live"     then work with the skills
#   scripts/cloud-vault.sh close [end args]     index, maps, Now, secret scan, commit, pull, push
#
# The vault's git remote comes from TOOLKIT_VAULT_REMOTE, never from this file. `close` is the
# pipeline's own `end` (`pipeline_run.py end`), so a cloud session commits exactly like a run:
# `close --distilled 1 --note "cloud: <what>"`. .vault-live/ is git-ignored here; the toolkit
# never commits the vault. [earned: 2026-09-23, R12 — code stays in the toolkit repo]
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIVE="$ROOT/.vault-live"
SCRIPTS="$ROOT/plugins/obsidian/scripts"

case "${1:-}" in
  open)
    : "${TOOLKIT_VAULT_REMOTE:?set TOOLKIT_VAULT_REMOTE to the git URL of the vault}"
    if [[ -d "$LIVE/.git" ]]; then
      git -C "$LIVE" pull -q --rebase
    else
      git clone -q --depth 50 "$TOOLKIT_VAULT_REMOTE" "$LIVE"
    fi
    git -C "$LIVE" config user.name >/dev/null || git -C "$LIVE" config user.name "Claude (cloud session)"
    git -C "$LIVE" config user.email >/dev/null || git -C "$LIVE" config user.email "noreply@anthropic.com"
    uv sync -q --project "$SCRIPTS"
    python3 -c "import os; print('keys:', {k: bool(os.environ.get(k)) for k in ('OPENROUTER_API_KEY','READWISE_TOKEN','KAGI_API_KEY')})"
    echo "vault: $LIVE ($(git -C "$LIVE" log -1 --format='%h %s'))"
    echo "export TOOLKIT_VAULT=\"$LIVE\""
    ;;
  close)
    [[ -d "$LIVE/.git" ]] || { echo "no vault at $LIVE; run open first" >&2; exit 1; }
    shift
    TOOLKIT_VAULT="$LIVE" uv run -q --project "$SCRIPTS" python3 "$SCRIPTS/pipeline_run.py" end "$@" --json
    ;;
  *)
    echo "usage: $0 open | close [--distilled N] [--dropped N] [--failed CAPTURE ...] [--note TEXT]" >&2
    exit 2
    ;;
esac
