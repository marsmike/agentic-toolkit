#!/bin/bash
# The Claude cloud environment's setup script for the TheVoid routines (pipeline and watchdog).
# Paste this file's content into the environment's "Setup script" field on claude.ai; it runs at
# the start of every session, before Claude Code starts and before any repository exists, so it
# prepares the machine only. The environment caches its result across runs. cloud/README.md
# explains each part; this file is the source, the README does not repeat it.
set -u

# uv runs every script (their dependencies install on the first `uv run`).
command -v uv >/dev/null 2>&1 || pip install -q uv || echo "uv not installed; the routine installs it"

# td, Doist's Todoist CLI: reads TODOIST_API_TOKEN, lets radar's --todoist comment on the epics directly.
if command -v npm >/dev/null 2>&1; then
  command -v td >/dev/null 2>&1 || npm install -g --silent @doist/todoist-cli || echo "td not installed; Todoist falls back to the connector"
else
  echo "npm missing: td not installed; Todoist falls back to the connector"
fi

# github.com over https: username x-access-token, password $GH_TOKEN, read at the time git asks,
# never written into a URL or a remote (cloud-vault.sh's remote check still sees the plain URL).
# Silent when GH_TOKEN is unset, so whatever git access the environment itself provides still applies.
# shellcheck disable=SC2016  # single quotes on purpose: git expands $1 and $GH_TOKEN when it asks
git config --global credential.https://github.com.helper \
  '!f() { test "$1" = get && test -n "${GH_TOKEN:-}" && echo username=x-access-token && echo "password=$GH_TOKEN"; }; f'
git config --global user.name >/dev/null || git config --global user.name "Claude (pipeline routine)"
git config --global user.email >/dev/null || git config --global user.email "noreply@anthropic.com"

# The engines (farsight, gaiafield): the vault's search and graph. `toolkit engines install` lives in
# the toolkit repo, which does not exist yet at this point, so a shallow clone pinned to a reviewed
# release tag runs it (never the mutable default branch; move the pin when engines are released).
# The binaries land in $XDG_DATA_HOME/agentic-toolkit/bin, default ~/.local/share/agentic-toolkit/bin,
# sha256-verified, and the environment's cache keeps them across runs. The routine's SETUP runs the
# same command again: a no-op when they are present.
TOOLKIT_PIN=gaiafield-v0.2.2
TOOLKIT_DATA="${XDG_DATA_HOME:-$HOME/.local/share}/agentic-toolkit"
if command -v uv >/dev/null 2>&1; then
  tmp=$(mktemp -d)
  if git clone -q --depth 1 --branch "$TOOLKIT_PIN" https://github.com/marsmike/agentic-toolkit "$tmp/toolkit" \
     && (cd "$tmp/toolkit" && uv run --locked toolkit engines install); then
    echo "engines: $(cd "$tmp/toolkit" && uv run --locked toolkit engines status 2>/dev/null | tr -s ' ' | tr '\n' ';')"
  else
    echo "engines not installed here; the routine's SETUP installs them"
  fi
  rm -rf "$tmp"
else
  echo "uv missing: engines not installed here; the routine's SETUP installs them"
fi

# gaiafield's embedding model (potion-base-8M, about 30 MB, sha256-pinned in the binary): fetched
# once into the cached data directory, so `infer` in a run never needs the network. The routine's
# SETUP exports the same TOOLKIT_GAIAFIELD_MODEL_DIR; without it gaiafield would download the model
# next to each fresh checkout's graph db, every run. [earned: 2026-09-26 — a run's `infer` failed
# on the download's TLS handshake and the dossier lost its graph; the cache is the belt, the
# binary's OS trust store (gaiafield 0.2.2) the braces]
export TOOLKIT_GAIAFIELD_MODEL_DIR="$TOOLKIT_DATA/models/potion-base-8M"
if [ -x "$TOOLKIT_DATA/bin/gaiafield" ]; then
  "$TOOLKIT_DATA/bin/gaiafield" fetch-model || echo "model not fetched here; the routine's infer downloads it"
else
  echo "gaiafield missing: model not fetched here"
fi

echo "uv: $(uv --version 2>/dev/null || echo missing) · td: $(td --version 2>/dev/null || echo missing)"
python3 -c "import os; print('vars set:', {k: bool(os.environ.get(k)) for k in ('TOOLKIT_VAULT_REMOTE','GH_TOKEN','OPENROUTER_API_KEY','READWISE_TOKEN','KAGI_API_KEY','TODOIST_API_TOKEN')})"
