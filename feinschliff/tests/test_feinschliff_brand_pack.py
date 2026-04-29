"""Smoke test for the feinschliff brand pack — minimal coverage for OSS launch."""
import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PACK_ROOT = REPO_ROOT / "feinschliff" / "brands" / "feinschliff"
PPTX_RENDERER = PACK_ROOT / "renderers" / "pptx"


def test_feinschliff_tokens_file_exists_and_is_valid_json():
    tokens_path = PACK_ROOT / "tokens.json"
    assert tokens_path.is_file()
    with tokens_path.open() as f:
        tokens = json.load(f)
    for required_key in ("color", "font-family", "font-weight", "font-size", "slide"):
        assert required_key in tokens


def test_feinschliff_tokens_have_required_color_roles():
    tokens_path = PACK_ROOT / "tokens.json"
    with tokens_path.open() as f:
        tokens = json.load(f)
    color_block = tokens["color"]
    for required_color in ("accent", "accent-hover", "highlight", "ink", "graphite", "paper", "white"):
        assert required_color in color_block


def test_feinschliff_pptx_build_succeeds():
    result = subprocess.run(
        ["uv", "run", "python", "build.py"],
        cwd=PPTX_RENDERER,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"build failed:\n{result.stdout}\n{result.stderr}"
    output = PPTX_RENDERER / "out" / "Feinschliff-Template.pptx"
    assert output.is_file()
    assert output.stat().st_size > 100_000


def test_feinschliff_catalog_brand_field():
    catalog_path = PACK_ROOT / "catalog" / "layouts.json"
    with catalog_path.open() as f:
        catalog = json.load(f)
    assert catalog.get("brand") == "feinschliff", \
        f"catalog brand must be 'feinschliff', got {catalog.get('brand')!r}"
