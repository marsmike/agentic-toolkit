"""Fetch bytes by URL. Supports file:// and https:// with optional query-token auth and HTTPS_PROXY."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


@dataclass
class AuthSpec:
    type: str   # "query_token" is the only one for v1
    env: str    # name of env var holding the token


class Fetcher:
    def __init__(self, base_url: str | None = None, auth: AuthSpec | None = None):
        self.base_url = base_url
        self.auth = auth

    def _resolve(self, source: str) -> str:
        if source.startswith("file://") or source.startswith("https://") or source.startswith("http://"):
            return source
        if not self.base_url:
            raise ValueError(f"relative source {source!r} but no base_url configured")
        return urljoin(self.base_url, source)

    def _apply_auth(self, url: str) -> str:
        if self.auth is None:
            return url
        if self.auth.type != "query_token":
            raise ValueError(f"unsupported auth type {self.auth.type!r}")
        token = os.environ.get(self.auth.env)
        if not token:
            raise RuntimeError(
                f"auth required but env var {self.auth.env} is not set"
            )
        # bare query-string token: "?TOKEN" with no key=
        sep = "&" if urlparse(url).query else "?"
        return url + sep + token

    def fetch(self, source: str) -> bytes:
        url = self._resolve(source)
        if url.startswith("file://"):
            return Path(url[len("file://"):]).read_bytes()
        url = self._apply_auth(url)
        req = Request(url)
        with urlopen(req) as resp:
            return resp.read()
