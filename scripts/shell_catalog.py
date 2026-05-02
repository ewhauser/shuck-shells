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
        if source_kind == "github_release":
            repo = release_source.get("repo")
            tag_version_pattern = release_source.get("tag_version_pattern")
            assets = release_source.get("assets")
            if (
                not isinstance(repo, str)
                or "/" not in repo
                or repo.startswith("/")
                or repo.endswith("/")
            ):
                raise CatalogError(
                    f"shell catalog entry `{shell}` must define a GitHub owner/name repo for github_release sources"
                )
            if not isinstance(tag_version_pattern, str) or not tag_version_pattern:
                raise CatalogError(
                    f"shell catalog entry `{shell}` must define a tag_version_pattern for github_release sources"
                )
            if not isinstance(assets, list) or not assets:
                raise CatalogError(
                    f"shell catalog entry `{shell}` must define non-empty asset rules for github_release sources"
                )
            for asset_rule in assets:
                if not isinstance(asset_rule, dict):
                    raise CatalogError(
                        f"shell catalog entry `{shell}` has a non-object github_release asset rule"
                    )
                pattern = asset_rule.get("pattern")
                platform = asset_rule.get("platform")
                if not isinstance(pattern, str) or not pattern:
                    raise CatalogError(
                        f"shell catalog entry `{shell}` has a github_release asset rule without a pattern"
                    )
                if not isinstance(platform, str) or not platform:
                    raise CatalogError(
                        f"shell catalog entry `{shell}` has a github_release asset rule without a platform"
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


def github_release_repo(shell: str) -> str:
    metadata = shell_metadata(shell)
    release_source = metadata["release_source"]
    source_kind = release_source["kind"]
    if source_kind != "github_release":
        raise CatalogError(
            f"shell `{shell}` uses release source kind `{source_kind}` and is not sourced from GitHub releases"
        )
    return str(release_source["repo"])


def github_release_tag_version_pattern(shell: str) -> str:
    metadata = shell_metadata(shell)
    release_source = metadata["release_source"]
    source_kind = release_source["kind"]
    if source_kind != "github_release":
        raise CatalogError(
            f"shell `{shell}` uses release source kind `{source_kind}` and is not sourced from GitHub releases"
        )
    return str(release_source["tag_version_pattern"])


def github_release_asset_rules(shell: str) -> list[dict[str, str]]:
    metadata = shell_metadata(shell)
    release_source = metadata["release_source"]
    source_kind = release_source["kind"]
    if source_kind != "github_release":
        raise CatalogError(
            f"shell `{shell}` uses release source kind `{source_kind}` and is not sourced from GitHub releases"
        )
    asset_rules = []
    for asset_rule in release_source["assets"]:
        asset_rules.append(
            {
                "pattern": str(asset_rule["pattern"]),
                "platform": str(asset_rule["platform"]),
            }
        )
    return asset_rules


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
        "github-release-repo",
        "github-release-tag-version-pattern",
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
        if args.command == "github-release-repo":
            print(github_release_repo(args.shell))
            return
        if args.command == "github-release-tag-version-pattern":
            print(github_release_tag_version_pattern(args.shell))
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
