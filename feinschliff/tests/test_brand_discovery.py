import json
from pathlib import Path

from lib.brand_discovery import discover_brands, Brand


def _write_brand(root: Path, name: str) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "catalog.json").write_text(json.dumps({"brand": name, "layouts": []}))
    return d


def test_discover_brands_finds_bundled(tmp_path, monkeypatch):
    bundled = tmp_path / "bundled" / "brands"
    _write_brand(bundled, "alpha")
    _write_brand(bundled, "beta")
    monkeypatch.setenv("FEINSCHLIFF_BRAND_PATH", "")
    monkeypatch.setattr("lib.brand_discovery._bundled_brands_root", lambda: bundled)
    monkeypatch.setattr("lib.brand_discovery._user_brands_root", lambda: tmp_path / "no-such")
    monkeypatch.setattr("lib.brand_discovery._plugin_brands_roots", lambda: [])

    brands = discover_brands()
    names = sorted(b.name for b in brands)
    assert names == ["alpha", "beta"]


def test_discover_brands_finds_env_path(tmp_path, monkeypatch):
    extra = tmp_path / "extra"
    _write_brand(extra, "gamma")
    monkeypatch.setenv("FEINSCHLIFF_BRAND_PATH", str(extra))
    monkeypatch.setattr("lib.brand_discovery._bundled_brands_root", lambda: tmp_path / "no-bundled")
    monkeypatch.setattr("lib.brand_discovery._user_brands_root", lambda: tmp_path / "no-user")
    monkeypatch.setattr("lib.brand_discovery._plugin_brands_roots", lambda: [])

    brands = discover_brands()
    assert any(b.name == "gamma" for b in brands)


def test_brand_dataclass_carries_path_and_catalog_path(tmp_path, monkeypatch):
    bundled = tmp_path / "bundled" / "brands"
    d = _write_brand(bundled, "delta")
    monkeypatch.setenv("FEINSCHLIFF_BRAND_PATH", "")
    monkeypatch.setattr("lib.brand_discovery._bundled_brands_root", lambda: bundled)
    monkeypatch.setattr("lib.brand_discovery._user_brands_root", lambda: tmp_path / "no-user")
    monkeypatch.setattr("lib.brand_discovery._plugin_brands_roots", lambda: [])

    [delta] = [b for b in discover_brands() if b.name == "delta"]
    assert delta.root == d
    assert delta.catalog_path == d / "catalog.json"


def test_plugin_brands_roots_walks_marketplace_layout(tmp_path, monkeypatch):
    """Marketplace-installed plugins live under ~/.claude/plugins/marketplaces/{m}/{plugin}/brands."""
    fake_home = tmp_path / "home"
    plugins = fake_home / ".claude" / "plugins"
    bsh = plugins / "marketplaces" / "bsh-team" / "feinschliff-bsh" / "brands"
    bsh.mkdir(parents=True)
    oss = plugins / "marketplaces" / "agentic-toolkit" / "feinschliff" / "brands"
    oss.mkdir(parents=True)

    monkeypatch.setenv("HOME", str(fake_home))

    from lib.brand_discovery import _plugin_brands_roots
    roots = _plugin_brands_roots()
    assert bsh in roots
    assert oss in roots


def test_plugin_brands_roots_includes_sideload_layout(tmp_path, monkeypatch):
    """Sideloaded plugins live directly under ~/.claude/plugins/{plugin}/brands."""
    fake_home = tmp_path / "home"
    plugins = fake_home / ".claude" / "plugins"
    sideload = plugins / "legacy-plugin" / "brands"
    sideload.mkdir(parents=True)

    monkeypatch.setenv("HOME", str(fake_home))

    from lib.brand_discovery import _plugin_brands_roots
    roots = _plugin_brands_roots()
    assert sideload in roots


def test_discover_brands_finds_v1_legacy_catalog_path(tmp_path, monkeypatch):
    """Transitional: brand keeps its catalog at brand/catalog/layouts.json (v1 layout)
    rather than brand/catalog.json (v2). Discovery accepts both during migration."""
    bundled = tmp_path / "bundled" / "brands"
    legacy_brand = bundled / "legacy"
    (legacy_brand / "catalog").mkdir(parents=True)
    (legacy_brand / "catalog" / "layouts.json").write_text(
        json.dumps({"brand": "legacy", "layouts": []})
    )

    monkeypatch.setenv("FEINSCHLIFF_BRAND_PATH", "")
    monkeypatch.setattr("lib.brand_discovery._bundled_brands_root", lambda: bundled)
    monkeypatch.setattr("lib.brand_discovery._user_brands_root", lambda: tmp_path / "no-user")
    monkeypatch.setattr("lib.brand_discovery._plugin_brands_roots", lambda: [])

    [b] = [b for b in discover_brands() if b.name == "legacy"]
    assert b.catalog_path == legacy_brand / "catalog" / "layouts.json"


def test_discover_brands_prefers_v2_catalog_over_legacy(tmp_path, monkeypatch):
    """When both catalog.json and catalog/layouts.json exist, v2 wins."""
    bundled = tmp_path / "bundled" / "brands"
    brand_dir = bundled / "dual"
    brand_dir.mkdir(parents=True)
    (brand_dir / "catalog.json").write_text(json.dumps({"brand": "dual", "layouts": []}))
    (brand_dir / "catalog").mkdir()
    (brand_dir / "catalog" / "layouts.json").write_text(
        json.dumps({"brand": "dual", "layouts": []})
    )

    monkeypatch.setenv("FEINSCHLIFF_BRAND_PATH", "")
    monkeypatch.setattr("lib.brand_discovery._bundled_brands_root", lambda: bundled)
    monkeypatch.setattr("lib.brand_discovery._user_brands_root", lambda: tmp_path / "no-user")
    monkeypatch.setattr("lib.brand_discovery._plugin_brands_roots", lambda: [])

    [b] = [b for b in discover_brands() if b.name == "dual"]
    assert b.catalog_path == brand_dir / "catalog.json"
