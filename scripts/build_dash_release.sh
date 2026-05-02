#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <dash-version> <platform> <output-dir>" >&2
  exit 1
fi

version="$1"
platform="$2"
output_dir="$3"

source_url="https://gondor.apana.org.au/~herbert/dash/files/dash-${version}.tar.gz"
work_root="$(mktemp -d)"
trap 'rm -rf "$work_root"' EXIT

source_archive="$work_root/dash-${version}.tar.gz"
source_dir="$work_root/dash-${version}"
build_dir="$work_root/build"
stage_dir="$work_root/stage"
archive_root="$work_root/dash-${version}-${platform}"
archive_name="dash-${version}-${platform}.tar.gz"

mkdir -p "$output_dir" "$build_dir"

echo "Downloading ${source_url}"
curl -fsSL "$source_url" -o "$source_archive"
tar -xzf "$source_archive" -C "$work_root"

pushd "$build_dir" >/dev/null
"$source_dir/configure" --prefix=/usr/local
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

mkdir -p "$archive_root"
cp -R "$stage_dir/usr/local/." "$archive_root/"
cp "$source_dir/COPYING" "$archive_root/LICENSE"
chmod 755 "$archive_root/bin/dash"

actual_output="$("$archive_root/bin/dash" -c 'printf ok')"
if [[ "$actual_output" != "ok" ]]; then
  echo "built dash failed smoke test" >&2
  exit 1
fi

tar -czf "${output_dir}/${archive_name}" -C "$work_root" "$(basename "$archive_root")"
tar -tzf "${output_dir}/${archive_name}" >/dev/null

echo "Created ${output_dir}/${archive_name}"
