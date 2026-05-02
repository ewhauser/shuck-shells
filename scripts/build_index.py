#!/usr/bin/env python3
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import urllib.request

from index_lib import IndexError, canonicalize_index, dump_json, parse_asset_filename, parse_release_tag


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


def build_index(releases: list[dict], asset_fetcher=fetch_asset_bytes) -> dict:
    shells: dict[str, dict[str, dict[str, dict[str, str]]]] = defaultdict(
        lambda: defaultdict(dict)
    )

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

            sha256 = hashlib.sha256(asset_fetcher(asset_url)).hexdigest()
            shells[shell][version][platform] = {"url": asset_url, "sha256": sha256}

    raw_index = {
        "version": 1,
        "shells": {
            shell: {
                "versions": {
                    version: {"platforms": platforms}
                    for version, platforms in versions.items()
                    if platforms
                }
            }
            for shell, versions in shells.items()
            if versions
        },
    }
    return canonicalize_index(raw_index)


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
        "--output",
        default="index.json",
        help="Path to write the generated index JSON",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.releases_file:
        with open(args.releases_file, "r", encoding="utf-8") as handle:
            releases = json.load(handle)
    else:
        if not args.repo:
            raise SystemExit("missing --repo and GITHUB_REPOSITORY is not set")
        releases = iter_releases(args.repo)
    if not isinstance(releases, list):
        raise SystemExit("release payload must be a JSON array")

    index = build_index(releases)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dump_json(str(output_path), index)


if __name__ == "__main__":
    main()
