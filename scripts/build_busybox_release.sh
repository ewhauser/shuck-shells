#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <busybox-version> <platform> <output-dir>" >&2
  exit 1
fi

version="$1"
platform="$2"
output_dir="$3"

case "$platform" in
  x86_64-linux-gnu|aarch64-linux-gnu|x86_64-linux-musl|aarch64-linux-musl)
    ;;
  *)
    echo "busybox build does not support platform ${platform}" >&2
    exit 1
    ;;
esac

source_url="https://busybox.net/downloads/busybox-${version}.tar.bz2"
work_root="$(mktemp -d)"
trap 'rm -rf "$work_root"' EXIT

source_archive="$work_root/busybox-${version}.tar.bz2"
source_dir="$work_root/busybox-${version}"
archive_root="$work_root/busybox-${version}-${platform}"
archive_name="busybox-${version}-${platform}.tar.gz"

mkdir -p "$output_dir"

echo "Downloading ${source_url}"
curl -fsSL "$source_url" -o "$source_archive"
tar -xjf "$source_archive" -C "$work_root"

pushd "$source_dir" >/dev/null
make defconfig
python3 - <<'PY'
from pathlib import Path

config_path = Path(".config")
text = config_path.read_text(encoding="utf-8")


def set_flag(config_text: str, key: str, value: str) -> str:
    active = f"{key}="
    inactive = f"# {key} is not set"
    lines = []
    replaced = False
    for line in config_text.splitlines():
        if line.startswith(active) or line == inactive:
            lines.append(f"{key}={value}")
            replaced = True
        else:
            lines.append(line)
    if not replaced:
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


text = set_flag(text, "CONFIG_ASH", "y")
text = set_flag(text, "CONFIG_SH_IS_ASH", "y")
config_path.write_text(text, encoding="utf-8")
PY
make olddefconfig >/dev/null
if command -v getconf >/dev/null 2>&1; then
  jobs="$(getconf _NPROCESSORS_ONLN)"
elif command -v sysctl >/dev/null 2>&1; then
  jobs="$(sysctl -n hw.ncpu)"
else
  jobs=2
fi
make -j"$jobs"
popd >/dev/null

mkdir -p "$archive_root/bin"
cp "$source_dir/busybox" "$archive_root/bin/busybox.bin"
cp "$source_dir/LICENSE" "$archive_root/LICENSE"

cat >"$archive_root/bin/busybox" <<'EOF'
#!/usr/bin/env sh
set -eu
SELF_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec "$SELF_DIR/busybox.bin" sh "$@"
EOF

chmod 755 "$archive_root/bin/busybox" "$archive_root/bin/busybox.bin"

actual_output="$("$archive_root/bin/busybox" -c 'printf ok')"
if [[ "$actual_output" != "ok" ]]; then
  echo "built busybox failed smoke test" >&2
  exit 1
fi

tar -czf "${output_dir}/${archive_name}" -C "$work_root" "$(basename "$archive_root")"
tar -tzf "${output_dir}/${archive_name}" >/dev/null

echo "Created ${output_dir}/${archive_name}"
