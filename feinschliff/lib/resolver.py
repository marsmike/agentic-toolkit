"""Resolver — fetch + verify + cache for catalog-referenced binaries."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from lib.cache import cache_path
from lib.fetcher import AuthSpec, Fetcher


class Resolver:
    def __init__(self, brand: str, version: str, catalog: dict[str, Any]):
        self.brand = brand
        self.version = version
        self.catalog = catalog
        default = catalog.get("asset_sources", {}).get("default", {})
        auth = default.get("auth")
        auth_spec = AuthSpec(type=auth["type"], env=auth["env"]) if auth else None
        self.fetcher = Fetcher(base_url=default.get("base_url"), auth=auth_spec)

    def fetch(self, source: str, sha256: str, kind: str, ext: str) -> Path:
        """Resolve source → cached local path. Verifies sha256 for non-file sources."""
        target = cache_path(self.brand, self.version, kind, sha256, ext)
        if target.exists():
            return target

        data = self.fetcher.fetch(source)

        if not source.startswith("file://"):
            actual = hashlib.sha256(data).hexdigest()
            if actual != sha256:
                raise ValueError(
                    f"hash mismatch for {source}: expected {sha256}, got {actual}"
                )

        target.write_bytes(data)
        return target

    def _find_in(self, kind: str, tags: list[str]) -> tuple[str, str] | None:
        items = self.catalog.get("assets", {}).get(kind, [])
        scored = []
        wanted = set(tags)
        for item in items:
            overlap = len(wanted & set(item.get("tags", [])))
            if overlap == 0:
                continue
            scored.append((-overlap, item["id"], item["source"], item["sha256"]))
        if not scored:
            return None
        scored.sort()
        _, _, source, sha = scored[0]
        return source, sha

    def find_icon(self, tags: list[str]) -> tuple[str, str] | None:
        return self._find_in("icons", tags)

    def find_image(self, tags: list[str]) -> tuple[str, str] | None:
        return self._find_in("images", tags)
