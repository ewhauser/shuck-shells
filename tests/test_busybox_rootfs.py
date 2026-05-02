from __future__ import annotations

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from busybox_rootfs import (  # noqa: E402
    BusyBoxRootfsError,
    parse_library_text,
    resolve_rootfs,
)


LIBRARY_TEXT = """
# https://github.com/docker-library/busybox/tree/dist-amd64
amd64-GitFetch: refs/heads/dist-amd64
amd64-GitCommit: c1375496373e76f680b1ef5f713500e98921a45c
# https://github.com/docker-library/busybox/tree/dist-arm64v8
arm64v8-GitFetch: refs/heads/dist-arm64v8
arm64v8-GitCommit: b6ab7c14ba46700181395f420545aee1ab297934

Tags: 1.37.0-glibc, 1.37-glibc, 1-glibc, unstable-glibc, glibc
Architectures: amd64, arm64v8
amd64-Directory: latest/glibc/amd64
arm64v8-Directory: latest/glibc/arm64v8

Tags: 1.37.0-musl, 1.37-musl, 1-musl, unstable-musl, musl
Architectures: amd64, arm64v8
amd64-Directory: latest/musl/amd64
arm64v8-Directory: latest/musl/arm64v8

Tags: 1.36.1-glibc, 1.36-glibc, stable-glibc
Architectures: amd64, arm64v8
amd64-Directory: latest-1/glibc/amd64
arm64v8-Directory: latest-1/glibc/arm64v8
"""


class BusyBoxRootfsTest(unittest.TestCase):
    def test_parse_library_text(self) -> None:
        parsed = parse_library_text(LIBRARY_TEXT)
        self.assertEqual(
            parsed["arch_commits"],
            {
                "amd64": "c1375496373e76f680b1ef5f713500e98921a45c",
                "arm64v8": "b6ab7c14ba46700181395f420545aee1ab297934",
            },
        )
        self.assertEqual(len(parsed["release_blocks"]), 3)

    def test_resolve_musl_rootfs(self) -> None:
        resolved = resolve_rootfs("1.37.0", "aarch64-linux-musl", LIBRARY_TEXT)
        self.assertEqual(resolved["variant"], "musl")
        self.assertEqual(resolved["docker_arch"], "arm64v8")
        self.assertEqual(
            resolved["rootfs_url"],
            "https://raw.githubusercontent.com/docker-library/busybox/"
            "b6ab7c14ba46700181395f420545aee1ab297934/latest/musl/arm64v8/rootfs.tar.gz",
        )

    def test_resolve_x86_64_musl_rootfs(self) -> None:
        resolved = resolve_rootfs("1.37.0", "x86_64-linux-musl", LIBRARY_TEXT)
        self.assertEqual(resolved["variant"], "musl")
        self.assertEqual(resolved["docker_arch"], "amd64")
        self.assertEqual(
            resolved["rootfs_url"],
            "https://raw.githubusercontent.com/docker-library/busybox/"
            "c1375496373e76f680b1ef5f713500e98921a45c/latest/musl/amd64/rootfs.tar.gz",
        )

    def test_rejects_missing_version(self) -> None:
        with self.assertRaisesRegex(BusyBoxRootfsError, "was not found"):
            resolve_rootfs("1.35.0", "x86_64-linux-musl", LIBRARY_TEXT)

    def test_rejects_unsupported_platform(self) -> None:
        with self.assertRaisesRegex(BusyBoxRootfsError, "unsupported busybox platform"):
            resolve_rootfs("1.37.0", "x86_64-linux-gnu", LIBRARY_TEXT)


if __name__ == "__main__":
    unittest.main()
