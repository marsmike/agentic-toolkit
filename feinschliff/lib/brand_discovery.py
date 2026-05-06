"""Locate brand packs across bundled, plugin-installed, env, and user-local paths."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Brand:
    name: str
    root: Path
    catalog_path: Path


def _bundled_brands_root() -> Path:
    """The brands/ directory shipped inside this plugin."""
    return Path(__file__).resolve().parents[1] / "brands"


def _user_brands_root() -> Path:
    return Path.home() / ".feinschliff" / "brands"


def _plugin_brands_roots() -> list[Path]:
    """`brands/` dirs from installed Claude Code plugins.

    Modern plugins land under ``~/.claude/plugins/marketplaces/{marketplace}/{plugin}/``;
    sideloaded plugins occasionally land directly under ``~/.claude/plugins/{plugin}/``.
    Both layouts are supported.
    """
    plugins = Path.home() / ".claude" / "plugins"
    if not plugins.is_dir():
        return []
    roots: list[Path] = []
    marketplaces = plugins / "marketplaces"
    if marketplaces.is_dir():
        for marketplace in sorted(marketplaces.iterdir()):
            if not marketplace.is_dir():
                continue
            for plugin in sorted(marketplace.iterdir()):
                brands = plugin / "brands"
                if brands.is_dir():
                    roots.append(brands)
    for entry in sorted(plugins.iterdir()):
        if entry.name == "marketplaces" or not entry.is_dir():
            continue
        brands = entry / "brands"
        if brands.is_dir():
            roots.append(brands)
    return roots


def _env_brands_roots() -> list[Path]:
    raw = os.environ.get("FEINSCHLIFF_BRAND_PATH", "")
    return [Path(p) for p in raw.split(os.pathsep) if p]


def discover_brands() -> list[Brand]:
    """Returns all brands found across all discovery sources, deduped by name (first wins)."""
    seen: dict[str, Brand] = {}
    for root in [
        _bundled_brands_root(),
        *_plugin_brands_roots(),
        *_env_brands_roots(),
        _user_brands_root(),
    ]:
        if not root.is_dir():
            continue
        for d in sorted(root.iterdir()):
            cat = d / "catalog.json"
            if not (d.is_dir() and cat.is_file()):
                continue
            if d.name in seen:
                continue
            seen[d.name] = Brand(name=d.name, root=d, catalog_path=cat)
    return list(seen.values())
