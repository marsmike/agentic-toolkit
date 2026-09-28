"""Profile resolution: env var -> vault note frontmatter -> caller default.

Per contract/PROFILE.md, a plugin's configuration resolves in this order:

1. `TOOLKIT_<PLUGIN>_<KEY>` environment variable.
2. `$VAULT/Config/toolkit/<plugin>.md` frontmatter.
3. The caller-supplied default.

A missing profile note is a normal condition, not an error — plugins run fine with no
profile configured, falling through to their shipped defaults.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import yaml

from toolkit_core.vault import parse_frontmatter


def profile_note_path(vault_path: Path, plugin: str) -> Path:
    return Path(vault_path) / "Config" / "toolkit" / f"{plugin}.md"


def read_profile_note(vault_path: Path, plugin: str) -> dict:
    """Return a plugin's profile frontmatter, or {} if no such note exists."""
    path = profile_note_path(vault_path, plugin)
    if not path.is_file():
        return {}
    frontmatter, _, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
    return frontmatter


def _env_prefix(plugin: str) -> str:
    return f"TOOLKIT_{plugin.upper()}_"


def _coerce_scalar(value: str):
    """Parse an env var string the same way its value would be typed had it come from
    frontmatter YAML instead — `"0.99"` -> `0.99`, `"true"` -> `True`, `"5"` -> `5` — so a caller
    reading `search_score_gate` gets a `float` whether it came from `Config/toolkit/<plugin>.md`
    or `TOOLKIT_<PLUGIN>_SEARCH_SCORE_GATE`, never a `float` from one source and a `str` from the
    other for what's meant to be the same value. Falls back to the raw string, tolerantly, on
    anything `yaml.safe_load` can't parse as a plain scalar (or that parses to a list/dict — an
    env var overriding a single config key should never turn it into a collection).
    [battle-test 2026-09-28: `unisphere profile obsidian --json` returned a `float` for
    `search_score_gate` from the note and a `str` for the same key set via env var]"""
    try:
        parsed = yaml.safe_load(value)
    except yaml.YAMLError:
        return value
    return value if isinstance(parsed, (list, dict)) else parsed


def env_overrides(plugin: str) -> dict:
    """All `TOOLKIT_<PLUGIN>_<KEY>` env vars currently set, keyed by lowercased <KEY>, with each
    value parsed as a YAML scalar so it matches the type a profile note's frontmatter would give
    the same value (see `_coerce_scalar`)."""
    prefix = _env_prefix(plugin)
    return {
        name[len(prefix) :].lower(): _coerce_scalar(value)
        for name, value in os.environ.items()
        if name.startswith(prefix)
    }


def resolve_profile(vault_path: Path, plugin: str) -> dict:
    """The full merged profile for a plugin: note frontmatter, with env vars overriding."""
    merged = dict(read_profile_note(vault_path, plugin))
    merged.update(env_overrides(plugin))
    return merged


def get(vault_path: Path, plugin: str, key: str, default=None):
    """Resolve one profile value: env var -> note field -> default."""
    env_name = f"{_env_prefix(plugin)}{key.upper()}"
    if env_name in os.environ:
        return _coerce_scalar(os.environ[env_name])
    note = read_profile_note(vault_path, plugin)
    if key in note:
        return note[key]
    return default


def known_plugins(repo_root: Path | None) -> list[str]:
    """Plugin names declared in the repo's `.claude-plugin/marketplace.json`, or []."""
    if repo_root is None:
        return []
    marketplace_path = Path(repo_root) / ".claude-plugin" / "marketplace.json"
    if not marketplace_path.is_file():
        return []
    try:
        data = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [entry["name"] for entry in data.get("plugins", []) if "name" in entry]
