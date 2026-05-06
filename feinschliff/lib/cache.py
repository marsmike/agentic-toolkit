"""Content-addressed cache for feinschliff binary artifacts."""
from __future__ import annotations

import os
from pathlib import Path


def _xdg_cache_home() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")


def cache_root() -> Path:
    """Root of the feinschliff cache (parent of all per-brand dirs)."""
    return _xdg_cache_home() / "feinschliff"


def cache_dir(brand: str, version: str) -> Path:
    """Per-brand-per-version cache root. Created on first call."""
    d = cache_root() / brand / version
    d.mkdir(parents=True, exist_ok=True)
    return d


def cache_path(brand: str, version: str, kind: str, sha256: str, ext: str) -> Path:
    """Content-addressed path for one cached artifact."""
    p = cache_dir(brand, version) / kind / f"{sha256}.{ext}"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p
