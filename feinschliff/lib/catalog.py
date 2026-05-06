"""Load and inspect feinschliff brand catalog files (v1 and v2 entries)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, RefResolver, ValidationError


REQUIRED_TOP_KEYS = ("brand", "layouts")
_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"


class RendererKind(Enum):
    V1 = "v1"
    V2 = "v2"
    NONE = "none"


@dataclass
class V2RendererSpec:
    source: str
    sha256: str
    placeholder_map: dict[str, int]

    @classmethod
    def from_entry(cls, entry: dict, kind: str) -> "V2RendererSpec":
        r = entry["renderer"][kind]
        return cls(source=r["source"], sha256=r["sha256"], placeholder_map=r["placeholder_map"])


def _build_validator() -> Draft202012Validator:
    catalog_schema = json.loads((_SCHEMA_DIR / "catalog-v2.schema.json").read_text())
    asset_schema = json.loads((_SCHEMA_DIR / "asset-entry.schema.json").read_text())
    store = {
        catalog_schema["$id"]: catalog_schema,
        asset_schema["$id"]: asset_schema,
        "asset-entry.schema.json": asset_schema,
    }
    resolver = RefResolver(base_uri=catalog_schema["$id"], referrer=catalog_schema, store=store)
    return Draft202012Validator(catalog_schema, resolver=resolver)


def load_catalog(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text())
    for k in REQUIRED_TOP_KEYS:
        if k not in data:
            raise ValueError(f"catalog at {path} missing required key '{k}'")
    # Build a fresh validator per call: jsonschema.RefResolver caches resolved $refs in
    # internal state, and that cache breaks $defs lookups when the same validator instance
    # is reused against multiple catalogs in the same process. Cost is negligible (~1ms).
    validator = _build_validator()
    try:
        validator.validate(data)
    except ValidationError as e:
        raise ValueError(f"catalog at {path} fails schema validation: {e.message}") from e
    return data


def get_renderer_kind(entry: dict, kind: str) -> RendererKind:
    r = entry.get("renderer", {}).get(kind)
    if r is None:
        return RendererKind.NONE
    if "source" in r:
        return RendererKind.V2
    if "module" in r:
        return RendererKind.V1
    return RendererKind.NONE
