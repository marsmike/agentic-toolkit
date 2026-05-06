import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from lib.resolver import Resolver


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def test_resolver_fetches_file_source_and_caches(tmp_cache_root, tmp_path, sample_v2_catalog):
    binary = b"PPTX-bytes"
    src = tmp_path / "demo.pptx"
    src.write_bytes(binary)
    sample_v2_catalog["layouts"][0]["renderer"]["pptx"]["source"] = f"file://{src}"
    sample_v2_catalog["layouts"][0]["renderer"]["pptx"]["sha256"] = _sha256(binary)

    r = Resolver(brand="test", version="1.0.0", catalog=sample_v2_catalog)
    p = r.fetch(source=f"file://{src}", sha256=_sha256(binary), kind="templates/pptx", ext="pptx")
    assert p.read_bytes() == binary
    p2 = r.fetch(source=f"file://{src}", sha256=_sha256(binary), kind="templates/pptx", ext="pptx")
    assert p2 == p


def test_resolver_hash_mismatch_raises_for_https(tmp_cache_root, sample_v2_catalog):
    r = Resolver(brand="test", version="1.0.0", catalog=sample_v2_catalog)
    wrong_sha = "f" * 64
    with patch("lib.fetcher.urlopen") as mock_open:
        mock_open.return_value.__enter__.return_value.read.return_value = b"actual content"
        with pytest.raises(ValueError, match="hash mismatch"):
            r.fetch(source="https://example.test/x.bin", sha256=wrong_sha, kind="templates/pptx", ext="pptx")


def test_resolver_skips_hash_check_for_file_sources(tmp_cache_root, tmp_path, sample_v2_catalog):
    src = tmp_path / "x.bin"
    src.write_bytes(b"some bytes")
    r = Resolver(brand="test", version="1.0.0", catalog=sample_v2_catalog)
    bogus_sha = "0" * 64
    p = r.fetch(source=f"file://{src}", sha256=bogus_sha, kind="x", ext="bin")
    assert p.read_bytes() == b"some bytes"


def test_find_icon_returns_top_tag_overlap_match(tmp_cache_root, sample_v2_catalog):
    sample_v2_catalog["assets"]["icons"] = [
        {"id": "leaf", "tags": ["sustainability", "green"], "source": "icons/leaf.svg", "sha256": "1" * 64},
        {"id": "factory", "tags": ["factory", "industry"], "source": "icons/factory.svg", "sha256": "2" * 64},
        {"id": "plant", "tags": ["sustainability", "factory"], "source": "icons/plant.svg", "sha256": "3" * 64},
    ]
    r = Resolver(brand="test", version="1.0.0", catalog=sample_v2_catalog)
    src, sha = r.find_icon(["sustainability", "factory"])
    assert src == "icons/plant.svg"  # 2 overlaps wins
    assert sha == "3" * 64


def test_find_icon_deterministic_tiebreak_by_id(tmp_cache_root, sample_v2_catalog):
    sample_v2_catalog["assets"]["icons"] = [
        {"id": "zebra", "tags": ["x"], "source": "icons/zebra.svg", "sha256": "1" * 64},
        {"id": "apple", "tags": ["x"], "source": "icons/apple.svg", "sha256": "2" * 64},
    ]
    r = Resolver(brand="test", version="1.0.0", catalog=sample_v2_catalog)
    src, sha = r.find_icon(["x"])
    assert src == "icons/apple.svg"


def test_find_icon_returns_none_when_no_overlap(tmp_cache_root, sample_v2_catalog):
    sample_v2_catalog["assets"]["icons"] = [
        {"id": "leaf", "tags": ["green"], "source": "icons/leaf.svg", "sha256": "1" * 64},
    ]
    r = Resolver(brand="test", version="1.0.0", catalog=sample_v2_catalog)
    assert r.find_icon(["unrelated"]) is None
