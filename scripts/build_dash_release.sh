#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 <dash-version> <platform> <source-sha256> <output-dir>" >&2
  exit 1
fi

version="$1"
platform="$2"
source_sha256="$3"
output_dir="$4"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

source_url="https://kernel.googlesource.com/pub/scm/utils/dash/dash/+archive/refs/tags/v${version}.tar.gz"
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
"$repo_root/scripts/verify_source_sha256.sh" "$source_sha256" "$source_archive"
mkdir -p "$source_dir"
tar -xzf "$source_archive" -C "$source_dir"

if [[ ! -x "$source_dir/configure" ]]; then
  if [[ -x "$source_dir/autogen.sh" ]]; then
    (cd "$source_dir" && ./autogen.sh)
  elif [[ -f "$source_dir/autogen.sh" ]]; then
    (cd "$source_dir" && sh ./autogen.sh)
  else
    echo "dash source archive does not contain configure or autogen.sh" >&2
    exit 1
  fi
fi

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
