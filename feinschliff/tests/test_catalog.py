import json
from pathlib import Path

import pytest

from lib.catalog import load_catalog, get_renderer_kind, RendererKind, V2RendererSpec


def test_load_catalog_returns_dict(sample_v2_catalog, tmp_path):
    p = tmp_path / "catalog.json"
    p.write_text(json.dumps(sample_v2_catalog))
    cat = load_catalog(p)
    assert cat["brand"] == "test"
    assert len(cat["layouts"]) == 1


def test_load_catalog_validates_against_schema(sample_v2_catalog, tmp_path):
    sample_v2_catalog["layouts"][0]["renderer"]["pptx"]["sha256"] = "not-a-hash"
    p = tmp_path / "catalog.json"
    p.write_text(json.dumps(sample_v2_catalog))
    with pytest.raises(ValueError, match="schema"):
        load_catalog(p)


def test_get_renderer_kind_v2_when_source_present(sample_v2_catalog):
    entry = sample_v2_catalog["layouts"][0]
    assert get_renderer_kind(entry, "pptx") is RendererKind.V2


def test_get_renderer_kind_v1_when_module_present():
    entry = {
        "id": "demo",
        "renderer": {"pptx": {"module": "feinschliff.brands.x.renderers.pptx.layouts.demo"}},
    }
    assert get_renderer_kind(entry, "pptx") is RendererKind.V1


def test_get_renderer_kind_none_when_renderer_missing():
    entry = {"id": "demo", "renderer": {}}
    assert get_renderer_kind(entry, "pptx") is RendererKind.NONE


def test_v2_renderer_spec_parses(sample_v2_catalog):
    entry = sample_v2_catalog["layouts"][0]
    spec = V2RendererSpec.from_entry(entry, "pptx")
    assert spec.source == "templates/pptx/demo.pptx"
    assert spec.sha256 == "0" * 64
    assert spec.placeholder_map == {"title": 0}


def test_load_catalog_raises_on_missing_required_keys(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"layouts": []}')
    with pytest.raises(ValueError, match="brand"):
        load_catalog(bad)
