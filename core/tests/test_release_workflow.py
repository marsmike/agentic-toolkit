"""Execute release tag validation and packaging with local fixtures only."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def release_steps():
    return yaml.safe_load((ROOT / ".github/workflows/release-binaries.yml").read_text())["jobs"]["build"]["steps"]


@pytest.mark.parametrize("tag,expected", [
    ("farsight-v0.1.2", "farsight"),
    ("gaiafield-v0.2.0", "gaiafield"),
    ("farsight;touch${IFS}owned-v0.1.2", None),
    ("$(touch${IFS}owned)-v0.1.2", None),
    ("-v0.1.2", None),
])
def test_release_rejects_shell_syntax_in_crate_name(tmp_path, tag, expected):
    derive = next(step for step in release_steps() if step.get("id") == "crate")
    output = tmp_path / "output"
    result = subprocess.run(
        ["bash", "-eu", "-c", derive["run"]], cwd=tmp_path,
        env={"PATH": os.environ["PATH"], "GITHUB_REF_NAME": tag, "GITHUB_OUTPUT": str(output)},
        capture_output=True, text=True, timeout=5,
    )
    if expected is None:
        assert result.returncode != 0
        assert not output.exists() or not output.read_text()
    else:
        assert result.returncode == 0, result.stderr
        assert output.read_text() == f"name={expected}\n"
    assert not (tmp_path / "owned").exists()


def test_tag_output_is_passed_as_environment_data():
    steps = release_steps()
    for name in ("Build", "Package binary"):
        step = next(step for step in steps if step.get("name") == name)
        assert "${{ steps.crate.outputs.name }}" not in step["run"]
        assert "${{ steps.crate.outputs.name }}" in step["env"].values()


@pytest.mark.parametrize("target_os,target", [
    ("macos-latest", "aarch64-apple-darwin"),
    ("ubuntu-latest", "x86_64-unknown-linux-musl"),
    ("windows-latest", "x86_64-pc-windows-msvc"),
])
def test_package_publishes_matching_checksum_sidecar(tmp_path, target_os, target):
    import hashlib

    package = next(step for step in release_steps() if step.get("name") == "Package binary")
    extension = ".exe" if target_os == "windows-latest" else ""
    binary = tmp_path / "target" / target / "release" / f"farsight{extension}"
    binary.parent.mkdir(parents=True)
    payload = b"local binary fixture\x00\xff\n"
    binary.write_bytes(payload)
    result = subprocess.run(
        ["bash", "-eu", "-c", package["run"]], cwd=tmp_path,
        env={"PATH": os.environ["PATH"], "CRATE_NAME": "farsight", "TARGET": target, "TARGET_OS": target_os},
        capture_output=True, text=True, timeout=5,
    )
    assert result.returncode == 0, result.stderr
    asset_name = f"farsight-{target}{extension}"
    assert (tmp_path / "dist" / asset_name).read_bytes() == payload
    sidecar = tmp_path / "dist" / f"{asset_name}.sha256"
    assert sidecar.read_text() == f"{hashlib.sha256(payload).hexdigest()}  {asset_name}\n"
    attach = next(step for step in release_steps() if step.get("name") == "Attach to release")
    assert sidecar in list(tmp_path.glob(attach["with"]["files"]))
