#!/usr/bin/env python3
"""Fetch a stub capture's own source through the Tavily CLI — distill's "A stub is not the content".

    fetch_source.py 01_Capture/<capture>.md [--json]

Reads the URL from the capture's frontmatter (`source`) — never one given on the command line, so
neither a capture's text nor an agent can point it anywhere else — and asks `tvly extract` for the
page as Markdown. Prints the page (or with --json: {ok, url, title, content, via}); exit 1 with a
reason when the capture has no http(s) source, the host is not allowed, or nothing came back.

The one way the obsidian plugin talks to Tavily is the `tvly` CLI, as everywhere in the toolkit.
The key is read by this script (`secret`: the environment, then the key file) and handed to `tvly`
alone; the unattended run's agent holds none. Without a key `tvly` still extracts, under Tavily's
keyless rate cap.

Hosts: when TOOLKIT_PIPELINE_FETCH_DOMAINS is set (the local unattended run sets it, default
`github.com raw.githubusercontent.com`), only those domains and their subdomains; unset (an
interactive session, the cloud routine), any http(s) host. Tavily fetches the page on its own
servers, so nothing on the local network is reachable through it.
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
from pathlib import Path
from urllib.parse import urlparse

from vault_utils import read_frontmatter, require_vault, secret, vault_file

TIMEOUT = 90
CLIENT_NAME = "agentic-toolkit-distill"
PASS_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "SSL_CERT_FILE", "SSL_CERT_DIR", "REQUESTS_CA_BUNDLE",
            "HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "https_proxy", "http_proxy", "no_proxy")


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


def extract(url: str) -> dict:
    """The one call out to `tvly` here. Evals replace it with a stub."""
    exe = tvly_binary()
    if exe is None:
        raise RuntimeError("tvly is not installed (uv tool install tavily-cli)")
    env = {k: os.environ[k] for k in PASS_ENV if os.environ.get(k)}
    key = secret("TAVILY_API_KEY")
    if key:
        env["TAVILY_API_KEY"] = key
    proc = subprocess.run([exe, "extract", url, "--format", "markdown", "--client-name", CLIENT_NAME, "--json"],
                          capture_output=True, text=True, timeout=TIMEOUT, env=env)
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr.strip() or proc.stdout.strip() or f"tvly exited {proc.returncode}")[:200])
    return json.loads(proc.stdout)


def fetch(vault: Path, capture_arg: str) -> dict:
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
        data = extract(url)
    except (OSError, subprocess.SubprocessError, RuntimeError, json.JSONDecodeError) as e:
        return {"ok": False, "url": url, "reason": f"tvly extract failed: {str(e)[:200]}"}
    results = [r for r in data.get("results") or [] if str(r.get("raw_content") or "").strip()]
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
