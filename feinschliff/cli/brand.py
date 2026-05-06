"""`feinschliff brand …` subcommand router."""
from __future__ import annotations

import argparse
import sys

from lib.brand_discovery import discover_brands
from lib.catalog import load_catalog, get_renderer_kind, RendererKind


def register(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="brand_command", required=True)

    p_list = sub.add_parser("list", help="List discovered brand packs")
    p_list.set_defaults(func=cmd_list)

    p_inspect = sub.add_parser("inspect", help="Print catalog summary for a brand")
    p_inspect.add_argument("name")
    p_inspect.set_defaults(func=cmd_inspect)


def cmd_list(_args) -> int:
    for b in discover_brands():
        print(f"{b.name}\t{b.root}")
    return 0


def cmd_inspect(args) -> int:
    brand = next((b for b in discover_brands() if b.name == args.name), None)
    if brand is None:
        print(f"brand not found: {args.name}", file=sys.stderr)
        return 1
    cat = load_catalog(brand.catalog_path)
    layouts = cat.get("layouts", [])
    v1 = sum(1 for e in layouts if get_renderer_kind(e, "pptx") is RendererKind.V1)
    v2 = sum(1 for e in layouts if get_renderer_kind(e, "pptx") is RendererKind.V2)
    assets = cat.get("assets", {})
    print(f"brand: {brand.name}")
    print(f"version: {cat.get('version', '?')}")
    print(f"layouts: {len(layouts)} (v1: {v1}, v2: {v2})")
    print(f"icons: {len(assets.get('icons', []))}")
    print(f"illustrations: {len(assets.get('illustrations', []))}")
    print(f"images: {len(assets.get('images', []))}")
    return 0
