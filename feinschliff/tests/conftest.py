import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def tmp_cache_root(tmp_path, monkeypatch):
    """Isolated cache directory for tests; sets XDG_CACHE_HOME."""
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    return cache


@pytest.fixture
def sample_v2_catalog():
    """Minimal catalog with one v2 template entry."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "schema_version": "1.0",
        "brand": "test",
        "version": "1.0.0",
        "asset_sources": {
            "default": {"base_url": "https://example.test/", "auth": None}
        },
        "layouts": [
            {
                "id": "demo",
                "slots": {"title": {"type": "string"}},
                "renderer": {
                    "pptx": {
                        "source": "templates/pptx/demo.pptx",
                        "sha256": "0" * 64,
                        "placeholder_map": {"title": 0},
                    }
                },
            }
        ],
        "assets": {"icons": [], "illustrations": [], "images": []},
    }
