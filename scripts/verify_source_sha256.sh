#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <expected-sha256> <archive-path>" >&2
  exit 1
fi

expected_sha256="$1"
archive_path="$2"

if [[ ! "$expected_sha256" =~ ^[0-9a-f]{64}$ ]]; then
  echo "invalid expected source sha256: ${expected_sha256}" >&2
  exit 1
fi

if [[ ! -f "$archive_path" ]]; then
  echo "source archive does not exist: ${archive_path}" >&2
  exit 1
fi

if command -v sha256sum >/dev/null 2>&1; then
  printf '%s  %s\n' "$expected_sha256" "$archive_path" | sha256sum -c -
elif command -v shasum >/dev/null 2>&1; then
  printf '%s  %s\n' "$expected_sha256" "$archive_path" | shasum -a 256 -c -
else
  echo "missing sha256sum or shasum for source verification" >&2
  exit 1
fi
