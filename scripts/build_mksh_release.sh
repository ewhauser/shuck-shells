#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  echo "usage: $0 <mksh-version> <platform> <source-sha256> <output-dir>" >&2
  exit 1
fi

version="$1"
platform="$2"
source_sha256="$3"
output_dir="$4"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

archive_version="$version"
case "$archive_version" in
  R*) ;;
  *) archive_version="R${archive_version}" ;;
esac

source_url="https://mbsd.evolvis.org/MirOS/dist/mir/mksh/mksh-${archive_version}.tgz"
work_root="$(mktemp -d)"
trap 'rm -rf "$work_root"' EXIT

source_archive="$work_root/mksh-${archive_version}.tgz"
source_dir="$work_root/mksh"
build_dir="$work_root/build"
archive_root="$work_root/mksh-${version}-${platform}"
archive_name="mksh-${version}-${platform}.tar.gz"

mkdir -p "$output_dir" "$source_dir" "$build_dir" "$archive_root/bin"

echo "Downloading ${source_url}"
curl -fsSL "$source_url" -o "$source_archive"
"$repo_root/scripts/verify_source_sha256.sh" "$source_sha256" "$source_archive"
tar -xzf "$source_archive" -C "$source_dir" --strip-components=1

pushd "$build_dir" >/dev/null
/bin/sh "$source_dir/Build.sh"
popd >/dev/null

binary_path="$build_dir/mksh"
if [[ ! -x "$binary_path" ]]; then
  echo "mksh build did not produce $binary_path" >&2
  exit 1
fi

cp "$binary_path" "$archive_root/bin/mksh"
chmod 755 "$archive_root/bin/mksh"

for candidate in LICENSE ISCL ML; do
  if [[ -f "$source_dir/$candidate" ]]; then
    cp "$source_dir/$candidate" "$archive_root/$candidate"
  fi
done

actual_output="$("$archive_root/bin/mksh" -c 'print ok')"
if [[ "$actual_output" != "ok" ]]; then
  echo "built mksh failed smoke test" >&2
  exit 1
fi

tar -czf "${output_dir}/${archive_name}" -C "$work_root" "$(basename "$archive_root")"
tar -tzf "${output_dir}/${archive_name}" >/dev/null

echo "Created ${output_dir}/${archive_name}"
