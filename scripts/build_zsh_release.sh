#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
  echo "usage: $0 <zsh-version> <platform> <output-dir>" >&2
  exit 1
fi

version="$1"
platform="$2"
output_dir="$3"

source_url="https://downloads.sourceforge.net/project/zsh/zsh/${version}/zsh-${version}.tar.xz"
work_root="$(mktemp -d)"
trap 'rm -rf "$work_root"' EXIT

source_archive="$work_root/zsh-${version}.tar.xz"
source_dir="$work_root/zsh-${version}"
stage_dir="$work_root/stage"
archive_root="$work_root/zsh-${version}-${platform}"
archive_name="zsh-${version}-${platform}.tar.gz"

mkdir -p "$output_dir"

echo "Downloading ${source_url}"
curl -fsSL "$source_url" -o "$source_archive"
tar -xJf "$source_archive" -C "$work_root"

python3 - "$source_dir/Src/Modules/termcap.c" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
old = "static char *boolcodes[] = {"
new = "NCURSES_CONST char *const boolcodes[] = {"
if new not in text:
    if old not in text:
        raise SystemExit("zsh termcap.c patch anchor not found")
    text = text.replace(old, new, 1)
    path.write_text(text, encoding="utf-8")
PY

pushd "$source_dir" >/dev/null
"$source_dir/configure" --prefix=/usr/local --with-tcsetpgrp
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
rm -rf "$archive_root/share/man" "$archive_root/share/info"

license_source="$source_dir/LICENCE"
if [[ ! -f "$license_source" ]]; then
  license_source="$source_dir/LICENSE"
fi
cp "$license_source" "$archive_root/LICENSE"

bootstrap_dir="$archive_root/lib/shuck-zsh-bootstrap"
mkdir -p "$bootstrap_dir"
cat >"$bootstrap_dir/.zshenv" <<'EOF'
typeset -gaU module_path fpath

for candidate in "$SHUCK_ZSH_ROOT"/lib/zsh/*; do
  if [[ -d "$candidate" ]]; then
    module_path=("$candidate" $module_path)
    break
  fi
done

for candidate in "$SHUCK_ZSH_ROOT"/share/zsh/*/functions; do
  if [[ -d "$candidate" ]]; then
    fpath=("$candidate" $fpath)
    break
  fi
done

if [[ -d "$SHUCK_ZSH_ROOT/share/zsh/site-functions" ]]; then
  fpath=("$SHUCK_ZSH_ROOT/share/zsh/site-functions" $fpath)
fi

if [[ ${SHUCK_ZSH_USER_ZDOTDIR:-__unset__} != "__unset__" ]]; then
  export ZDOTDIR="$SHUCK_ZSH_USER_ZDOTDIR"
  user_zdotdir="$SHUCK_ZSH_USER_ZDOTDIR"
else
  unset ZDOTDIR
  user_zdotdir="${SHUCK_ZSH_USER_HOME:-}"
fi

user_zshenv=""
if [[ -n "$user_zdotdir" ]]; then
  user_zshenv="$user_zdotdir/.zshenv"
fi

if [[ -n "$user_zshenv" && -r "$user_zshenv" && "$user_zshenv" != "${SHUCK_ZSH_BOOTSTRAP_ZSHENV:-}" ]]; then
  source "$user_zshenv"
fi
EOF

mv "$archive_root/bin/zsh" "$archive_root/bin/zsh.real"
cat >"$archive_root/bin/zsh" <<'EOF'
#!/bin/sh
set -eu

self_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
root_dir=$(CDPATH= cd -- "$self_dir/.." && pwd)
bootstrap_dir="$root_dir/lib/shuck-zsh-bootstrap"
if [ "${ZDOTDIR+x}" = "x" ]; then
  export SHUCK_ZSH_USER_ZDOTDIR="$ZDOTDIR"
else
  export SHUCK_ZSH_USER_ZDOTDIR="__unset__"
fi
export SHUCK_ZSH_USER_HOME="${HOME:-}"
export SHUCK_ZSH_ROOT="$root_dir"
export SHUCK_ZSH_BOOTSTRAP_ZSHENV="$bootstrap_dir/.zshenv"
export ZDOTDIR="$bootstrap_dir"
exec "$self_dir/zsh.real" "$@"
EOF
chmod 755 "$archive_root/bin/zsh" "$archive_root/bin/zsh.real"

actual_version="$("$archive_root/bin/zsh" --version | head -n 1)"
case "$actual_version" in
  "zsh ${version}"* | *"zsh ${version}"*) ;;
  *)
    echo "built zsh reported unexpected version: ${actual_version}" >&2
    exit 1
    ;;
esac

"$archive_root/bin/zsh" -c 'zmodload zsh/zutil'
"$archive_root/bin/zsh" -c 'autoload -Uz add-zsh-hook; add-zsh-hook -L >/dev/null'

tar -czf "${output_dir}/${archive_name}" -C "$work_root" "$(basename "$archive_root")"
tar -tzf "${output_dir}/${archive_name}" >/dev/null

echo "Created ${output_dir}/${archive_name}"
