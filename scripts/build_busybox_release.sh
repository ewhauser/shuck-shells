#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <busybox-version> <platform> <output-dir>" >&2
  exit 1
fi

version="$1"
platform="$2"
output_dir="$3"
script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"

case "$platform" in
  x86_64-linux-musl|aarch64-linux-musl)
    ;;
  *)
    echo "busybox repackaging does not support platform ${platform}" >&2
    exit 1
    ;;
esac

work_root="$(mktemp -d)"
trap 'rm -rf "$work_root"' EXIT

source_url="$(
  python3 "$script_dir/busybox_rootfs.py" resolve "$version" "$platform" --field rootfs_url
)"
source_archive="$work_root/rootfs.tar.gz"
source_dir="$work_root/rootfs"
archive_root="$work_root/busybox-${version}-${platform}"
archive_name="busybox-${version}-${platform}.tar.gz"

mkdir -p "$output_dir"
mkdir -p "$source_dir"

echo "Downloading ${source_url}"
curl -fsSL "$source_url" -o "$source_archive"
tar -xzf "$source_archive" -C "$source_dir"

mkdir -p "$archive_root/bin"
cp "$source_dir/bin/busybox" "$archive_root/bin/busybox.bin"

cat >"$archive_root/bin/busybox" <<'EOF'
#!/usr/bin/env sh
set -eu
SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$SELF_DIR/busybox.bin" sh "$@"
EOF

chmod 755 "$archive_root/bin/busybox" "$archive_root/bin/busybox.bin"

actual_output="$("$archive_root/bin/busybox" -c 'printf ok')"
if [[ "$actual_output" != "ok" ]]; then
  echo "repackaged busybox failed smoke test" >&2
  exit 1
fi

tar -czf "${output_dir}/${archive_name}" -C "$work_root" "$(basename "$archive_root")"
tar -tzf "${output_dir}/${archive_name}" >/dev/null

echo "Created ${output_dir}/${archive_name}"
