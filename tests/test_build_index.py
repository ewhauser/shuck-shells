from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_index import build_registry  # noqa: E402
from index_lib import IndexError  # noqa: E402


class BuildIndexTest(unittest.TestCase):
    def test_build_registry_hashes_assets_and_sorts_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            older = temp / "bash-5.1.16-x86_64-linux-gnu.tar.gz"
            newer = temp / "bash-5.2.21-x86_64-linux-gnu.tar.gz"
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

            documents = build_registry(releases)

            root_index = documents["index.json"]
            self.assertEqual(list(root_index["shells"].keys()), ["bash"])
            self.assertEqual(
                list(documents["shells/bash/index.json"]["versions"].keys()),
                ["5.2.21", "5.1.16"],
            )
            self.assertEqual(
                documents["shells/bash/5.2.21.json"]["platforms"]["x86_64-linux-gnu"]["sha256"],
                hashlib.sha256(b"newer").hexdigest(),
            )
            self.assertEqual(
                root_index["shells"]["bash"]["versions_url"],
                "shells/bash/index.json",
            )

    def test_build_registry_rejects_mismatched_asset_version(self) -> None:
        releases = [
            {
                "tag_name": "bash-5.2.21",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "bash-5.1.16-x86_64-linux-gnu.tar.gz",
                        "browser_download_url": "https://example.invalid/bash-5.1.16-x86_64-linux-gnu.tar.gz",
                    }
                ],
            }
        ]

        with self.assertRaises(IndexError):
            build_registry(releases, asset_fetcher=lambda _: b"ignored")

    def test_build_registry_rejects_duplicate_platform_assets(self) -> None:
        releases = [
            {
                "tag_name": "bash-5.2.21",
                "draft": False,
                "prerelease": False,
                "assets": [
                    {
                        "name": "bash-5.2.21-x86_64-linux-gnu.tar.gz",
                        "browser_download_url": "https://example.invalid/bash-5.2.21-x86_64-linux-gnu.tar.gz",
                    },
                    {
                        "name": "bash-5.2.21-x86_64-linux-gnu.tar.gz",
                        "browser_download_url": "https://example.invalid/bash-5.2.21-x86_64-linux-gnu-alt.tar.gz",
                    },
                ],
            }
        ]

        with self.assertRaises(IndexError):
            build_registry(releases, asset_fetcher=lambda _: b"ignored")

    def test_build_registry_skips_draft_and_prerelease_entries(self) -> None:
        releases = [
            {
                "tag_name": "bash-5.2.21",
                "draft": True,
                "prerelease": False,
                "assets": [
                    {
                        "name": "bash-5.2.21-x86_64-linux-gnu.tar.gz",
                        "browser_download_url": "https://example.invalid/bash-5.2.21-x86_64-linux-gnu.tar.gz",
                    }
                ],
            },
            {
                "tag_name": "bash-5.2.22",
                "draft": False,
                "prerelease": True,
                "assets": [
                    {
                        "name": "bash-5.2.22-x86_64-linux-gnu.tar.gz",
                        "browser_download_url": "https://example.invalid/bash-5.2.22-x86_64-linux-gnu.tar.gz",
                    }
                ],
            },
        ]

        documents = build_registry(releases, asset_fetcher=lambda _: b"ignored")
        self.assertEqual(documents["index.json"]["shells"], {})

    def test_build_registry_rejects_invalid_release_tag(self) -> None:
        releases = [
            {
                "tag_name": "fish-3.7.1",
                "draft": False,
                "prerelease": False,
                "assets": [],
            }
        ]

        with self.assertRaises(IndexError):
            build_registry(releases, asset_fetcher=lambda _: b"ignored")

    def test_build_registry_ignores_non_matching_assets(self) -> None:
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

        documents = build_registry(releases, asset_fetcher=lambda _: b"ignored")
        self.assertEqual(documents["index.json"]["shells"], {})

    def test_build_registry_cli_writes_site_from_releases_file(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "build_index.py"
        with tempfile.TemporaryDirectory() as tempdir:
            temp = Path(tempdir)
            asset_path = temp / "bash-5.2.21-x86_64-linux-gnu.tar.gz"
            asset_path.write_bytes(b"cli-fixture")
            releases_path = temp / "releases.json"
            output_dir = temp / "registry"
            releases_path.write_text(
                json.dumps(
                    [
                        {
                            "tag_name": "bash-5.2.21",
                            "draft": False,
                            "prerelease": False,
                            "assets": [
                                {
                                    "name": asset_path.name,
                                    "browser_download_url": asset_path.as_uri(),
                                }
                            ],
                        }
                    ]
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(script_path),
                    "--releases-file",
                    str(releases_path),
                    "--output-dir",
                    str(output_dir),
                ],
                check=True,
            )

            self.assertTrue((output_dir / "index.json").is_file())
            self.assertTrue((output_dir / "shells" / "bash" / "index.json").is_file())
            self.assertTrue((output_dir / "shells" / "bash" / "5.2.21.json").is_file())


if __name__ == "__main__":
    unittest.main()
