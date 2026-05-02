#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import urllib.request

from index_lib import (
    IndexError,
    build_registry_documents,
    canonicalize_inventory,
    parse_asset_filename,
    parse_release_tag,
    write_registry_documents,
)
from shell_catalog import (
    github_release_asset_rules,
    github_release_repo,
    github_release_tag_version_pattern,
    load_shell_catalog,
    release_source_kind,
)


def github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "shuck-shells-index-builder",
    }
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_json(url: str) -> object:
    request = urllib.request.Request(url, headers=github_headers())
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def iter_releases(repo: str) -> list[dict]:
    releases: list[dict] = []
    page = 1
    while True:
        url = f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}"
        payload = fetch_json(url)
        if not isinstance(payload, list):
            raise IndexError(f"expected a release list from {url}")
        if not payload:
            return releases
        releases.extend(payload)
        page += 1


def fetch_asset_bytes(url: str) -> bytes:
    request = urllib.request.Request(url, headers=github_headers())
    with urllib.request.urlopen(request) as response:
        return response.read()


def asset_sha256(asset: dict, asset_fetcher=fetch_asset_bytes) -> str:
    digest = asset.get("digest")
    if isinstance(digest, str):
        match = re.fullmatch(r"sha256:([0-9a-f]{64})", digest)
        if match:
            return match.group(1)

    asset_url = asset.get("browser_download_url")
    if not isinstance(asset_url, str):
        raise IndexError("release asset is missing `browser_download_url`")
    return hashlib.sha256(asset_fetcher(asset_url)).hexdigest()


def ingest_build_releases(
    shells: dict[str, dict[str, dict[str, dict[str, str]]]],
    releases: list[dict],
    asset_fetcher=fetch_asset_bytes,
) -> None:
    for release in releases:
        if not isinstance(release, dict):
            raise IndexError("release entries must be objects")
        if release.get("draft") or release.get("prerelease"):
            continue
        tag_name = release.get("tag_name")
        if not isinstance(tag_name, str):
            raise IndexError("release is missing `tag_name`")
        shell, version = parse_release_tag(tag_name)
        assets = release.get("assets", [])
        if not isinstance(assets, list):
            raise IndexError(f"release `{tag_name}` has a non-list `assets` field")

        for asset in assets:
            if not isinstance(asset, dict):
                raise IndexError(f"release `{tag_name}` has a non-object asset entry")
            asset_name = asset.get("name")
            asset_url = asset.get("browser_download_url")
            if not isinstance(asset_name, str) or not isinstance(asset_url, str):
                raise IndexError(f"release `{tag_name}` has an invalid asset entry")
            parsed = parse_asset_filename(asset_name)
            if parsed is None:
                continue

            asset_shell, asset_version, platform = parsed
            if asset_shell != shell or asset_version != version:
                raise IndexError(
                    f"asset `{asset_name}` does not match release tag `{tag_name}`"
                )
            if platform in shells[shell][version]:
                raise IndexError(
                    f"duplicate archive for {shell} {version} on {platform}: `{asset_name}`"
                )

            sha256 = asset_sha256(asset, asset_fetcher=asset_fetcher)
            shells[shell][version][platform] = {"url": asset_url, "sha256": sha256}


def ingest_github_release_sources(
    shells: dict[str, dict[str, dict[str, dict[str, str]]]],
    releases_by_repo: dict[str, list[dict]],
    asset_fetcher=fetch_asset_bytes,
) -> None:
    catalog = load_shell_catalog()
    for shell in catalog:
        if release_source_kind(shell) != "github_release":
            continue

        repo = github_release_repo(shell)
        tag_pattern = re.compile(github_release_tag_version_pattern(shell))
        asset_rules = [
            (re.compile(rule["pattern"]), rule["platform"])
            for rule in github_release_asset_rules(shell)
        ]
        try:
            releases = releases_by_repo[repo]
        except KeyError as exc:
            raise IndexError(
                f"missing releases payload for github_release source repo `{repo}`"
            ) from exc

        for release in releases:
            if not isinstance(release, dict):
                raise IndexError(f"release entries for `{repo}` must be objects")
            if release.get("draft") or release.get("prerelease"):
                continue
            tag_name = release.get("tag_name")
            if not isinstance(tag_name, str):
                raise IndexError(f"release in `{repo}` is missing `tag_name`")
            tag_match = tag_pattern.fullmatch(tag_name)
            if tag_match is None:
                continue
            version = tag_match.groupdict().get("version")
            if not version:
                raise IndexError(
                    f"github_release shell `{shell}` tag pattern must capture a `version` group"
                )

            assets = release.get("assets", [])
            if not isinstance(assets, list):
                raise IndexError(f"release `{tag_name}` in `{repo}` has a non-list `assets` field")

            for asset in assets:
                if not isinstance(asset, dict):
                    raise IndexError(
                        f"release `{tag_name}` in `{repo}` has a non-object asset entry"
                    )
                asset_name = asset.get("name")
                asset_url = asset.get("browser_download_url")
                if not isinstance(asset_name, str) or not isinstance(asset_url, str):
                    raise IndexError(f"release `{tag_name}` in `{repo}` has an invalid asset entry")

                matched_platform = None
                for asset_pattern, platform in asset_rules:
                    asset_match = asset_pattern.fullmatch(asset_name)
                    if asset_match is None:
                        continue
                    asset_version = asset_match.groupdict().get("version")
                    if asset_version is not None and asset_version != version:
                        raise IndexError(
                            f"asset `{asset_name}` in `{repo}` does not match release version `{version}`"
                        )
                    matched_platform = platform
                    break

                if matched_platform is None:
                    continue
                if matched_platform in shells[shell][version]:
                    raise IndexError(
                        f"duplicate archive for {shell} {version} on {matched_platform}: `{asset_name}`"
                    )

                sha256 = asset_sha256(asset, asset_fetcher=asset_fetcher)
                shells[shell][version][matched_platform] = {
                    "url": asset_url,
                    "sha256": sha256,
                }


def build_registry(
    releases: list[dict],
    github_release_releases_by_repo: dict[str, list[dict]] | None = None,
    asset_fetcher=fetch_asset_bytes,
) -> dict:
    shells: dict[str, dict[str, dict[str, dict[str, str]]]] = defaultdict(
        lambda: defaultdict(dict)
    )

    ingest_build_releases(shells, releases, asset_fetcher=asset_fetcher)
    if github_release_releases_by_repo is not None:
        ingest_github_release_sources(
            shells,
            github_release_releases_by_repo,
            asset_fetcher=asset_fetcher,
        )

    inventory = {
        shell: {
            version: platforms for version, platforms in versions.items() if platforms
        }
        for shell, versions in shells.items()
        if versions
    }
    return build_registry_documents(canonicalize_inventory(inventory))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build shuck shell archive index JSON.")
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="GitHub repository to scan for releases, in owner/name form",
    )
    parser.add_argument(
        "--releases-file",
        help="Read releases from a local JSON file instead of the GitHub API",
    )
    parser.add_argument(
        "--output-dir",
        default="registry",
        help="Directory to write the generated registry site into",
    )
    parser.add_argument("--output", dest="output_dir", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.releases_file:
        with open(args.releases_file, "r", encoding="utf-8") as handle:
            releases = json.load(handle)
        github_release_releases_by_repo: dict[str, list[dict]] | None = None
    else:
        if not args.repo:
            raise SystemExit("missing --repo and GITHUB_REPOSITORY is not set")
        releases = iter_releases(args.repo)
        github_release_releases_by_repo = {}
        for shell, metadata in load_shell_catalog().items():
            if release_source_kind(shell) != "github_release":
                continue
            repo = str(metadata["release_source"]["repo"])
            if repo not in github_release_releases_by_repo:
                github_release_releases_by_repo[repo] = iter_releases(repo)
    if not isinstance(releases, list):
        raise SystemExit("release payload must be a JSON array")

    documents = build_registry(
        releases,
        github_release_releases_by_repo=github_release_releases_by_repo,
    )
    output_dir = Path(args.output_dir)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    write_registry_documents(output_dir, documents)


if __name__ == "__main__":
    main()
