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

    p_bundle = sub.add_parser("bundle", help="Pack brand cache into a portable archive")
    p_bundle.add_argument("name")
    p_bundle.add_argument("-o", "--output", required=True, help="Output archive path (.tar.gz)")
    p_bundle.set_defaults(func=cmd_bundle)

    p_install = sub.add_parser("install", help="Extract a bundle archive into the cache")
    p_install.add_argument("archive")
    p_install.set_defaults(func=cmd_install)


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


def cmd_bundle(args) -> int:
    """Pack the brand directory and the per-brand cache into a two-namespace tar.gz.

    Layout:
        brand/{name}/         <- catalog.json + templates/ + assets/  (restored to ~/.feinschliff/brands/{name}/)
        cache/{name}/{ver}/   <- content-addressed binaries           (restored to ~/.cache/feinschliff/{name}/{ver}/)
    """
    import tarfile
    from lib.cache import cache_dir

    brand = next((b for b in discover_brands() if b.name == args.name), None)
    if brand is None:
        print(f"brand not found: {args.name}", file=sys.stderr)
        return 1
    cat = load_catalog(brand.catalog_path)
    version = cat.get("version", "0.0.0")
    cdir = cache_dir(brand.name, version)
    out = args.output
    with tarfile.open(out, "w:gz") as tf:
        tf.add(brand.root, arcname=f"brand/{brand.name}")
        if cdir.is_dir():
            tf.add(cdir, arcname=f"cache/{brand.name}/{version}")
    print(f"wrote {out}")
    return 0


def cmd_install(args) -> int:
    """Restore a bundle: brand dir → ~/.feinschliff/brands/, cache → ~/.cache/feinschliff/.

    Verifies each content-addressed cache file's filename matches its sha256 after extraction.
    """
    import hashlib
    import tarfile
    from pathlib import Path
    from lib.cache import cache_root

    user_brands_root = Path.home() / ".feinschliff" / "brands"
    croot = cache_root()
    user_brands_root.mkdir(parents=True, exist_ok=True)
    croot.mkdir(parents=True, exist_ok=True)

    extracted_cache_files: list[Path] = []
    with tarfile.open(args.archive, "r:gz") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            parts = Path(member.name).parts
            if len(parts) < 2:
                continue
            section, rel_parts = parts[0], parts[1:]
            if section == "brand":
                target_root = user_brands_root
            elif section == "cache":
                target_root = croot
            else:
                continue
            target = target_root.joinpath(*rel_parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            extracted = tf.extractfile(member)
            if extracted is None:
                continue
            with open(target, "wb") as dst:
                dst.write(extracted.read())
            if section == "cache":
                extracted_cache_files.append(target)

    bad: list[str] = []
    for p in extracted_cache_files:
        stem = p.stem
        if len(stem) == 64 and all(c in "0123456789abcdef" for c in stem):
            actual = hashlib.sha256(p.read_bytes()).hexdigest()
            if actual != stem:
                bad.append(f"{p}: expected {stem}, got {actual}")
    if bad:
        for line in bad:
            print(f"hash mismatch: {line}", file=sys.stderr)
        return 2

    print(f"installed {args.archive}: brand → {user_brands_root}, cache → {croot}")
    return 0
