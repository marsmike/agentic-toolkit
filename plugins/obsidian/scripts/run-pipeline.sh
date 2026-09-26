#!/bin/zsh
# One unattended pipeline run: Claude Code headless with the pipeline skill.
# Scheduled every 3 hours by launchd; see skills/pipeline/references/scheduling.md.
# Plain bash syntax as well (core/tests/test_pipeline_policy.py runs it under either shell).
set -euo pipefail
export TOOLKIT_REPO="${TOOLKIT_REPO:-$HOME/Developer/agentic-toolkit}"
: "${TOOLKIT_VAULT:?set TOOLKIT_VAULT to the vault this run keeps current}"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$TOOLKIT_REPO"
REPO="$(pwd -P)"
VAULT="$(cd "$TOOLKIT_VAULT" && pwd -P)"
export TOOLKIT_VAULT="$VAULT"

# The run distills text other people wrote, so the agent holds no key and reaches only what the
# skills name. [earned: 2026-09-24, review-01 SEC-1: `Bash(uv run:*)` ran any code, the agent's
# environment held every key in ~/.env, and WebFetch reached any host]
# - Keys: never sourced here. The agent starts from an empty environment plus the names below
#   (Claude Code's own login, locale, TOOLKIT_* settings that are not a key or token), so nothing
#   the caller exported reaches it. Each script reads the one key it needs from the key file itself
#   (vault_utils.secret: TOOLKIT_KEYS_FILE, default ~/.env); the agent may neither read nor edit it.
# - Bash: exactly the scripts the pipeline and distill skills run, each through `uv run --locked`,
#   written relative to the repo; a shell function, a variable, `cd` or `python3 -c` is refused.
# - Files: read the repo and the vault, write the vault only; the agent's own file tools never read or
#   write either .git (history, hooks, remote; the granted scripts' git calls still work) and never write
#   Config/toolkit (a profile names the host a key is sent to).
# - WebFetch: only the domains in TOOLKIT_PIPELINE_FETCH_DOMAINS, for a stub's own source; a
#   stub elsewhere ends as a short note with its link (distill "A stub is not the content").
KEYS_FILE="${TOOLKIT_KEYS_FILE:-$HOME/.env}"
[[ "$KEYS_FILE" = /* ]] || KEYS_FILE="$PWD/$KEYS_FILE"
export TOOLKIT_KEYS_FILE="$KEYS_FILE"
AGENT_ENV=()
for name in HOME PATH USER LOGNAME SHELL TMPDIR LANG LC_ALL LC_CTYPE TERM \
    XDG_CONFIG_HOME XDG_DATA_HOME XDG_CACHE_HOME CLAUDE_CONFIG_DIR \
    ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN ANTHROPIC_BASE_URL CLAUDE_CODE_OAUTH_TOKEN \
    $(env | sed -n 's/^\(TOOLKIT_[A-Z0-9_]*\)=.*/\1/p'); do
  case "$name" in TOOLKIT_*KEY|TOOLKIT_*TOKEN) continue ;; esac
  if value="$(printenv "$name")"; then AGENT_ENV+=("$name=$value"); fi
done
# claude itself needs its own auth (above), but nothing it starts may inherit it: the scrub strips
# Anthropic credentials from every Bash command, hook and MCP server the run spawns, so a granted
# script or a steered prompt cannot print or forward them. [earned: 2026-09-24, Copilot review of #26]
AGENT_ENV+=("CLAUDE_CODE_SUBPROCESS_ENV_SCRUB=1")
FETCH_DOMAINS="${TOOLKIT_PIPELINE_FETCH_DOMAINS:-github.com raw.githubusercontent.com}"

script() {  # plugin, script, [fixed leading args]: the command, with and without further args
  local cmd="uv run --locked --project plugins/$1/scripts python3 plugins/$1/scripts/$2${3:+ $3}"
  printf 'Bash(%s),Bash(%s *),' "$cmd" "$cmd"
}
ALLOWED="$(script obsidian pipeline_run.py begin)$(script obsidian pipeline_run.py queue)"
ALLOWED+="$(script obsidian pipeline_run.py end)$(script obsidian index_build.py)"
ALLOWED+="$(script obsidian distill_judge.py)$(script obsidian distill_check.py)"
ALLOWED+="$(script obsidian retire_capture.py)$(script obsidian search.py)"
ALLOWED+="$(script radar radar.py scan)$(script radar radar.py gaps)$(script radar radar.py weekly)"
ALLOWED+="$(script radar radar.py sensors)$(script radar radar.py signal)"
ALLOWED+="$(script readwise ingest.py)"
# No bare Glob or Grep grant: a tool-level grant searches any directory (a run searched $HOME and
# returned ~/.env lines), and a Read deny covers only the path it names. Without the grant dontAsk
# still lets them search the working directories (repo and vault) and refuses everywhere else.
# [earned: 2026-09-25, Copilot review of #28, reproduced headless]
ALLOWED+="Read(/$REPO/**),Read(/$VAULT/**),Edit(/$VAULT/**),Skill"
for domain in $(printf '%s' "$FETCH_DOMAINS" | tr ',' ' '); do ALLOWED+=",WebFetch(domain:$domain)"; done
# .git is denied to the agent's file tools for reads too: history can hold old secrets, and hooks and
# remotes are not the agent's business. (A granted script that runs git still reads it; that is the
# script's job, and the scripts are the reviewed surface.) [earned: 2026-09-24, Copilot review of #26]
DENIED="Read(/$KEYS_FILE),Edit(/$KEYS_FILE),Read(/$VAULT/.git),Read(/$VAULT/.git/**),Read(/$REPO/.git),Read(/$REPO/.git/**)"
# `.git` is a file in a worktree, which `.git/**` does not match: deny the exact path as well.
DENIED+=",Edit(/$VAULT/.git),Edit(/$VAULT/.git/**),Edit(/$REPO/.git),Edit(/$REPO/.git/**),Edit(/$VAULT/Config/toolkit/**),Edit(/$REPO/**)"

PROMPT="Run the obsidian:pipeline skill against the vault in TOOLKIT_VAULT ($VAULT). \
Run every script from the working directory exactly as \
'uv run --locked --project plugins/<plugin>/scripts python3 plugins/<plugin>/scripts/<script> <args>' \
(plugin obsidian, radar or readwise); no shell function, variable, cd or other command is permitted. \
Reply with the one-line run summary."

# The prompt goes first: --allowedTools takes several values and would swallow it. User settings
# only: the repo's .claude/settings.json enables its plugins for interactive and cloud sessions, and
# a headless run cannot answer its trust prompt; --plugin-dir loads them here instead. dontAsk:
# anything not allowed above is refused, not prompted.
exec env -i "${AGENT_ENV[@]}" claude -p "$PROMPT" \
  --setting-sources user --plugin-dir plugins/obsidian --plugin-dir plugins/radar \
  --add-dir "$VAULT" \
  --permission-mode dontAsk \
  --allowedTools "$ALLOWED" \
  --disallowedTools "$DENIED" \
  < /dev/null
