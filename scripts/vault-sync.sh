#!/bin/zsh
# The Mac's half of git as the vault's sync channel while the pipeline runs as a cloud routine:
# `pipeline_run.py sync` commits hand edits (the pipeline's secret scan), pulls the cloud's commits
# (a conflict is aborted with a DLQ note) and pushes. launchd runs it every 10 minutes
# (io.agentic-toolkit.vault-sync, plugins/obsidian/skills/pipeline/references/scheduling.md), with
# or without Obsidian open. One line per run on stdout; a macOS notification only when something
# needs a human. [earned: 2026-10-01 — nothing on the Mac pulled after the pipeline moved to the
# cloud: the vault, and the devices Obsidian Sync feeds from it, lagged until a session pulled]
#
#   TOOLKIT_VAULT=~/Documents/TheVoid scripts/vault-sync.sh
#
# Git authenticates with GH_TOKEN (or GITHUB_TOKEN) from ~/.env (TOOLKIT_KEYS_FILE), through a
# credential helper that only answers from that variable: every configured helper is reset first,
# so an unattended run never reaches the macOS Keychain (gh's keyring, osxkeychain) and never
# prompts. Without a token the pull and push fail, and the run says so.
set -uo pipefail
: "${TOOLKIT_VAULT:?set TOOLKIT_VAULT to the vault}"
REPO="$(cd "$(dirname "$0")/.." && pwd -P)"
export PATH="$HOME/.local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
STATE="${XDG_STATE_HOME:-$HOME/.local/state}/agentic-toolkit/vault-sync.status"
mkdir -p "${STATE:h}"

keys="${TOOLKIT_KEYS_FILE:-$HOME/.env}"
token=""
if [[ -r "$keys" ]]; then
  for name in GH_TOKEN GITHUB_TOKEN; do
    token="$(grep -E "^(export[[:space:]]+)?${name}=" "$keys" | tail -n 1 | sed -E "s/^(export[[:space:]]+)?${name}=//; s/^[\"']//; s/[\"']\$//")"
    [[ -n "$token" ]] && break
  done
fi
export TOOLKIT_SYNC_GIT_TOKEN="$token"
export GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=never
export GIT_CONFIG_COUNT=2
export GIT_CONFIG_KEY_0=credential.helper GIT_CONFIG_VALUE_0=""
export GIT_CONFIG_KEY_1=credential.helper
export GIT_CONFIG_VALUE_1='!f() { [ "$1" = get ] && [ -n "$TOOLKIT_SYNC_GIT_TOKEN" ] && printf "username=x-access-token\npassword=%s\n" "$TOOLKIT_SYNC_GIT_TOKEN"; :; }; f'

out="$(cd "$REPO" && uv run --locked --quiet --project plugins/obsidian/scripts \
  python3 plugins/obsidian/scripts/pipeline_run.py sync 2>&1)"
line="$(printf '%s\n' "$out" | tail -n 1)"
read -r sync_status detail <<<"$(printf '%s' "$line" | python3 -c '
import json, sys
try:
    r = json.loads(sys.stdin.read())
except ValueError:
    print("failed unreadable output"); sys.exit()
facts = []
if r.get("hand_edits"):
    facts.append("hand edits " + str(r["hand_edits"]))
if r.get("new_commits"):
    facts.append(str(r["new_commits"]) + " new")
print(r.get("status", "failed"), "; ".join(facts) or r.get("detail", "") or "up to date")
' 2>/dev/null || echo "failed unreadable output")"
[[ -z "${token}" ]] && detail="${detail}; no GH_TOKEN in ${keys}"
print -r -- "$(date -u '+%Y-%m-%d %H:%M')Z ${sync_status} ${detail}"

# Notify on what needs a human: a conflict or a refused key (once, when it starts), and failures
# that last an hour (offline, a dead token). Busy and ok never notify.
last_status="" count=0
[[ -r "$STATE" ]] && read -r last_status count < "$STATE"
[[ "$sync_status" == "$last_status" ]] && count=$((count + 1)) || count=1
print -r -- "$sync_status $count" > "$STATE"
message=""
case "$sync_status" in
  conflict) [[ $count -eq 1 ]] && message="Vault sync stopped: a conflict between the Mac and the cloud. See 00_Memory/dlq/ (pipeline-pull-conflict)." ;;
  refused) [[ $count -eq 1 ]] && message="Vault sync refused: a note holds a key-shaped string. See 00_Memory/dlq/ (pipeline-secret-refused)." ;;
  failed) [[ $count -eq 6 ]] && message="Vault sync has failed for an hour: ${detail}" ;;
esac
if [[ -n "$message" ]]; then
  osascript -e "display notification \"${message//\"/\'}\" with title \"The Void\"" >/dev/null 2>&1 || true
fi
exit 0
