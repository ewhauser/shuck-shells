#!/usr/bin/env python3
from __future__ import annotations

import argparse

from index_lib import validate_registry_site


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate the generated shuck shell registry.")
    parser.add_argument("site_root", help="Path to the generated registry root directory")
    return parser.parse_args()


def validate_registry(path: str) -> None:
    validate_registry_site(path)


def main() -> None:
    args = parse_args()
    validate_registry(args.site_root)


if __name__ == "__main__":
    main()
