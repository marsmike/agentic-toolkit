#!/usr/bin/env bash
# Mechanical docs-truth checks — run before every release, alongside coldboot.sh.
#
# coldboot.sh verifies the stranger INSTALL experience end to end; this verifies the
# public DOCS content against the running system — the cheap, mechanically-catchable
# slice of that verification, not a substitute for the full adversarial pass. See
# vault/04_Resources/Concepts/The-Cold-Boot-Ritual.md, "A sibling ritual: verifying the
# docs site against reality".
#
# [earned: docs-vs-reality verification 2026-07-26 — 3 of 10 findings from an adversarial
# docs-vs-reality pass were mechanically catchable: the marketplace plugin-list drifting
# from marketplace.json, `vault init`'s no-default behavior silently regressing, and the
# backtick-inside-wikilink-alias class of Quartz renderer trip-up. This script exists so
# those 3 stay caught automatically instead of needing another adversarial pass to notice.]
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MARKETPLACE_JSON="$REPO_ROOT/.claude-plugin/marketplace.json"
CURATION_NOTE="$REPO_ROOT/vault/04_Resources/Tools/Marketplace-and-Plugin-Curation.md"
VAULT_DIR="$REPO_ROOT/vault"

fail=0

# --- (a) the curation note's shipped-plugin list must match marketplace.json exactly ---
echo "== docscheck: marketplace plugin list vs. Marketplace-and-Plugin-Curation.md =="

doc_plugins="$(sed -n '/^## Roadmap/q; s/^- \*\*\([A-Za-z0-9_-]*\)\*\*.*/\1/p' "$CURATION_NOTE" | sort)"
mp_plugins="$(python3 -c "
import json
with open('$MARKETPLACE_JSON', encoding='utf-8') as f:
    data = json.load(f)
print('\n'.join(sorted(p['name'] for p in data['plugins'])))
")"

if [ "$doc_plugins" != "$mp_plugins" ]; then
  echo "FAIL: shipped-plugin list in $CURATION_NOTE does not match marketplace.json"
  echo "  documented: $(echo "$doc_plugins" | tr '\n' ' ')"
  echo "  actual:     $(echo "$mp_plugins" | tr '\n' ' ')"
  fail=1
else
  echo "ok: documented shipped plugins match marketplace.json ($(echo "$mp_plugins" | tr '\n' ' '))"
fi

# --- (b) `toolkit vault init` with no path must exit nonzero (no default — locked) ---
echo "== docscheck: 'toolkit vault init' has no default path =="

if (cd "$REPO_ROOT" && uv run toolkit vault init) >/dev/null 2>&1; then
  echo "FAIL: 'toolkit vault init' with no path unexpectedly succeeded — Toolkit-CLI.md" \
       "documents this as a required positional with no default"
  fail=1
else
  echo "ok: 'toolkit vault init' with no path exits nonzero, as documented"
fi

# --- (c) cheap static stand-in for a full docs-site build: no backtick-in-wikilink-alias ---
echo "== docscheck: no backtick inside a wikilink alias (Quartz renderer trip-up) =="
# A full 'npx quartz build' check is skipped here even when available — this grep is the
# cheap static equivalent for the one known trip-up class (a `code span` inside the alias
# half of [[path|alias]] breaks Quartz's wikilink renderer); it is not a general build check.
hits="$(grep -rnE '\[\[[^]|]+\|[^]]*`[^]]*\]\]' "$VAULT_DIR" --include='*.md' || true)"
if [ -n "$hits" ]; then
  echo "FAIL: wikilink alias containing a backtick code-span found:"
  echo "$hits"
  fail=1
else
  echo "ok: no backtick-in-wikilink-alias found vault-wide"
fi

if [ "$fail" -ne 0 ]; then
  echo "docscheck: FAILED"
  exit 1
fi
echo "docscheck: all checks passed"
