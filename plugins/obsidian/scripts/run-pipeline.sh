#!/bin/zsh
# One unattended pipeline run: Claude Code headless with the pipeline skill.
# Scheduled every 3 hours by launchd; see skills/pipeline/references/scheduling.md.
set -euo pipefail
export TOOLKIT_REPO="${TOOLKIT_REPO:-$HOME/Developer/agentic-toolkit}"
REPO="$TOOLKIT_REPO"
: "${TOOLKIT_VAULT:?set TOOLKIT_VAULT to the vault this run keeps current}"
# Keys (READWISE_TOKEN, OPENROUTER_API_KEY, KAGI_API_KEY) come from ~/.env, never from the repo.
[[ -f "$HOME/.env" ]] && { set -a; source "$HOME/.env"; set +a; }
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
cd "$REPO"
# The prompt goes first: --allowedTools takes several values and would swallow it. User settings
# only: the repo's .claude/settings.json enables its plugins for interactive and cloud sessions, and
# a headless run cannot answer its trust prompt; --plugin-dir loads them here instead.
exec claude -p "Run the obsidian:pipeline skill against the vault in TOOLKIT_VAULT ($TOOLKIT_VAULT). Reply with the one-line run summary." \
  --setting-sources user --plugin-dir plugins/obsidian --plugin-dir plugins/radar \
  --add-dir "$TOOLKIT_VAULT" \
  --permission-mode acceptEdits \
  --allowedTools "Bash(uv run:*),Bash(uv:*),Bash(env:*),Bash(python3:*),Bash(git -C:*),Bash(trash:*),Bash(ls:*),Bash(mkdir:*),Bash(mv:*),Read,Write,Edit,Glob,Grep,Skill,WebFetch" \
  < /dev/null
