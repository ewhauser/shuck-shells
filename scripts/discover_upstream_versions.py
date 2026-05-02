#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
from typing import Callable
import urllib.request

from build_index import github_headers
from index_lib import IndexError, version_sort_key
from shell_catalog import CatalogError, load_shell_catalog, release_source_kind, upstream_source_sha256s


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers=github_headers())
    with urllib.request.urlopen(request) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_json(url: str) -> object:
    request = urllib.request.Request(url, headers=github_headers())
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def iter_repo_releases(repo: str) -> list[dict]:
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


def extract_versions_from_text(text: str, version_pattern: str) -> list[str]:
    regex = re.compile(version_pattern)
    raw_matches = regex.findall(text)
    versions: list[str] = []
    seen: set[str] = set()
    for match in raw_matches:
        if isinstance(match, tuple):
            version = str(match[0])
        else:
            version = str(match)
        if version in seen:
            continue
        seen.add(version)
        versions.append(version)
    return versions


def latest_version(text: str, version_pattern: str) -> str:
    versions = extract_versions_from_text(text, version_pattern)
    if not versions:
        raise IndexError(f"no upstream versions matched `{version_pattern}`")
    return sorted(set(versions), key=version_sort_key, reverse=True)[0]


def existing_release_tags(releases: list[dict]) -> set[str]:
    tags: set[str] = set()
    for release in releases:
        if not isinstance(release, dict):
            raise IndexError("release entries must be objects")
        tag_name = release.get("tag_name")
        if isinstance(tag_name, str):
            tags.add(tag_name)
    return tags


def discover_pending_builds(
    repo: str,
    page_fetcher: Callable[[str], str] = fetch_text,
) -> dict[str, object]:
    catalog = load_shell_catalog()
    releases = iter_repo_releases(repo)
    tags = existing_release_tags(releases)

    discovered: list[dict[str, object]] = []
    pending_builds: list[dict[str, str]] = []

    for shell, metadata in catalog.items():
        if release_source_kind(shell) != "build":
            continue
        upstream = metadata["upstream"]
        discovery_urls = [str(discovery_url) for discovery_url in upstream["discovery_urls"]]
        version_pattern = str(upstream["version_pattern"])
        last_error: str | None = None
        for discovery_url in discovery_urls:
            try:
                text = page_fetcher(discovery_url)
                version = latest_version(text, version_pattern)
                release_tag = f"{shell}-{version}"
                release_exists = release_tag in tags
                entry = {
                    "shell": shell,
                    "version": version,
                    "release_tag": release_tag,
                    "discovery_url": discovery_url,
                    "release_exists": release_exists,
                }
                try:
                    source_sha256s = upstream_source_sha256s(shell, version)
                    entry["source_sha256s"] = source_sha256s
                    if not release_exists:
                        pending_builds.append(
                            {
                                "shell": shell,
                                "version": version,
                                "source_sha256s": source_sha256s,
                            }
                        )
                except CatalogError as exc:
                    entry["source_sha256_missing"] = True
                    entry["error"] = str(exc)
                discovered.append(entry)
                break
            except Exception as exc:
                last_error = str(exc)
        else:
            discovered.append(
                {
                    "shell": shell,
                    "discovery_urls": discovery_urls,
                    "error": last_error or "unknown discovery failure",
                }
            )

    return {"discovered": discovered, "pending_builds": pending_builds}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Discover latest upstream shell releases and determine which builds are missing."
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="GitHub repository to check for existing releases, in owner/name form",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print the JSON result",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.repo:
        raise SystemExit("missing --repo and GITHUB_REPOSITORY is not set")
    result = discover_pending_builds(args.repo)
    if args.pretty:
        print(json.dumps(result, indent=2))
    else:
        print(json.dumps(result))


if __name__ == "__main__":
    main()
