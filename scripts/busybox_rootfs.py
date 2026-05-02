#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import urllib.request

from build_index import github_headers

BUSYBOX_LIBRARY_URL = (
    "https://raw.githubusercontent.com/docker-library/official-images/master/library/busybox"
)

PLATFORM_TARGETS = {
    "x86_64-linux-gnu": {"docker_arch": "amd64", "variant": "glibc"},
    "aarch64-linux-gnu": {"docker_arch": "arm64v8", "variant": "glibc"},
    "x86_64-linux-musl": {"docker_arch": "amd64", "variant": "musl"},
    "aarch64-linux-musl": {"docker_arch": "arm64v8", "variant": "musl"},
}


class BusyBoxRootfsError(ValueError):
    pass


def fetch_text(url: str) -> str:
    request = urllib.request.Request(url, headers=github_headers())
    with urllib.request.urlopen(request) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_library_text(text: str) -> dict[str, object]:
    arch_commits: dict[str, str] = {}
    release_blocks: list[dict[str, object]] = []
    current_block: dict[str, object] | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        commit_match = re.fullmatch(r"([A-Za-z0-9]+)-GitCommit:\s*([0-9a-f]{40})", line)
        if commit_match is not None:
            arch_commits[commit_match.group(1)] = commit_match.group(2)
            continue

        if line.startswith("Tags: "):
            if current_block is not None:
                release_blocks.append(current_block)
            current_block = {
                "tags": [tag.strip() for tag in line.removeprefix("Tags: ").split(",")],
                "directories": {},
            }
            continue

        if current_block is None:
            continue

        if line.startswith("Architectures: "):
            current_block["architectures"] = [
                architecture.strip()
                for architecture in line.removeprefix("Architectures: ").split(",")
            ]
            continue

        directory_match = re.fullmatch(r"([A-Za-z0-9]+)-Directory:\s*(\S+)", line)
        if directory_match is not None:
            directories = current_block["directories"]
            assert isinstance(directories, dict)
            directories[directory_match.group(1)] = directory_match.group(2)

    if current_block is not None:
        release_blocks.append(current_block)

    if not arch_commits:
        raise BusyBoxRootfsError("library metadata did not contain any architecture commits")
    if not release_blocks:
        raise BusyBoxRootfsError("library metadata did not contain any release blocks")

    return {"arch_commits": arch_commits, "release_blocks": release_blocks}


def resolve_rootfs(version: str, platform: str, library_text: str) -> dict[str, str]:
    try:
        target = PLATFORM_TARGETS[platform]
    except KeyError as exc:
        raise BusyBoxRootfsError(f"unsupported busybox platform `{platform}`") from exc

    parsed = parse_library_text(library_text)
    arch_commits = parsed["arch_commits"]
    release_blocks = parsed["release_blocks"]
    assert isinstance(arch_commits, dict)
    assert isinstance(release_blocks, list)

    variant = str(target["variant"])
    docker_arch = str(target["docker_arch"])
    tag_name = f"{version}-{variant}"

    matching_block = None
    for block in release_blocks:
        tags = block["tags"]
        assert isinstance(tags, list)
        if tag_name in tags:
            matching_block = block
            break

    if matching_block is None:
        raise BusyBoxRootfsError(
            f"busybox version `{version}` with variant `{variant}` was not found in Docker metadata"
        )

    directories = matching_block["directories"]
    assert isinstance(directories, dict)
    try:
        directory = str(directories[docker_arch])
    except KeyError as exc:
        raise BusyBoxRootfsError(
            f"busybox version `{version}` variant `{variant}` did not publish `{docker_arch}`"
        ) from exc

    try:
        git_commit = str(arch_commits[docker_arch])
    except KeyError as exc:
        raise BusyBoxRootfsError(
            f"busybox Docker metadata did not include a commit for `{docker_arch}`"
        ) from exc

    rootfs_url = (
        f"https://raw.githubusercontent.com/docker-library/busybox/"
        f"{git_commit}/{directory}/rootfs.tar.gz"
    )

    return {
        "docker_arch": docker_arch,
        "git_commit": git_commit,
        "platform": platform,
        "rootfs_directory": directory,
        "rootfs_url": rootfs_url,
        "variant": variant,
        "version": version,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Resolve Docker BusyBox rootfs archives.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("version")
    resolve_parser.add_argument("platform")
    resolve_parser.add_argument("--field")
    resolve_parser.add_argument(
        "--library-url",
        default=BUSYBOX_LIBRARY_URL,
        help="Docker official-images library metadata URL",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command != "resolve":
        raise SystemExit(f"unsupported command `{args.command}`")

    payload = resolve_rootfs(args.version, args.platform, fetch_text(args.library_url))
    if args.field:
        try:
            print(payload[args.field])
        except KeyError as exc:
            raise SystemExit(f"unknown field `{args.field}`") from exc
        return
    print(json.dumps(payload))


if __name__ == "__main__":
    main()
