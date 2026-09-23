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
      # A clone of another vault must never be pulled or pushed under this remote's name.
      # Fetch and every push URL: `git push` honours remote.origin.pushurl, so both must match.
      urls="$(git -C "$LIVE" remote get-url origin 2>/dev/null; git -C "$LIVE" remote get-url --push --all origin 2>/dev/null)"
      if [[ -z "$urls" ]] || grep -qvxF -- "$TOOLKIT_VAULT_REMOTE" <<<"$urls"; then
        # The remote URL is not printed: it can carry embedded credentials.
        echo "$LIVE is a clone of a different remote than TOOLKIT_VAULT_REMOTE; move it away and open again" >&2
        exit 1
      fi
      # `end` pushes to the branch's upstream, so that must be the origin just checked.
      if [[ "$(git -C "$LIVE" rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)" != origin/* ]]; then
        echo "$LIVE does not track a branch of origin; move it away and open again" >&2
        exit 1
      fi
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
    run() { TOOLKIT_VAULT="$LIVE" uv run -q --project "$SCRIPTS" python3 "$SCRIPTS/pipeline_run.py" "$@"; }
    # Claim the run lock first, like any run, so two closes (or a close and a pipeline run in the
    # same clone) never write to git at once; `begin` commits the session's work and pulls.
    began="$(run begin --json)"
    token="$(python3 -c 'import json,sys; r=json.loads(sys.stdin.read()); print(r.get("token","") if r.get("status")=="ok" else "")' <<<"$began")"
    [[ -n "$token" ]] || { echo "$began"; echo "could not take the run lock; nothing was closed" >&2; exit 1; }
    # Exit non-zero unless `end` reports ok and the vault is in sync with its remote: `end` prints
    # its result either way, but a refused commit (a key-shaped string), a failed commit or a
    # failed push is not a closed vault. A session that changed nothing closes fine, no commit.
    result="$(run end "$@" --token "$token" --json)"
    echo "$result"
    python3 -c 'import json,sys; r=json.loads(sys.stdin.read()); ok = r.get("status") == "ok" and (r.get("sync") or {}).get("pushed", False); sys.exit(0 if ok else 1)' <<<"$result"
    ;;
  *)
    echo "usage: $0 open | close [--distilled N] [--dropped N] [--failed CAPTURE ...] [--note TEXT]" >&2
    exit 2
    ;;
esac
