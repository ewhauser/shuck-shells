from __future__ import annotations

from collections import OrderedDict
import json
import re
from typing import Iterable

INDEX_VERSION = 1
SUPPORTED_SHELLS = ("bash", "zsh", "dash", "mksh")
SUPPORTED_PLATFORMS = (
    "x86_64-linux",
    "aarch64-linux",
    "x86_64-darwin",
    "aarch64-darwin",
)
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
TAG_PATTERN = re.compile(r"^(bash|zsh|dash|mksh)-(.+)$")


class IndexError(ValueError):
    pass


def parse_release_tag(tag: str) -> tuple[str, str]:
    match = TAG_PATTERN.fullmatch(tag)
    if not match:
        raise IndexError(
            f"invalid release tag `{tag}`; expected <shell>-<version> for a supported shell"
        )
    shell, version = match.groups()
    if not version:
        raise IndexError(f"missing version in release tag `{tag}`")
    return shell, version


def parse_asset_filename(filename: str) -> tuple[str, str, str] | None:
    for platform in SUPPORTED_PLATFORMS:
        suffix = f"-{platform}.tar.gz"
        if not filename.endswith(suffix):
            continue
        stem = filename[: -len(suffix)]
        shell, version = parse_release_tag(stem)
        return shell, version, platform
    return None


def tokenize_version(raw: str) -> list[tuple[int, int | str]]:
    tokens: list[tuple[int, int | str]] = []
    index = 0
    while index < len(raw):
        ch = raw[index]
        if ch.isdigit():
            end = index
            while end < len(raw) and raw[end].isdigit():
                end += 1
            tokens.append((0, int(raw[index:end])))
            index = end
            continue
        if ch.isalpha():
            end = index
            while end < len(raw) and raw[end].isalpha():
                end += 1
            tokens.append((1, raw[index:end].lower()))
            index = end
            continue
        if ch == ".":
            index += 1
            continue
        break
    if not tokens:
        raise IndexError(f"invalid version `{raw}`")
    return tokens


def version_sort_key(raw: str) -> tuple[tuple[int, int | str], ...]:
    return tuple(tokenize_version(raw))


def canonicalize_index(index: dict) -> OrderedDict[str, object]:
    shells = index.get("shells", {})
    canonical_shells: OrderedDict[str, object] = OrderedDict()
    for shell in sorted(shells):
        versions = shells[shell]["versions"]
        canonical_versions: OrderedDict[str, object] = OrderedDict()
        for version in sorted(versions, key=version_sort_key, reverse=True):
            platforms = versions[version]["platforms"]
            canonical_platforms: OrderedDict[str, object] = OrderedDict()
            for platform in sorted(platforms):
                canonical_platforms[platform] = OrderedDict(
                    (
                        ("url", platforms[platform]["url"]),
                        ("sha256", platforms[platform]["sha256"]),
                    )
                )
            canonical_versions[version] = OrderedDict((("platforms", canonical_platforms),))
        canonical_shells[shell] = OrderedDict((("versions", canonical_versions),))
    return OrderedDict((("version", INDEX_VERSION), ("shells", canonical_shells)))


def duplicate_key_hook(pairs: Iterable[tuple[str, object]]) -> OrderedDict[str, object]:
    ordered: OrderedDict[str, object] = OrderedDict()
    for key, value in pairs:
        if key in ordered:
            raise IndexError(f"duplicate key `{key}` in JSON document")
        ordered[key] = value
    return ordered


def load_ordered_json(path: str) -> OrderedDict[str, object]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=duplicate_key_hook)


def dump_json(path: str, data: OrderedDict[str, object]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def validate_index_shape(index: OrderedDict[str, object]) -> None:
    if list(index.keys()) != ["version", "shells"]:
        raise IndexError("top-level keys must be exactly `version` and `shells` in that order")
    if index["version"] != INDEX_VERSION:
        raise IndexError(f"`version` must be {INDEX_VERSION}")
    shells = index["shells"]
    if not isinstance(shells, dict):
        raise IndexError("`shells` must be an object")

    shell_names = list(shells.keys())
    if shell_names != sorted(shell_names):
        raise IndexError("shell keys must be sorted lexically")
    for shell, shell_entry in shells.items():
        if shell not in SUPPORTED_SHELLS:
            raise IndexError(f"unsupported shell `{shell}`")
        if not isinstance(shell_entry, dict):
            raise IndexError(f"`shells.{shell}` must be an object")
        if list(shell_entry.keys()) != ["versions"]:
            raise IndexError(f"`shells.{shell}` must contain only `versions`")
        versions = shell_entry["versions"]
        if not isinstance(versions, dict):
            raise IndexError(f"`shells.{shell}.versions` must be an object")
        version_names = list(versions.keys())
        expected_versions = sorted(version_names, key=version_sort_key, reverse=True)
        if version_names != expected_versions:
            raise IndexError(f"`shells.{shell}.versions` must be sorted newest-first")
        for version, version_entry in versions.items():
            if not isinstance(version_entry, dict):
                raise IndexError(f"`shells.{shell}.versions.{version}` must be an object")
            if list(version_entry.keys()) != ["platforms"]:
                raise IndexError(
                    f"`shells.{shell}.versions.{version}` must contain only `platforms`"
                )
            platforms = version_entry["platforms"]
            if not isinstance(platforms, dict):
                raise IndexError(
                    f"`shells.{shell}.versions.{version}.platforms` must be an object"
                )
            platform_names = list(platforms.keys())
            if platform_names != sorted(platform_names):
                raise IndexError(
                    f"`shells.{shell}.versions.{version}.platforms` must be sorted lexically"
                )
            for platform, artifact in platforms.items():
                if platform not in SUPPORTED_PLATFORMS:
                    raise IndexError(f"unsupported platform `{platform}`")
                if not isinstance(artifact, dict):
                    raise IndexError(
                        f"`shells.{shell}.versions.{version}.platforms.{platform}` must be an object"
                    )
                if list(artifact.keys()) != ["url", "sha256"]:
                    raise IndexError(
                        f"`shells.{shell}.versions.{version}.platforms.{platform}` must contain only `url` and `sha256`"
                    )
                url = artifact["url"]
                sha256 = artifact["sha256"]
                if not isinstance(url, str) or not url.startswith("https://"):
                    raise IndexError(
                        f"`shells.{shell}.versions.{version}.platforms.{platform}.url` must be an https URL"
                    )
                if not isinstance(sha256, str) or not SHA256_PATTERN.fullmatch(sha256):
                    raise IndexError(
                        f"`shells.{shell}.versions.{version}.platforms.{platform}.sha256` must be a 64-character lowercase hex digest"
                    )
