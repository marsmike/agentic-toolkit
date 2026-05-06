import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from cli.main import main


def _write_brand(root: Path, name: str, payload: dict) -> Path:
    d = root / name
    d.mkdir(parents=True, exist_ok=True)
    (d / "catalog.json").write_text(json.dumps(payload))
    return d


@pytest.fixture
def isolated_brands(tmp_path, monkeypatch):
    bundled = tmp_path / "bundled" / "brands"
    bundled.mkdir(parents=True)
    monkeypatch.setattr("lib.brand_discovery._bundled_brands_root", lambda: bundled)
    monkeypatch.setattr("lib.brand_discovery._user_brands_root", lambda: tmp_path / "no-user")
    monkeypatch.setattr("lib.brand_discovery._plugin_brands_roots", lambda: [])
    monkeypatch.setenv("FEINSCHLIFF_BRAND_PATH", "")
    return bundled


def test_brand_list_prints_discovered_brands(isolated_brands, capsys):
    _write_brand(isolated_brands, "alpha", {"brand": "alpha", "layouts": []})
    _write_brand(isolated_brands, "beta", {"brand": "beta", "layouts": []})
    rc = main(["brand", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha" in out
    assert "beta" in out


def test_brand_inspect_prints_summary(isolated_brands, capsys):
    _write_brand(isolated_brands, "alpha", {
        "brand": "alpha",
        "version": "1.0.0",
        "layouts": [
            {"id": "x", "renderer": {"pptx": {"source": "x.pptx", "sha256": "0" * 64, "placeholder_map": {}}}},
            {"id": "y", "renderer": {"pptx": {"module": "old"}}},
        ],
        "assets": {"icons": [
            {"id": "i1", "source": "i1.svg", "sha256": "a" * 64},
            {"id": "i2", "source": "i2.svg", "sha256": "b" * 64},
        ], "illustrations": [], "images": []},
    })
    rc = main(["brand", "inspect", "alpha"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha" in out
    assert "layouts: 2" in out
    assert "v2: 1" in out
    assert "v1: 1" in out
    assert "icons: 2" in out


def test_brand_inspect_unknown_brand_returns_nonzero(isolated_brands, capsys):
    rc = main(["brand", "inspect", "nope"])
    assert rc != 0


def test_brand_sync_fetches_v2_templates(isolated_brands, tmp_cache_root, tmp_path, capsys):
    src_pptx = tmp_path / "demo.pptx"
    src_pptx.write_bytes(b"PPTX")
    import hashlib
    sha = hashlib.sha256(b"PPTX").hexdigest()
    _write_brand(isolated_brands, "alpha", {
        "brand": "alpha",
        "version": "1.0.0",
        "layouts": [
            {"id": "x", "renderer": {"pptx": {
                "source": f"file://{src_pptx}",
                "sha256": sha,
                "placeholder_map": {},
            }}},
        ],
        "assets": {"icons": [], "illustrations": [], "images": []},
    })
    rc = main(["brand", "sync", "alpha"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1/1" in out


def test_brand_sync_skips_images_by_default(isolated_brands, tmp_cache_root, tmp_path, capsys):
    src_pptx = tmp_path / "x.pptx"
    src_pptx.write_bytes(b"X")
    src_jpg = tmp_path / "img.jpg"
    src_jpg.write_bytes(b"IMG")
    import hashlib
    _write_brand(isolated_brands, "alpha", {
        "brand": "alpha",
        "version": "1.0.0",
        "layouts": [
            {"id": "x", "renderer": {"pptx": {
                "source": f"file://{src_pptx}",
                "sha256": hashlib.sha256(b"X").hexdigest(),
                "placeholder_map": {},
            }}},
        ],
        "assets": {
            "icons": [],
            "illustrations": [],
            "images": [{
                "id": "i1", "tags": [],
                "source": f"file://{src_jpg}",
                "sha256": hashlib.sha256(b"IMG").hexdigest(),
            }],
        },
    })
    rc = main(["brand", "sync", "alpha"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "skipping images" in out


def test_brand_sync_with_images_fetches_them(isolated_brands, tmp_cache_root, tmp_path, capsys):
    src_jpg = tmp_path / "img.jpg"
    src_jpg.write_bytes(b"IMG")
    import hashlib
    _write_brand(isolated_brands, "alpha", {
        "brand": "alpha",
        "version": "1.0.0",
        "layouts": [],
        "assets": {
            "icons": [],
            "illustrations": [],
            "images": [{
                "id": "i1", "tags": [],
                "source": f"file://{src_jpg}",
                "sha256": hashlib.sha256(b"IMG").hexdigest(),
            }],
        },
    })
    rc = main(["brand", "sync", "alpha", "--with-images"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "1/1" in out


def test_brand_bundle_creates_two_namespace_archive(isolated_brands, tmp_cache_root, tmp_path):
    """Bundle packs both the brand directory and the cache, in two top-level namespaces."""
    import hashlib
    import tarfile
    src_pptx = tmp_path / "x.pptx"
    src_pptx.write_bytes(b"X")
    _write_brand(isolated_brands, "alpha", {
        "brand": "alpha",
        "version": "1.0.0",
        "layouts": [
            {"id": "x", "renderer": {"pptx": {
                "source": f"file://{src_pptx}",
                "sha256": hashlib.sha256(b"X").hexdigest(),
                "placeholder_map": {},
            }}},
        ],
        "assets": {"icons": [], "illustrations": [], "images": []},
    })
    main(["brand", "sync", "alpha"])  # populate cache
    out_archive = tmp_path / "alpha.tar.gz"
    rc = main(["brand", "bundle", "alpha", "-o", str(out_archive)])
    assert rc == 0
    assert out_archive.is_file()

    with tarfile.open(out_archive) as tf:
        names = tf.getnames()
    assert any(n.endswith("brand/alpha/catalog.json") or n == "brand/alpha/catalog.json" for n in names), \
        f"missing brand/alpha/catalog.json in {names}"
    assert any(n.startswith("cache/alpha/1.0.0/") for n in names), \
        f"missing cache/alpha/1.0.0/ in {names}"


def test_brand_install_restores_brand_dir_and_cache(tmp_cache_root, tmp_path, monkeypatch):
    """Install on a fresh target rebuilds the brand directory under ~/.feinschliff/brands/ and the cache."""
    import hashlib
    import json
    import tarfile

    sha = hashlib.sha256(b"X").hexdigest()
    bundle_dir = tmp_path / "bundle"
    (bundle_dir / "brand" / "alpha" / "templates" / "pptx").mkdir(parents=True)
    (bundle_dir / "brand" / "alpha" / "catalog.json").write_text(json.dumps({
        "brand": "alpha", "version": "1.0.0",
        "layouts": [{"id": "x", "renderer": {"pptx": {
            "source": "templates/pptx/x.pptx",
            "sha256": sha,
            "placeholder_map": {},
        }}}],
        "assets": {"icons": [], "illustrations": [], "images": []},
    }))
    (bundle_dir / "brand" / "alpha" / "templates" / "pptx" / "x.pptx").write_bytes(b"X")
    (bundle_dir / "cache" / "alpha" / "1.0.0" / "templates" / "pptx").mkdir(parents=True)
    (bundle_dir / "cache" / "alpha" / "1.0.0" / "templates" / "pptx" / f"{sha}.pptx").write_bytes(b"X")

    archive = tmp_path / "alpha.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(bundle_dir, arcname=".")

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    rc = main(["brand", "install", str(archive)])
    assert rc == 0

    assert (fake_home / ".feinschliff" / "brands" / "alpha" / "catalog.json").is_file()
    assert (fake_home / ".feinschliff" / "brands" / "alpha" / "templates" / "pptx" / "x.pptx").is_file()
    cached = tmp_cache_root / "feinschliff" / "alpha" / "1.0.0" / "templates" / "pptx" / f"{sha}.pptx"
    assert cached.is_file()


def test_brand_install_rejects_hash_mismatch(tmp_cache_root, tmp_path, monkeypatch):
    """A tampered cache file with a mismatching content-addressed name causes install to fail."""
    import hashlib
    import json
    import tarfile

    sha = hashlib.sha256(b"X").hexdigest()  # advertised
    bundle_dir = tmp_path / "bundle"
    (bundle_dir / "brand" / "alpha").mkdir(parents=True)
    (bundle_dir / "brand" / "alpha" / "catalog.json").write_text(json.dumps({
        "brand": "alpha", "version": "1.0.0", "layouts": [],
        "assets": {"icons": [], "illustrations": [], "images": []},
    }))
    (bundle_dir / "cache" / "alpha" / "1.0.0" / "templates" / "pptx").mkdir(parents=True)
    # Filename advertises sha for b"X", actual content is b"Y" — mismatch.
    (bundle_dir / "cache" / "alpha" / "1.0.0" / "templates" / "pptx" / f"{sha}.pptx").write_bytes(b"Y")

    archive = tmp_path / "alpha.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        tf.add(bundle_dir, arcname=".")

    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))

    rc = main(["brand", "install", str(archive)])
    assert rc != 0
