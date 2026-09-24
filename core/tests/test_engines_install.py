"""`toolkit engines install` against a fake release (review-01 SEC-2), with no network: the
release list and every download are served from memory."""

from __future__ import annotations

import hashlib
import io

import pytest
from toolkit_core import engines

BINARY = b"\x7fELF fake engine binary"
TRIPLE = "aarch64-apple-darwin"
FILENAME = f"farsight-{TRIPLE}"


def _release(*, checksum: bytes | None) -> dict:
    assets = [{"name": FILENAME, "browser_download_url": "https://example.invalid/bin"}]
    if checksum is not None:
        assets.append({"name": FILENAME + ".sha256", "browser_download_url": "https://example.invalid/sum"})
    return {"tag_name": "farsight-v0.1.2", "assets": assets}


@pytest.fixture
def fake_net(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    monkeypatch.setattr(engines, "target_triple", lambda *a, **k: TRIPLE)
    served: dict[str, bytes] = {"https://example.invalid/bin": BINARY}

    def urlopen(req, timeout=None):
        return io.BytesIO(served[req.full_url])

    monkeypatch.setattr(engines.urllib.request, "urlopen", urlopen)
    return served


def test_install_verifies_a_published_checksum(fake_net):
    fake_net["https://example.invalid/sum"] = f"{hashlib.sha256(BINARY).hexdigest()}  {FILENAME}\n".encode()
    result = engines.install_engine("farsight", [_release(checksum=b"")])
    assert result["ok"] and result["verified"] and "warning" not in result
    assert engines.binary_path("farsight").read_bytes() == BINARY
    assert engines.read_manifest()["farsight"]["verified"] is True


def test_checksum_mismatch_installs_nothing_and_keeps_the_old_binary(fake_net):
    dest = engines.binary_path("farsight")
    dest.parent.mkdir(parents=True)
    dest.write_bytes(b"the binary already installed")
    fake_net["https://example.invalid/sum"] = ("0" * 64 + f"  {FILENAME}\n").encode()
    result = engines.install_engine("farsight", [_release(checksum=b"")], force=True)
    assert not result["ok"] and "checksum mismatch" in result["error"]
    assert dest.read_bytes() == b"the binary already installed"
    assert not dest.with_name(dest.name + ".new").exists()
    assert "farsight" not in engines.read_manifest()


def test_unreadable_checksum_is_an_error_not_a_skip(fake_net):
    fake_net["https://example.invalid/sum"] = b"<html>not a digest</html>"
    result = engines.install_engine("farsight", [_release(checksum=b"")])
    assert not result["ok"] and "not a sha256 digest" in result["error"]
    assert not engines.binary_path("farsight").exists()


def test_release_without_checksum_installs_unverified_with_a_warning(fake_net):
    result = engines.install_engine("farsight", [_release(checksum=None)])
    assert result["ok"] and result["verified"] is False
    assert "installed unverified" in result["warning"]
    assert engines.read_manifest()["farsight"]["verified"] is False
