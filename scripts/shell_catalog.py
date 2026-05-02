from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "shells.json"
SUPPORTED_SOURCE_KINDS = ("build", "github_release")


class CatalogError(ValueError):
    pass


def load_shell_catalog() -> dict[str, dict[str, Any]]:
    catalog_path = Path(os.environ.get("SHUCK_SHELLS_CATALOG_PATH", DEFAULT_CATALOG_PATH))
    with open(catalog_path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise CatalogError("shell catalog root must be an object")

    shell_names = list(payload.keys())
    if shell_names != sorted(shell_names):
        raise CatalogError("shell catalog keys must be sorted lexically")

    for shell, metadata in payload.items():
        if not isinstance(metadata, dict):
            raise CatalogError(f"shell catalog entry `{shell}` must be an object")

        display_name = metadata.get("display_name")
        if not isinstance(display_name, str) or not display_name:
            raise CatalogError(f"shell catalog entry `{shell}` must define a display_name")

        release_source = metadata.get("release_source")
        if not isinstance(release_source, dict):
            raise CatalogError(f"shell catalog entry `{shell}` must define release_source")

        source_kind = release_source.get("kind")
        if source_kind not in SUPPORTED_SOURCE_KINDS:
            raise CatalogError(
                f"shell catalog entry `{shell}` has unsupported release source kind `{source_kind}`"
            )

        if source_kind == "build":
            builder = release_source.get("builder")
            if not isinstance(builder, str) or not builder:
                raise CatalogError(
                    f"shell catalog entry `{shell}` must define a builder for build sources"
                )

        upstream = metadata.get("upstream")
        if source_kind == "build":
            if not isinstance(upstream, dict):
                raise CatalogError(
                    f"shell catalog entry `{shell}` must define upstream discovery metadata"
                )
            discovery_urls = upstream.get("discovery_urls")
            version_pattern = upstream.get("version_pattern")
            if (
                not isinstance(discovery_urls, list)
                or not discovery_urls
                or any(
                    not isinstance(discovery_url, str) or not discovery_url.startswith("https://")
                    for discovery_url in discovery_urls
                )
            ):
                raise CatalogError(
                    f"shell catalog entry `{shell}` must define non-empty https upstream discovery_urls"
                )
            if not isinstance(version_pattern, str) or not version_pattern:
                raise CatalogError(
                    f"shell catalog entry `{shell}` must define an upstream version_pattern"
                )
    return payload


def shell_metadata(shell: str) -> dict[str, Any]:
    catalog = load_shell_catalog()
    try:
        return catalog[shell]
    except KeyError as exc:
        raise CatalogError(f"unsupported shell `{shell}`") from exc


def shell_display_name(shell: str) -> str:
    return str(shell_metadata(shell)["display_name"])


def release_source_kind(shell: str) -> str:
    release_source = shell_metadata(shell)["release_source"]
    return str(release_source["kind"])


def build_script(shell: str) -> str:
    metadata = shell_metadata(shell)
    release_source = metadata["release_source"]
    source_kind = release_source["kind"]
    if source_kind != "build":
        raise CatalogError(
            f"shell `{shell}` uses release source kind `{source_kind}` and is not buildable by this workflow"
        )
    return str(release_source["builder"])


def upstream_discovery_urls(shell: str) -> list[str]:
    metadata = shell_metadata(shell)
    upstream = metadata["upstream"]
    return [str(discovery_url) for discovery_url in upstream["discovery_urls"]]


def upstream_version_pattern(shell: str) -> str:
    metadata = shell_metadata(shell)
    upstream = metadata["upstream"]
    return str(upstream["version_pattern"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect shuck-shells shell metadata.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for command in (
        "display-name",
        "source-kind",
        "build-script",
        "upstream-discovery-urls",
        "upstream-version-pattern",
    ):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("shell")

    subparsers.add_parser("buildable-shells")
    return parser.parse_args()


def main() -> None:
    try:
        args = parse_args()
        if args.command == "display-name":
            print(shell_display_name(args.shell))
            return
        if args.command == "source-kind":
            print(release_source_kind(args.shell))
            return
        if args.command == "build-script":
            print(build_script(args.shell))
            return
        if args.command == "upstream-discovery-urls":
            for discovery_url in upstream_discovery_urls(args.shell):
                print(discovery_url)
            return
        if args.command == "upstream-version-pattern":
            print(upstream_version_pattern(args.shell))
            return
        if args.command == "buildable-shells":
            catalog = load_shell_catalog()
            for shell in catalog:
                if release_source_kind(shell) == "build":
                    print(shell)
            return
        raise SystemExit(f"unsupported command: {args.command}")
    except CatalogError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
