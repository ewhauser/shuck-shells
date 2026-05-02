from __future__ import annotations

from collections import OrderedDict
import json
from pathlib import Path
import re
import shutil
from typing import Iterable

SCHEMA_VERSION = 2
ROOT_KIND = "shuck.shells.index"
SHELL_KIND = "shuck.shells.versions"
RELEASE_KIND = "shuck.shells.release"
SUPPORTED_SHELLS = ("bash", "zsh", "dash", "mksh")
SUPPORTED_PLATFORMS = (
    "x86_64-linux-gnu",
    "aarch64-linux-gnu",
    "x86_64-linux-musl",
    "aarch64-linux-musl",
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


def canonicalize_inventory(
    shells: dict[str, dict[str, dict[str, dict[str, str]]]],
) -> OrderedDict[str, object]:
    canonical_shells: OrderedDict[str, object] = OrderedDict()
    for shell in sorted(shells):
        versions = shells[shell]
        canonical_versions: OrderedDict[str, object] = OrderedDict()
        for version in sorted(versions, key=version_sort_key, reverse=True):
            platforms = versions[version]
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
    return canonical_shells


def build_registry_documents(
    inventory: OrderedDict[str, object],
) -> OrderedDict[str, OrderedDict[str, object]]:
    documents: OrderedDict[str, OrderedDict[str, object]] = OrderedDict()
    root_shells: OrderedDict[str, object] = OrderedDict()
    for shell, shell_entry in inventory.items():
        root_shells[shell] = OrderedDict((("versions_url", f"shells/{shell}/index.json"),))

        shell_versions: OrderedDict[str, object] = OrderedDict()
        versions = shell_entry["versions"]
        for version, version_entry in versions.items():
            shell_versions[version] = OrderedDict((("manifest_url", f"{version}.json"),))
            documents[f"shells/{shell}/{version}.json"] = OrderedDict(
                (
                    ("version", SCHEMA_VERSION),
                    ("kind", RELEASE_KIND),
                    ("shell", shell),
                    ("release", version),
                    ("platforms", version_entry["platforms"]),
                )
            )

        documents[f"shells/{shell}/index.json"] = OrderedDict(
            (
                ("version", SCHEMA_VERSION),
                ("kind", SHELL_KIND),
                ("shell", shell),
                ("versions", shell_versions),
            )
        )

    documents["index.json"] = OrderedDict(
        (
            ("version", SCHEMA_VERSION),
            ("kind", ROOT_KIND),
            ("shells", root_shells),
        )
    )
    return documents


def duplicate_key_hook(pairs: Iterable[tuple[str, object]]) -> OrderedDict[str, object]:
    ordered: OrderedDict[str, object] = OrderedDict()
    for key, value in pairs:
        if key in ordered:
            raise IndexError(f"duplicate key `{key}` in JSON document")
        ordered[key] = value
    return ordered


def load_ordered_json(path: str | Path) -> OrderedDict[str, object]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle, object_pairs_hook=duplicate_key_hook)


def dump_json(path: str | Path, data: OrderedDict[str, object]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def write_registry_documents(
    output_dir: str | Path, documents: OrderedDict[str, OrderedDict[str, object]]
) -> None:
    output_path = Path(output_dir)
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True, exist_ok=True)
    for relative_path, document in documents.items():
        target = output_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        dump_json(target, document)


def validate_relative_json_reference(reference: object, field_name: str) -> str:
    if not isinstance(reference, str) or not reference.endswith(".json"):
        raise IndexError(f"`{field_name}` must be a relative JSON path")
    if reference.startswith("/") or "://" in reference:
        raise IndexError(f"`{field_name}` must be a relative JSON path")
    parts = Path(reference).parts
    if any(part == ".." for part in parts):
        raise IndexError(f"`{field_name}` must not escape the registry root")
    return reference


def resolve_reference(site_root: Path, base_document: Path, reference: str) -> Path:
    resolved = (base_document.parent / reference).resolve()
    try:
        resolved.relative_to(site_root.resolve())
    except ValueError as exc:
        raise IndexError(f"reference `{reference}` escapes the registry root") from exc
    return resolved


def validate_artifacts(
    platforms: object, shell: str, version: str
) -> None:
    if not isinstance(platforms, dict):
        raise IndexError(f"`{shell}` release `{version}` platforms must be an object")
    platform_names = list(platforms.keys())
    if platform_names != sorted(platform_names):
        raise IndexError(f"`{shell}` release `{version}` platforms must be sorted lexically")
    for platform, artifact in platforms.items():
        if platform not in SUPPORTED_PLATFORMS:
            raise IndexError(f"unsupported platform `{platform}`")
        if not isinstance(artifact, dict):
            raise IndexError(f"`{shell}` release `{version}` platform `{platform}` must be an object")
        if list(artifact.keys()) != ["url", "sha256"]:
            raise IndexError(
                f"`{shell}` release `{version}` platform `{platform}` must contain only `url` and `sha256`"
            )
        url = artifact["url"]
        sha256 = artifact["sha256"]
        if not isinstance(url, str) or not url.startswith("https://"):
            raise IndexError(
                f"`{shell}` release `{version}` platform `{platform}` url must be an https URL"
            )
        if not isinstance(sha256, str) or not SHA256_PATTERN.fullmatch(sha256):
            raise IndexError(
                f"`{shell}` release `{version}` platform `{platform}` sha256 must be a 64-character lowercase hex digest"
            )


def validate_root_document(document: OrderedDict[str, object]) -> OrderedDict[str, str]:
    if list(document.keys()) != ["version", "kind", "shells"]:
        raise IndexError(
            "root index keys must be exactly `version`, `kind`, and `shells` in that order"
        )
    if document["version"] != SCHEMA_VERSION:
        raise IndexError(f"root index `version` must be {SCHEMA_VERSION}")
    if document["kind"] != ROOT_KIND:
        raise IndexError(f"root index `kind` must be `{ROOT_KIND}`")
    shells = document["shells"]
    if not isinstance(shells, dict):
        raise IndexError("root index `shells` must be an object")

    shell_names = list(shells.keys())
    if shell_names != sorted(shell_names):
        raise IndexError("root index shell keys must be sorted lexically")

    references: OrderedDict[str, str] = OrderedDict()
    for shell, entry in shells.items():
        if shell not in SUPPORTED_SHELLS:
            raise IndexError(f"unsupported shell `{shell}`")
        if not isinstance(entry, dict):
            raise IndexError(f"root index entry for `{shell}` must be an object")
        if list(entry.keys()) != ["versions_url"]:
            raise IndexError(f"root index entry for `{shell}` must contain only `versions_url`")
        references[shell] = validate_relative_json_reference(
            entry["versions_url"], f"shells.{shell}.versions_url"
        )
    return references


def validate_shell_document(
    document: OrderedDict[str, object], expected_shell: str
) -> OrderedDict[str, str]:
    if list(document.keys()) != ["version", "kind", "shell", "versions"]:
        raise IndexError(
            "shell index keys must be exactly `version`, `kind`, `shell`, and `versions` in that order"
        )
    if document["version"] != SCHEMA_VERSION:
        raise IndexError(f"shell index `version` must be {SCHEMA_VERSION}")
    if document["kind"] != SHELL_KIND:
        raise IndexError(f"shell index `kind` must be `{SHELL_KIND}`")
    if document["shell"] != expected_shell:
        raise IndexError(f"shell index shell must be `{expected_shell}`")
    versions = document["versions"]
    if not isinstance(versions, dict):
        raise IndexError(f"`{expected_shell}` shell index `versions` must be an object")

    version_names = list(versions.keys())
    expected_versions = sorted(version_names, key=version_sort_key, reverse=True)
    if version_names != expected_versions:
        raise IndexError(f"`{expected_shell}` shell index versions must be sorted newest-first")

    references: OrderedDict[str, str] = OrderedDict()
    for version, entry in versions.items():
        if not isinstance(entry, dict):
            raise IndexError(f"`{expected_shell}` version `{version}` entry must be an object")
        if list(entry.keys()) != ["manifest_url"]:
            raise IndexError(
                f"`{expected_shell}` version `{version}` entry must contain only `manifest_url`"
            )
        references[version] = validate_relative_json_reference(
            entry["manifest_url"], f"{expected_shell}.versions.{version}.manifest_url"
        )
    return references


def validate_release_document(
    document: OrderedDict[str, object], expected_shell: str, expected_version: str
) -> None:
    if list(document.keys()) != ["version", "kind", "shell", "release", "platforms"]:
        raise IndexError(
            "release manifest keys must be exactly `version`, `kind`, `shell`, `release`, and `platforms` in that order"
        )
    if document["version"] != SCHEMA_VERSION:
        raise IndexError(f"release manifest `version` must be {SCHEMA_VERSION}")
    if document["kind"] != RELEASE_KIND:
        raise IndexError(f"release manifest `kind` must be `{RELEASE_KIND}`")
    if document["shell"] != expected_shell:
        raise IndexError(f"release manifest shell must be `{expected_shell}`")
    if document["release"] != expected_version:
        raise IndexError(f"release manifest release must be `{expected_version}`")
    validate_artifacts(document["platforms"], expected_shell, expected_version)


def validate_registry_site(site_root: str | Path) -> None:
    site_path = Path(site_root)
    root_path = site_path / "index.json"
    root_document = load_ordered_json(root_path)
    shell_references = validate_root_document(root_document)

    for shell, reference in shell_references.items():
        shell_path = resolve_reference(site_path, root_path, reference)
        if not shell_path.is_file():
            raise IndexError(f"missing shell index for `{shell}` at `{reference}`")
        shell_document = load_ordered_json(shell_path)
        manifest_references = validate_shell_document(shell_document, shell)
        for version, manifest_reference in manifest_references.items():
            manifest_path = resolve_reference(site_path, shell_path, manifest_reference)
            if not manifest_path.is_file():
                raise IndexError(
                    f"missing release manifest for `{shell}` `{version}` at `{manifest_reference}`"
                )
            release_document = load_ordered_json(manifest_path)
            validate_release_document(release_document, shell, version)
