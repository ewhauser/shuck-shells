from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_index import build_index  # noqa: E402
from index_lib import IndexError  # noqa: E402


class BuildIndexTest(unittest.TestCase):
    def test_build_index_hashes_assets_and_sorts_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            older = temp / "bash-5.1.16-x86_64-linux.tar.gz"
            newer = temp / "bash-5.2.21-x86_64-linux.tar.gz"
            older.write_bytes(b"older")
            newer.write_bytes(b"newer")

            releases = [
                {
                    "tag_name": "bash-5.1.16",
                    "draft": False,
                    "prerelease": False,
                    "assets": [
                        {
                            "name": older.name,
                            "browser_download_url": older.as_uri(),
                        }
                    ],
                },
                {
                    "tag_name": "bash-5.2.21",
                    "draft": False,
                    "prerelease": False,
                    "assets": [
                        {
                            "name": newer.name,
                            "browser_download_url": newer.as_uri(),
                        }
                    ],
                },
            ]

            index = build_index(releases)

            self.assertEqual(list(index["shells"].keys()), ["bash"])
            self.assertEqual(
                list(index["shells"]["bash"]["versions"].keys()),
                ["5.2.21", "5.1.16"],
            )
            self.assertEqual(
                index["shells"]["bash"]["versions"]["5.2.21"]["platforms"]["x86_64-linux"][
                    "sha256"
                ],
                hashlib.sha256(b"newer").hexdigest(),
            )

    def test_build_index_rejects_mismatched_asset_version(self) -> None:
        releases = [
            {
                "tag_name": "bash-5.2.21",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "bash-5.1.16-x86_64-linux.tar.gz",
                        "browser_download_url": "https://example.invalid/bash-5.1.16-x86_64-linux.tar.gz",
                    }
                ],
            }
        ]

        with self.assertRaises(IndexError):
            build_index(releases, asset_fetcher=lambda _: b"ignored")

    def test_build_index_rejects_duplicate_platform_assets(self) -> None:
        releases = [
            {
                "tag_name": "bash-5.2.21",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "bash-5.2.21-x86_64-linux.tar.gz",
                        "browser_download_url": "https://example.invalid/bash-5.2.21-x86_64-linux.tar.gz",
                    },
                    {
                        "name": "bash-5.2.21-x86_64-linux.tar.gz",
                        "browser_download_url": "https://example.invalid/bash-5.2.21-x86_64-linux-alt.tar.gz",
                    },
                ],
            }
        ]

        with self.assertRaises(IndexError):
            build_index(releases, asset_fetcher=lambda _: b"ignored")

    def test_build_index_skips_draft_and_prerelease_entries(self) -> None:
        releases = [
            {
                "tag_name": "bash-5.2.21",
                "draft": True,
                "prerelease": False,
                "assets": [
                    {
                        "name": "bash-5.2.21-x86_64-linux.tar.gz",
                        "browser_download_url": "https://example.invalid/bash-5.2.21-x86_64-linux.tar.gz",
                    }
                ],
            },
            {
                "tag_name": "bash-5.2.22",
                "draft": False,
                "prerelease": True,
                "assets": [
                    {
                        "name": "bash-5.2.22-x86_64-linux.tar.gz",
                        "browser_download_url": "https://example.invalid/bash-5.2.22-x86_64-linux.tar.gz",
                    }
                ],
            },
        ]

        index = build_index(releases, asset_fetcher=lambda _: b"ignored")
        self.assertEqual(index["shells"], {})

    def test_build_index_rejects_invalid_release_tag(self) -> None:
        releases = [
            {
                "tag_name": "fish-3.7.1",
                "draft": False,
                "prerelease": False,
                "assets": [],
            }
        ]

        with self.assertRaises(IndexError):
            build_index(releases, asset_fetcher=lambda _: b"ignored")

    def test_build_index_ignores_non_matching_assets(self) -> None:
        releases = [
            {
                "tag_name": "bash-5.2.21",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "notes.txt",
                        "browser_download_url": "https://example.invalid/notes.txt",
                    }
                ],
            }
        ]

        index = build_index(releases, asset_fetcher=lambda _: b"ignored")
        self.assertEqual(index["shells"], {})

    def test_build_index_cli_writes_index_from_releases_file(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "build_index.py"
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            asset_path = temp / "bash-5.2.21-x86_64-linux.tar.gz"
            asset_path.write_bytes(b"cli-fixture")
            releases_path = temp / "releases.json"
            output_path = temp / "index.json"
            releases_path.write_text(
                (
                    "["
                    "{"
                    "\"tag_name\": \"bash-5.2.21\","
                    "\"draft\": false,"
                    "\"prerelease\": false,"
                    "\"assets\": ["
                    "{"
                    f"\"name\": \"{asset_path.name}\","
                    f"\"browser_download_url\": \"{asset_path.as_uri()}\""
                    "}"
                    "]"
                    "}"
                    "]"
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--releases-file",
                    str(releases_path),
                    "--output",
                    str(output_path),
                ],
                check=True,
            )

            self.assertIn("\"bash\"", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
