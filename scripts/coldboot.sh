#!/usr/bin/env bash
# Cold-boot ritual: verify the stranger experience end-to-end before a release.
# Clones the PUBLISHED repo into a temp dir, uses RELEASED binaries, and (opt-in)
# drives a real headless claude session against an ISOLATED config — never your
# own ~/.claude, never your own vault.
#
# Usage:
#   scripts/coldboot.sh              # stages 1-3: clone, doctor, engines
#   scripts/coldboot.sh --live       # + stage 4: headless claude -p distill phase-1
#
# [earned: cold-boot test 2026-07-26 — found the uv workspace-dep quick-start
# failure, missing example profiles, and the headless permission-mode wall]
set -euo pipefail

REPO="marsmike/agentic-toolkit"
WORK="$(mktemp -d -t toolkit-coldboot)"
trap 'rm -rf "$WORK"' EXIT
echo "workdir: $WORK"

# Stage 1 — only the doctor half of the README quick start.
# The README quick start is clone + `uv run toolkit doctor` + `claude plugin marketplace
# add .` + `claude plugin install obsidian@agentic-toolkit`; the marketplace-add/install
# part needs an isolated CLAUDE_CONFIG_DIR (never the developer's own), so it doesn't run
# until Stage 4 (--live) below. Stages 1-3 without --live verify the doctor/engine half
# only, not the full quick start end to end.
git clone -q "https://github.com/$REPO.git" "$WORK/repo"
cd "$WORK/repo"
uv run toolkit doctor

# Stage 2 — released engine binaries, as a stranger downloads them
mkdir -p bin
case "$(uname -sm)" in
  "Darwin arm64") SUFFIX="aarch64-apple-darwin" ;;
  "Linux x86_64") SUFFIX="x86_64-unknown-linux-musl" ;;
  "Linux aarch64") SUFFIX="aarch64-unknown-linux-musl" ;;
  *) echo "unsupported platform for release binaries"; exit 1 ;;
esac
for engine in farsight gaiafield; do
  tag=$(gh release list -R "$REPO" --json tagName -q ".[] | .tagName | select(startswith(\"$engine-v\"))" | head -1)
  gh release download "$tag" -p "$engine-$SUFFIX" -O "bin/$engine" -R "$REPO"
  chmod +x "bin/$engine"
done

# Stage 3 — engine smoke checks against the example vault
./bin/farsight query "retrieval verification" --vault ./vault --k 3 --json \
  | python3 -c "import json,sys; r=json.load(sys.stdin); assert r, 'farsight: no results'; print('farsight ok:', r[0]['path'].split('/')[-1])"
./bin/gaiafield index --vault ./vault --json \
  | python3 -c "import json,sys; d=json.load(sys.stdin); assert d['total_nodes'] > 50, d; print('gaiafield ok:', d['total_nodes'], 'nodes')"

[ "${1:-}" = "--live" ] || { echo "cold boot (stages 1-3) PASSED — rerun with --live for the headless-session stage"; exit 0; }

# Stage 4 — live headless session, isolated config.
# Notes that cost us a debugging round each:
#  - --allowedTools takes ONE comma-separated argument, not repeated strings
#  - skills compose `env VAR=... uv run ...` lines, so Bash(env:*) is required
#  - auth: copy an OAuth credential blob into $ISOLATED/.credentials.json first
ISOLATED="$WORK/claude-config"
mkdir -p "$ISOLATED"
if security find-generic-password -s "Claude Code-credentials" -w > "$ISOLATED/.credentials.json" 2>/dev/null; then
  chmod 600 "$ISOLATED/.credentials.json"
else
  echo "no keychain credentials — run: CLAUDE_CONFIG_DIR=$ISOLATED claude /login"; exit 1
fi
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN CLAUDE_CONFIG_DIR="$ISOLATED" \
  claude plugin marketplace add "$REPO" >/dev/null
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN CLAUDE_CONFIG_DIR="$ISOLATED" \
  claude plugin install "obsidian@agentic-toolkit" >/dev/null

OUT=$(env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN \
  CLAUDE_CONFIG_DIR="$ISOLATED" TOOLKIT_VAULT="$PWD/vault" \
  TOOLKIT_FARSIGHT_BIN="$PWD/bin/farsight" TOOLKIT_GAIAFIELD_BIN="$PWD/bin/gaiafield" \
  claude -p \
  --allowedTools "Bash(uv run:*),Bash(uv:*),Bash(env:*),Bash(python3:*),Bash(./bin/farsight:*),Bash(./bin/gaiafield:*)" \
  --max-turns 40 \
  "Use the obsidian plugin's distill skill, PHASE 1 ONLY (analysis — no writes): triage the capture 01_Capture/Readwise-Hybrid-Search-Landscape.md in the vault at ./vault. End with the exact line 'ENGINES: ok' if both farsight and gaiafield executed successfully, or 'ENGINES: failed' otherwise.")

echo "$OUT" | tail -5
echo "$OUT" | grep -q "ENGINES: ok" || { echo "live stage FAILED"; exit 1; }
git -C . status --porcelain | grep -v "^?? bin/" | grep -q . && { echo "FAILED: live session modified tracked files"; exit 1; }
echo "cold boot (all stages) PASSED"
