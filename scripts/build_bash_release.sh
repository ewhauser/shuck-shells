#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <bash-version> <platform> <output-dir>" >&2
  exit 1
fi

version="$1"
platform="$2"
output_dir="$3"

source_url="https://ftp.gnu.org/pub/gnu/bash/bash-${version}.tar.gz"
work_root="$(mktemp -d)"
trap 'rm -rf "$work_root"' EXIT

source_archive="$work_root/bash-${version}.tar.gz"
source_dir="$work_root/bash-${version}"
build_dir="$work_root/build"
stage_dir="$work_root/stage"
archive_root="$work_root/bash-${version}-${platform}"
archive_name="bash-${version}-${platform}.tar.gz"

mkdir -p "$output_dir" "$build_dir" "$archive_root/bin"

echo "Downloading ${source_url}"
curl -fsSL "$source_url" -o "$source_archive"
tar -xzf "$source_archive" -C "$work_root"

pushd "$build_dir" >/dev/null
"$source_dir/configure" --prefix=/usr/local --without-bash-malloc
if command -v getconf >/dev/null 2>&1; then
  jobs="$(getconf _NPROCESSORS_ONLN)"
elif command -v sysctl >/dev/null 2>&1; then
  jobs="$(sysctl -n hw.ncpu)"
else
  jobs=2
fi
make -j"$jobs"
make install DESTDIR="$stage_dir"
popd >/dev/null

cp "$stage_dir/usr/local/bin/bash" "$archive_root/bin/bash"
cp "$source_dir/COPYING" "$archive_root/LICENSE"
chmod 755 "$archive_root/bin/bash"

actual_version="$("$archive_root/bin/bash" --version | head -n 1)"
case "$actual_version" in
  *"version ${version}"*) ;;
  *)
    echo "built bash reported unexpected version: ${actual_version}" >&2
    exit 1
    ;;
esac

tar -czf "${output_dir}/${archive_name}" -C "$work_root" "$(basename "$archive_root")"
tar -tzf "${output_dir}/${archive_name}" >/dev/null

echo "Created ${output_dir}/${archive_name}"
