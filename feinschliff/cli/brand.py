"""`feinschliff brand …` subcommand router."""
from __future__ import annotations

import argparse


def register(parser: argparse.ArgumentParser) -> None:
    sub = parser.add_subparsers(dest="brand_command", required=True)
    placeholder = sub.add_parser("_placeholder", help=argparse.SUPPRESS)
    placeholder.set_defaults(func=lambda args: 0)
