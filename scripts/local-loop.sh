#!/bin/zsh
# The local improvement loop: one radar scan (with promotion) and a dry ingest against a throwaway
# clone of the vault, every Reader write logged instead of sent (TOOLKIT_READER_SHADOW). Seconds,
# not a cloud run, and nothing moves in Reader or reaches the vault's remote.
# [earned: 2026-09-30 — the owner: "test the ingest and distill locally to have a faster
# improvement loop"]
#
#   TOOLKIT_VAULT=~/Documents/TheVoid scripts/local-loop.sh [workdir]
#
# Distill needs an agent: in an interactive session, run begin/queue/end with this checkout's
# scripts against the real vault and distill the queue with the distill skill (subagents in
# parallel, one per group of captures that touch the same notes). Never a headless `claude -p`
# for it: without a token in ~/.env it falls back to the macOS Keychain. [earned: 2026-09-30]
set -euo pipefail
: "${TOOLKIT_VAULT:?set TOOLKIT_VAULT to the vault to clone}"
REPO="$(cd "$(dirname "$0")/.." && pwd -P)"
WORK="${1:-$(mktemp -d -t toolkit-loop)}"
mkdir -p "$WORK"
git clone -q "$TOOLKIT_VAULT" "$WORK/vault"
git -C "$WORK/vault" remote set-url --push origin DISABLED-local-loop
export TOOLKIT_READER_SHADOW="$WORK/reader-writes.jsonl"
: > "$TOOLKIT_READER_SHADOW"
cd "$REPO"
TOOLKIT_VAULT="$WORK/vault" uv run --locked --project plugins/radar/scripts \
  python3 plugins/radar/scripts/radar.py scan --since 1d --promote --json > "$WORK/scan.json"
TOOLKIT_VAULT="$WORK/vault" uv run --locked --project plugins/readwise/scripts \
  python3 plugins/readwise/scripts/ingest.py --dry-run --json > "$WORK/ingest.json" || true
python3 - "$WORK" <<'PY'
import json, sys
from pathlib import Path
work = Path(sys.argv[1])
scan = json.loads((work / "scan.json").read_text())
writes = [json.loads(line) for line in (work / "reader-writes.jsonl").read_text().splitlines() if line.strip()]
print(f"scan: {scan.get('status')} · judged {scan.get('judged', 0)} · promoted by bubble {scan.get('bubbles', {})} "
      f"· must-see {scan.get('must_see', 0)} · held {scan.get('held', 0) + scan.get('sensors_held', 0)}")
print(f"Reader writes (logged, not sent): {len(writes)}")
for w in writes[:10]:
    print("  ", w["method"], w["url"].rsplit("/", 2)[-2], (w.get("data") or {}).get("url", ""))
briefings = sorted((work / "vault" / "00_Memory" / "radar").glob("Bubbles-*.md"))
print(f"briefing: {briefings[-1] if briefings else '(none)'}")
print(f"workdir: {work}")
PY
