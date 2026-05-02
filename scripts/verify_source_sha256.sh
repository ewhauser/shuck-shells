#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then
  echo "usage: $0 <expected-sha256> <source-path>" >&2
  exit 1
fi

expected_sha256="$1"
source_path="$2"

if [[ ! "$expected_sha256" =~ ^[0-9a-f]{64}$ ]]; then
  echo "invalid expected source sha256: ${expected_sha256}" >&2
  exit 1
fi

if [[ ! -e "$source_path" ]]; then
  echo "source path does not exist: ${source_path}" >&2
  exit 1
fi

if [[ -f "$source_path" ]]; then
  if command -v sha256sum >/dev/null 2>&1; then
    printf '%s  %s\n' "$expected_sha256" "$source_path" | sha256sum -c -
  elif command -v shasum >/dev/null 2>&1; then
    printf '%s  %s\n' "$expected_sha256" "$source_path" | shasum -a 256 -c -
  else
    echo "missing sha256sum or shasum for source verification" >&2
    exit 1
  fi
elif [[ -d "$source_path" ]]; then
  actual_sha256="$(
    python3 - "$source_path" <<'PY'
import hashlib
import os
import stat
import sys

root = os.path.abspath(sys.argv[1])
digest = hashlib.sha256()

for current_root, dirnames, filenames in os.walk(root):
    dirnames.sort()
    filenames.sort()
    rel_root = os.path.relpath(current_root, root)
    if rel_root != ".":
        rel_root = rel_root.replace(os.sep, "/")
        digest.update(b"D\0")
        digest.update(rel_root.encode("utf-8"))
        digest.update(b"\0")
    for name in filenames:
        path = os.path.join(current_root, name)
        rel_path = os.path.relpath(path, root).replace(os.sep, "/")
        st = os.lstat(path)
        executable = b"1" if (st.st_mode & 0o111) else b"0"
        if stat.S_ISLNK(st.st_mode):
            digest.update(b"L\0")
            digest.update(rel_path.encode("utf-8"))
            digest.update(b"\0")
            digest.update(executable)
            digest.update(b"\0")
            digest.update(os.readlink(path).encode("utf-8"))
            digest.update(b"\0")
            continue
        digest.update(b"F\0")
        digest.update(rel_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(executable)
        digest.update(b"\0")
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
        digest.update(b"\0")

print(digest.hexdigest())
PY
  )"

  if [[ "$actual_sha256" != "$expected_sha256" ]]; then
    echo "source content sha256 mismatch: expected ${expected_sha256}, got ${actual_sha256}" >&2
    exit 1
  fi
else
  echo "unsupported source path for verification: ${source_path}" >&2
  exit 1
fi
