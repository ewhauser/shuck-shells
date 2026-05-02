#!/usr/bin/env python3
from __future__ import annotations

import argparse

from index_lib import load_ordered_json, validate_index_shape


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate shuck shell archive index JSON.")
    parser.add_argument("index_path", help="Path to index.json")
    return parser.parse_args()


def validate_index_file(path: str) -> None:
    index = load_ordered_json(path)
    validate_index_shape(index)


def main() -> None:
    args = parse_args()
    validate_index_file(args.index_path)


if __name__ == "__main__":
    main()
