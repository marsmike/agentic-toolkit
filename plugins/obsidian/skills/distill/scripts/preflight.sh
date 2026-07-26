# shellcheck shell=bash
# Distill preflight — source this, don't execute it.
#
#   source "${CLAUDE_PLUGIN_ROOT}/skills/distill/scripts/preflight.sh"
#
# Exports: VAULT, DISTILL_TMP
# Defines: extract_urls, canonicalize_urls
#
# Filesystem-first by design (contract/KNOWLEDGE_API.md) — there is no app-CLI mode to
# probe here, unlike v1. If you want the optional Obsidian desktop CLI enhancement, see
# vault-ops/references/commands.md's silent-exit-0 trap before trusting its exit code.

# --- vault ---------------------------------------------------------------
if [[ -n "${TOOLKIT_VAULT:-}" ]]; then
  export VAULT="$TOOLKIT_VAULT"
else
  # Walk up from cwd for the repo marker, same resolution order as vault_utils.py.
  _dir="$PWD"
  while [[ "$_dir" != "/" ]]; do
    if [[ -f "$_dir/.claude-plugin/marketplace.json" ]]; then
      export VAULT="$_dir/vault"
      break
    fi
    _dir="$(dirname "$_dir")"
  done
  unset _dir
fi

if [[ -z "${VAULT:-}" || ! -d "${VAULT:-/nonexistent}/01_Capture" ]]; then
  echo "PREFLIGHT FAIL: no vault found (checked TOOLKIT_VAULT and ./vault under the repo root)" >&2
  return 1 2>/dev/null || exit 1
fi

# --- scratch dir -----------------------------------------------------------
export DISTILL_TMP="${CLAUDE_SCRATCHPAD_DIR:-${TMPDIR:-/tmp}}/distill"
mkdir -p "$DISTILL_TMP"

# --- URL helpers ------------------------------------------------------------
# Allowlist of RFC-3986 URL characters, not a denylist — a denylist like `[^)>" ]`
# leaks markdown-link-syntax collisions (`[url](url` -> `url](url`). Parens are
# excluded from the allowlist deliberately since markdown link syntax is common.
extract_urls() {
  grep -oE 'https?://[A-Za-z0-9._~:/?#@!$&*+,;=%-]+' "$1" \
    | sed -E 's/[.,;:]+$//' \
    | sort -u
}

# Lowercases and strips trailing slash for diffing two URL sets. Never write a
# canonicalized URL into a note — it is for comparison only, not for citing; some
# hosts (URL shorteners) are case-sensitive in their path.
canonicalize_urls() {
  extract_urls "$1" | sed -E 's|/$||' | tr '[:upper:]' '[:lower:]' | sort -u
}

echo "distill preflight OK"
echo "  VAULT=$VAULT"
echo "  DISTILL_TMP=$DISTILL_TMP"
