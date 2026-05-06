"""`feinschliff brand …` subcommand router."""
from __future__ import annotations

import argparse
import sys

from lib.brand_discovery import discover_brands
from lib.catalog import load_catalog, get_renderer_kind, RendererKind, V2RendererSpec
from lib.resolver import Resolver


def register(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="brand_command", required=True)

    p_list = sub.add_parser("list", help="List discovered brand packs")
    p_list.set_defaults(func=cmd_list)

    p_inspect = sub.add_parser("inspect", help="Print catalog summary for a brand")
    p_inspect.add_argument("name")
    p_inspect.set_defaults(func=cmd_inspect)

    p_sync = sub.add_parser("sync", help="Prefetch + verify all artifacts for a brand")
    p_sync.add_argument("name")
    p_sync.add_argument("--with-images", action="store_true",
                        help="Also fetch the full image corpus (default: skip)")
    p_sync.set_defaults(func=cmd_sync)


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


def cmd_sync(args) -> int:
    brand = next((b for b in discover_brands() if b.name == args.name), None)
    if brand is None:
        print(f"brand not found: {args.name}", file=sys.stderr)
        return 1
    cat = load_catalog(brand.catalog_path)
    version = cat.get("version", "0.0.0")
    resolver = Resolver(brand=brand.name, version=version, catalog=cat)

    targets: list[tuple[str, str, str, str]] = []
    for entry in cat.get("layouts", []):
        if get_renderer_kind(entry, "pptx") is not RendererKind.V2:
            continue
        spec = V2RendererSpec.from_entry(entry, "pptx")
        targets.append((spec.source, spec.sha256, "templates/pptx", "pptx"))

    assets = cat.get("assets", {})
    for item in assets.get("icons", []):
        targets.append((item["source"], item["sha256"], "icons", _ext(item["source"])))
    for item in assets.get("illustrations", []):
        targets.append((item["source"], item["sha256"], "illustrations", _ext(item["source"])))
    if args.with_images:
        for item in assets.get("images", []):
            targets.append((item["source"], item["sha256"], "images", _ext(item["source"])))
    elif assets.get("images"):
        print(f"skipping images ({len(assets['images'])}); pass --with-images to include")

    total = len(targets)
    for i, (source, sha, kind, ext) in enumerate(targets, 1):
        resolver.fetch(source=source, sha256=sha, kind=kind, ext=ext)
        print(f"{i}/{total}\t{source}")
    return 0


def _ext(source: str) -> str:
    return source.rsplit(".", 1)[-1]
