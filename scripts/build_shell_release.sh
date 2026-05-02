#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 <shell> <version> <platform> <output-dir>" >&2
  exit 1
fi

shell_name="$1"
version="$2"
platform="$3"
output_dir="$4"

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
repo_root="$(CDPATH= cd -- "$script_dir/.." && pwd)"

builder_script="$(python3 "$script_dir/shell_catalog.py" build-script "$shell_name")"
exec bash "$repo_root/$builder_script" "$version" "$platform" "$output_dir"
