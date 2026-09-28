"""Tavily for the radar, through the Tavily CLI (`tvly`): the one way every part of the toolkit talks
to Tavily, locally and in the cloud routine (cloud/setup.sh installs it). Two uses:

- Reddit reach: Reddit refuses cloud addresses, so the Reddit sensor asks Tavily for the day's
  threads of each subreddit instead (no scores: Tavily does not carry them).
- The Signal Radar's name check: a few new names a day, searched on the week's web.

Only basic-depth search (1 credit; advanced costs 2 and was not needed, measured 2026-09-28). `tvly`
reports no usage, so the ledger records the list price: $0.008 a credit pay-as-you-go, after the
free 1,000 a month. A weekly budget (`tavily_weekly_budget_usd`, default 2.00) is checked before
every call, over both writers' ledgers, as for Kagi.

The key: read by this script (`secret`, never os.environ) and handed to `tvly` alone, in an
environment that carries nothing else of the caller's. Without a key the caller reports SKIPPED:
keyless `tvly` works under a rate cap, but a budget cannot be kept on calls it does not bill.

What leaves the machine: the subreddit queries and the entity names, to Tavily.
[earned: 2026-09-28 — the owner chose the Tavily CLI as the uniform way to use Tavily]
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from kagi import Ledger
from vault_utils import secret

USD_PER_CREDIT = 0.008
CREDITS = {"basic": 1}
DEFAULT_WEEKLY_BUDGET_USD = 2.00
TIMEOUT = 60
CLIENT_NAME = "agentic-toolkit-radar"
# One ledger file per writer (see kagi.LEDGER): the pipeline's scan and the Signal Radar both push.
LEDGER = "tavily-ledger.jsonl"
SIGNAL_LEDGER = "tavily-ledger-signal.jsonl"
# What `tvly` may see of the caller's environment besides its key.
PASS_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
            "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy")


class NoKey(RuntimeError):
    """TAVILY_API_KEY is not set. Callers report SKIPPED."""


class NoCli(RuntimeError):
    """`tvly` is not installed. Callers report SKIPPED."""


class TavilyError(RuntimeError):
    pass


class OverBudget(TavilyError):
    pass


def binary() -> str | None:
    """`TOOLKIT_TVLY_BIN`, then PATH, then uv's tool directory (`uv tool install tavily-cli`)."""
    env = os.environ.get("TOOLKIT_TVLY_BIN")
    if env:
        return env
    found = shutil.which("tvly")
    if found:
        return found
    fallback = Path.home() / ".local" / "bin" / "tvly"
    return str(fallback) if fallback.is_file() else None


def _run(args: list[str]) -> dict:
    """The one call out to `tvly` in this module. Evals replace it with a stub."""
    key = secret("TAVILY_API_KEY")
    if not key:
        raise NoKey("TAVILY_API_KEY is not set")
    exe = binary()
    if exe is None:
        raise NoCli("tvly is not installed (uv tool install tavily-cli)")
    env = {k: os.environ[k] for k in PASS_ENV if os.environ.get(k)} | {"TAVILY_API_KEY": key}
    try:
        proc = subprocess.run([exe, *args, "--json"], capture_output=True, text=True, timeout=TIMEOUT, env=env)
    except (OSError, subprocess.SubprocessError) as e:
        raise TavilyError(f"tvly failed: {e}") from e
    if proc.returncode != 0:
        raise TavilyError((proc.stderr.strip() or proc.stdout.strip() or f"tvly exited {proc.returncode}")[:200])
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise TavilyError(f"tvly returned no JSON: {proc.stdout[:120]!r}") from e
    if not isinstance(data, dict):
        raise TavilyError("tvly returned an unexpected shape")
    return data


def ledger(out: Path, weekly_budget: float, signal: bool = False) -> Ledger:
    """This writer's ledger in the radar dir `out`, budgeted together with the other one."""
    own, other = (SIGNAL_LEDGER, LEDGER) if signal else (LEDGER, SIGNAL_LEDGER)
    return Ledger(out / own, weekly_budget, shared=(out / other,))


def search(query: str, ledger: Ledger, *, max_results: int = 10, time_range: str | None = None,
           include_domains: tuple[str, ...] = (), topic: str | None = None,
           now: datetime | None = None) -> list[dict[str, str]]:
    """One basic-depth search: [{url, title, content, host}]. Refused before the call when the
    week's spend plus its price would pass the budget; recorded after it."""
    now = now or datetime.now(UTC)
    usd = CREDITS["basic"] * USD_PER_CREDIT
    if ledger.spent_this_week(now) + usd > ledger.weekly_budget:
        raise OverBudget(f"Tavily weekly budget ${ledger.weekly_budget:.2f} reached")
    args = ["search", query, "--depth", "basic", "--max-results", str(max_results), "--client-name", CLIENT_NAME]
    if time_range:
        args += ["--time-range", time_range]
    if include_domains:
        args += ["--include-domains", ",".join(include_domains)]
    if topic:
        args += ["--topic", topic]
    data = _run(args)
    ledger.record({"at": now.isoformat(), "kind": "search", "query": query, "credits": CREDITS["basic"],
                   "usd": usd, "balance": None})
    rows = []
    for r in data.get("results") or []:
        url = str(r.get("url") or "")
        if url.startswith(("http://", "https://")):
            rows.append({"url": url, "title": str(r.get("title") or ""), "content": str(r.get("content") or ""),
                         "host": urlparse(url).hostname or ""})
    return rows
