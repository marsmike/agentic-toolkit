#!/usr/bin/env python3
"""Fetch a stub capture's own source through the Tavily CLI — distill's "A stub is not the content".

    fetch_source.py 01_Capture/<capture>.md [--json]

Reads the URL from the capture's frontmatter (`source`) — never one given on the command line, so
neither a capture's text nor an agent can point it anywhere else — and asks `tvly extract` for the
page as Markdown. Prints the page (or with --json: {ok, url, title, content, via}); exit 1 with a
reason when the capture has no http(s) source, the host is not allowed, nothing came back, or a
keyed call would pass the weekly Tavily budget.

The one way the obsidian plugin talks to Tavily is the `tvly` CLI, as everywhere in the toolkit.
The key is read by this script (`secret`: the environment, then the key file) and handed to `tvly`
alone; the unattended run's agent holds none. Without a key `tvly` still extracts, under Tavily's
keyless rate cap — a keyless call costs nothing, so it is never budgeted or recorded.

Hosts: when TOOLKIT_PIPELINE_FETCH_DOMAINS is set (the local unattended run sets it, default
`github.com raw.githubusercontent.com`), only those domains and their subdomains; unset (an
interactive session, the cloud routine), any http(s) host. Tavily fetches the page on its own
servers, so nothing on the local network is reachable through it.

A keyed call is billed and budgeted like the radar's Tavily search: $0.008/credit, 1 credit per 5
URLs at basic depth, 2 at advanced — one URL a call, so a basic call costs 1/5 credit. Each keyed
call is recorded to this plugin's own ledger (`00_Memory/tavily-extract-ledger.jsonl`, the radar
ledger's row shape, so a whole-vault total can sum both); a call that would push the week's spend
past `tavily_weekly_budget_usd` (profile, default 2.00) is refused before it runs (`ok: false`,
never an exception). When a keyed basic extraction comes back with no content — a JS-rendered page
basic extract often can't see — fetch retries once at `--extract-depth advanced`, budgeted and
recorded the same way.
[earned: 2026-09-28 — the owner chose the Tavily CLI as the uniform way to use Tavily; a direct
`tvly extract` grant would have bypassed the run's domain allow-list]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

from vault_utils import append_jsonl, profile_value, read_frontmatter, read_jsonl, require_vault, secret, vault_file

TIMEOUT = 90
CLIENT_NAME = "agentic-toolkit-distill"
PASS_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
            "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy")

# This plugin's own extract ledger — never the radar's `00_Memory/radar/`, same row shape as its
# tavily-ledger*.jsonl so a whole-vault Tavily total can sum every writer's rows.
LEDGER = Path("00_Memory") / "tavily-extract-ledger.jsonl"
USD_PER_CREDIT = 0.008
CREDITS_PER_5_URLS = {"basic": 1, "advanced": 2}  # tvly extract bills per up to 5 URLs a call; one here
DEFAULT_WEEKLY_BUDGET_USD = 2.00


class OverBudget(RuntimeError):
    pass


def tvly_binary() -> str | None:
    """`TOOLKIT_TVLY_BIN`, then PATH, then uv's tool directory (`uv tool install tavily-cli`)."""
    env = os.environ.get("TOOLKIT_TVLY_BIN")
    if env:
        return env
    found = shutil.which("tvly")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "tvly"
    return str(fallback) if fallback.is_file() else None


def allowed(host: str) -> bool:
    domains = os.environ.get("TOOLKIT_PIPELINE_FETCH_DOMAINS")
    if not domains:
        return True
    host = host.lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in (x.strip().lower() for x in domains.replace(",", " ").split()) if d)


def _spent_this_week(vault: Path, now: datetime) -> float:
    since = now - timedelta(days=7)
    total = 0.0
    for r in read_jsonl(vault / LEDGER):
        try:
            if datetime.fromisoformat(r["at"]) >= since:
                total += float(r.get("usd") or 0)
        except (KeyError, TypeError, ValueError):
            continue
    return total


def _weekly_budget(vault: Path) -> float:
    """`tavily_weekly_budget_usd`, read robustly: anything that doesn't parse as a number falls
    back to the default rather than breaking the budget check."""
    raw = profile_value(vault, "tavily_weekly_budget_usd", DEFAULT_WEEKLY_BUDGET_USD)
    try:
        return float(raw)
    except (TypeError, ValueError):
        return DEFAULT_WEEKLY_BUDGET_USD


def _record(vault: Path, url: str, depth: str, now: datetime) -> None:
    credits = CREDITS_PER_5_URLS[depth] / 5
    append_jsonl(vault / LEDGER, {"at": now.isoformat(), "kind": "extract", "query": url,
                                   "credits": credits, "usd": credits * USD_PER_CREDIT, "balance": None})


def extract(url: str, depth: str = "basic") -> dict:
    """The one call out to `tvly` here. Evals replace it with a stub."""
    exe = tvly_binary()
    if exe is None:
        raise RuntimeError("tvly is not installed (uv tool install tavily-cli)")
    env = {k: os.environ[k] for k in PASS_ENV if os.environ.get(k)}
    key = secret("TAVILY_API_KEY")
    if key:
        env["TAVILY_API_KEY"] = key
    args = [exe, "extract", url, "--format", "markdown", "--client-name", CLIENT_NAME, "--json"]
    if depth == "advanced":
        args += ["--extract-depth", "advanced"]
    proc = subprocess.run(args, capture_output=True, text=True, timeout=TIMEOUT, env=env)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr.strip() or proc.stdout.strip() or f"tvly exited {proc.returncode}")[:200])
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"tvly returned no JSON: {proc.stdout[:120]!r}") from e
    if not isinstance(data, dict):
        raise RuntimeError("tvly returned an unexpected shape")
    return data


def _extract_billed(vault: Path, url: str, now: datetime, depth: str) -> dict:
    """`extract()` plus the ledger: budgeted before a keyed call (refused, never raised past this
    as anything but OverBudget) and recorded after one that actually ran. A keyless call is free
    and goes unrecorded."""
    keyed = bool(secret("TAVILY_API_KEY"))
    if keyed:
        credits = CREDITS_PER_5_URLS[depth] / 5
        usd = credits * USD_PER_CREDIT
        budget = _weekly_budget(vault)
        if _spent_this_week(vault, now) + usd > budget:
            raise OverBudget(f"Tavily weekly budget ${budget:.2f} reached")
    data = extract(url, depth=depth)
    if keyed:
        _record(vault, url, depth, now)
    return data


def _results(data: dict) -> list[dict]:
    return [r for r in data.get("results") or [] if str(r.get("raw_content") or "").strip()]


def fetch(vault: Path, capture_arg: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    capture = vault_file(vault, capture_arg)
    if not capture.is_file():
        return {"ok": False, "reason": f"no such capture: {capture_arg}"}
    fm, _ = read_frontmatter(capture)
    url = str(fm.get("source") or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return {"ok": False, "reason": "the capture records no http(s) source"}
    if not allowed(parsed.hostname):
        return {"ok": False, "url": url, "reason": f"{parsed.hostname} is not in TOOLKIT_PIPELINE_FETCH_DOMAINS"}
    try:
        data = _extract_billed(vault, url, now, "basic")
    except OverBudget as e:
        return {"ok": False, "url": url, "reason": str(e)}
    except (OSError, subprocess.SubprocessError, RuntimeError, json.JSONDecodeError) as e:
        return {"ok": False, "url": url, "reason": f"tvly extract failed: {str(e)[:200]}"}
    results = _results(data)
    if not results and secret("TAVILY_API_KEY"):
        # A JS-rendered page's content often only shows up at advanced depth.
        try:
            data = _extract_billed(vault, url, now, "advanced")
        except OverBudget as e:
            return {"ok": False, "url": url, "reason": str(e)}
        except (OSError, subprocess.SubprocessError, RuntimeError, json.JSONDecodeError) as e:
            return {"ok": False, "url": url, "reason": f"tvly extract failed: {str(e)[:200]}"}
        results = _results(data)
    if not results:
        failed = data.get("failed_results") or []
        detail = (failed[0].get("error") if failed and isinstance(failed[0], dict) else None) or "no content"
        return {"ok": False, "url": url, "reason": f"nothing extracted: {str(detail)[:160]}"}
    r = results[0]
    return {"ok": True, "url": url, "title": str(r.get("title") or ""), "content": str(r["raw_content"]),
            "via": "tavily"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("capture", help="vault-relative path of the capture, e.g. 01_Capture/<capture>.md")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = fetch(require_vault(), args.capture)
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    elif result["ok"]:
        print(f"# {result['title']}\n\n*Fetched from {result['url']} via Tavily*\n\n{result['content']}")
    else:
        print(f"not fetched: {result['reason']}", file=sys.stderr)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
