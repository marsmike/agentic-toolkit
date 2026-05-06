import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, RefResolver
from jsonschema.exceptions import ValidationError

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "lib" / "schemas"
CATALOG_SCHEMA = SCHEMA_DIR / "catalog-v2.schema.json"
ASSET_SCHEMA = SCHEMA_DIR / "asset-entry.schema.json"


def _validator():
    schema = json.loads(CATALOG_SCHEMA.read_text())
    asset = json.loads(ASSET_SCHEMA.read_text())
    store = {schema["$id"]: schema, asset["$id"]: asset, "asset-entry.schema.json": asset}
    resolver = RefResolver(base_uri=schema["$id"], referrer=schema, store=store)
    return Draft202012Validator(schema, resolver=resolver)


def test_schemas_are_valid_draft_2020_12():
    Draft202012Validator.check_schema(json.loads(CATALOG_SCHEMA.read_text()))
    Draft202012Validator.check_schema(json.loads(ASSET_SCHEMA.read_text()))


def test_minimal_v2_catalog_validates(sample_v2_catalog):
    _validator().validate(sample_v2_catalog)


def test_legacy_v1_module_form_now_rejected():
    """v1 'module' form was supported during the migration; PR-2 dropped it.
    A renderer entry with only a 'module' field no longer validates."""
    cat = {
        "brand": "x",
        "layouts": [
            {"id": "old", "renderer": {"pptx": {"module": "x.y.z", "placeholder_map": {"title": 0}}}}
        ],
    }
    with pytest.raises(ValidationError):
        _validator().validate(cat)


def test_renderer_extra_fields_rejected():
    """rendererSpec is now strict: only source + sha256 + placeholder_map allowed."""
    cat = {
        "brand": "x",
        "layouts": [
            {"id": "demo", "renderer": {"pptx": {
                "source": "templates/pptx/x.pptx",
                "sha256": "a" * 64,
                "placeholder_map": {"title": 0},
                "module": "leftover-from-v1",
            }}}
        ],
    }
    with pytest.raises(ValidationError):
        _validator().validate(cat)


def test_alternatives_accepted_with_max_2(sample_v2_catalog):
    sample_v2_catalog["layouts"][0]["alternatives"] = [
        {
            "id": "demo--variant-a",
            "when_to_use": "When A",
            "renderer": {"pptx": {
                "source": "templates/pptx/demo-a.pptx",
                "sha256": "b" * 64,
                "placeholder_map": {"title": 0},
            }},
        },
        {
            "id": "demo--variant-b",
            "renderer": {"pptx": {
                "source": "templates/pptx/demo-b.pptx",
                "sha256": "c" * 64,
                "placeholder_map": {"title": 0},
            }},
        },
    ]
    _validator().validate(sample_v2_catalog)


def test_alternatives_over_max_rejected(sample_v2_catalog):
    sample_v2_catalog["layouts"][0]["alternatives"] = [
        {"id": f"demo--v{i}", "renderer": {"pptx": {
            "source": f"templates/pptx/demo-{i}.pptx",
            "sha256": str(i) * 64,
            "placeholder_map": {"title": 0},
        }}}
        for i in range(3)
    ]
    with pytest.raises(ValidationError):
        _validator().validate(sample_v2_catalog)


def test_v2_entry_missing_sha256_rejected():
    cat = {
        "brand": "x",
        "layouts": [
            {"id": "bad", "renderer": {"pptx": {"source": "x.pptx", "placeholder_map": {}}}}
        ],
    }
    with pytest.raises(ValidationError):
        _validator().validate(cat)


def test_invalid_sha256_pattern_rejected():
    cat = {
        "brand": "x",
        "layouts": [
            {"id": "bad", "renderer": {"pptx": {
                "source": "x.pptx", "sha256": "not-a-hash", "placeholder_map": {}
            }}}
        ],
    }
    with pytest.raises(ValidationError):
        _validator().validate(cat)


def test_unknown_auth_type_rejected():
    cat = {
        "brand": "x",
        "asset_sources": {
            "default": {"base_url": "https://example/", "auth": {"type": "oauth2", "env": "X"}}
        },
        "layouts": [],
    }
    with pytest.raises(ValidationError):
        _validator().validate(cat)


def test_asset_entry_with_bogus_sha_rejected():
    bad_asset = {"id": "x", "source": "x.svg", "sha256": "zz"}
    asset_schema = json.loads(ASSET_SCHEMA.read_text())
    with pytest.raises(ValidationError):
        Draft202012Validator(asset_schema).validate(bad_asset)
