"""Top-level CLI entry. Dispatches to subcommands."""
from __future__ import annotations

import argparse
import sys

from cli import brand as brand_cmd


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="feinschliff")
    sub = p.add_subparsers(dest="command", required=True)

    brand_parser = sub.add_parser("brand", help="Brand pack management")
    brand_cmd.register(brand_parser)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())
