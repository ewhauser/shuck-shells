from __future__ import annotations

from pathlib import Path
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from discover_upstream_versions import (  # noqa: E402
    discover_pending_builds,
    extract_versions_from_text,
    latest_version,
)


class DiscoverUpstreamVersionsTest(unittest.TestCase):
    def test_extract_versions_from_text(self) -> None:
        text = """
        bash-5.2.15.tar.gz
        bash-5.2.21.tar.gz
        bash-5.2.21.tar.gz.sig
        """
        self.assertEqual(
            extract_versions_from_text(text, r"bash-([0-9]+(?:\.[0-9]+)*)\.tar\.gz"),
            ["5.2.15", "5.2.21"],
        )

    def test_latest_version_uses_repo_sorting(self) -> None:
        text = """
        mksh-R59b.tgz
        mksh-R59c.tgz
        """
        self.assertEqual(latest_version(text, r"mksh-(R[0-9][0-9A-Za-z.]*)\.tgz"), "R59c")

    def test_discover_pending_builds_marks_existing_releases(self) -> None:
        catalog = {
            "bash": {
                "display_name": "Bash",
                "release_source": {
                    "kind": "build",
                    "builder": "scripts/build_bash_release.sh",
                    "supported_platforms": ["x86_64-linux-gnu"],
                },
                "upstream": {
                    "discovery_urls": ["https://example.invalid/bash"],
                    "version_pattern": r"bash-([0-9]+(?:\.[0-9]+)*)\.tar\.gz",
                    "source_sha256s": {
                        "5.2.21": "a" * 64,
                    },
                },
            },
            "zsh": {
                "display_name": "Zsh",
                "release_source": {
                    "kind": "build",
                    "builder": "scripts/build_zsh_release.sh",
                    "supported_platforms": ["x86_64-linux-gnu"],
                },
                "upstream": {
                    "discovery_urls": ["https://example.invalid/zsh"],
                    "version_pattern": r"zsh-([0-9]+(?:\.[0-9]+)*)\.tar\.xz",
                    "source_sha256s": {
                        "5.9": "b" * 64,
                    },
                },
            },
        }
        pages = {
            "https://example.invalid/bash": "bash-5.2.15.tar.gz bash-5.2.21.tar.gz",
            "https://example.invalid/zsh": "zsh-5.8.tar.xz zsh-5.9.tar.xz",
        }
        releases = [{"tag_name": "bash-5.2.21"}]

        with tempfile.TemporaryDirectory() as tempdir:
            catalog_path = Path(tempdir) / "shells.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            old_value = os.environ.get("SHUCK_SHELLS_CATALOG_PATH")
            os.environ["SHUCK_SHELLS_CATALOG_PATH"] = str(catalog_path)
            try:
                with patch(
                    "discover_upstream_versions.iter_repo_releases",
                    return_value=releases,
                ):
                    result = discover_pending_builds(
                        "owner/repo",
                        page_fetcher=lambda url: pages[url],
                    )
            finally:
                if old_value is None:
                    os.environ.pop("SHUCK_SHELLS_CATALOG_PATH", None)
                else:
                    os.environ["SHUCK_SHELLS_CATALOG_PATH"] = old_value

        self.assertEqual(
            result["pending_builds"],
            [
                {
                    "shell": "zsh",
                    "version": "5.9",
                    "source_sha256s": {"x86_64-linux-gnu": "b" * 64},
                }
            ],
        )
        self.assertEqual(
            result["discovered"],
            [
                {
                    "shell": "bash",
                    "version": "5.2.21",
                    "release_tag": "bash-5.2.21",
                    "discovery_url": "https://example.invalid/bash",
                    "release_exists": True,
                    "source_sha256s": {"x86_64-linux-gnu": "a" * 64},
                },
                {
                    "shell": "zsh",
                    "version": "5.9",
                    "release_tag": "zsh-5.9",
                    "discovery_url": "https://example.invalid/zsh",
                    "release_exists": False,
                    "source_sha256s": {"x86_64-linux-gnu": "b" * 64},
                },
            ],
        )

    def test_discover_pending_builds_keeps_going_when_one_upstream_fails(self) -> None:
        catalog = {
            "bash": {
                "display_name": "Bash",
                "release_source": {
                    "kind": "build",
                    "builder": "scripts/build_bash_release.sh",
                    "supported_platforms": ["x86_64-linux-gnu"],
                },
                "upstream": {
                    "discovery_urls": ["https://example.invalid/bash"],
                    "version_pattern": r"bash-([0-9]+(?:\.[0-9]+)*)\.tar\.gz",
                    "source_sha256s": {},
                },
            },
            "zsh": {
                "display_name": "Zsh",
                "release_source": {
                    "kind": "build",
                    "builder": "scripts/build_zsh_release.sh",
                    "supported_platforms": ["x86_64-linux-gnu"],
                },
                "upstream": {
                    "discovery_urls": ["https://example.invalid/zsh"],
                    "version_pattern": r"zsh-([0-9]+(?:\.[0-9]+)*)\.tar\.xz",
                    "source_sha256s": {
                        "5.9": "b" * 64,
                    },
                },
            },
        }

        with tempfile.TemporaryDirectory() as tempdir:
            catalog_path = Path(tempdir) / "shells.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            old_value = os.environ.get("SHUCK_SHELLS_CATALOG_PATH")
            os.environ["SHUCK_SHELLS_CATALOG_PATH"] = str(catalog_path)
            try:
                with patch(
                    "discover_upstream_versions.iter_repo_releases",
                    return_value=[],
                ):
                    result = discover_pending_builds(
                        "owner/repo",
                        page_fetcher=lambda url: (
                            "zsh-5.9.tar.xz" if url.endswith("/zsh") else (_ for _ in ()).throw(RuntimeError("boom"))
                        ),
                    )
            finally:
                if old_value is None:
                    os.environ.pop("SHUCK_SHELLS_CATALOG_PATH", None)
                else:
                    os.environ["SHUCK_SHELLS_CATALOG_PATH"] = old_value

        self.assertEqual(
            result["pending_builds"],
            [
                {
                    "shell": "zsh",
                    "version": "5.9",
                    "source_sha256s": {"x86_64-linux-gnu": "b" * 64},
                }
            ],
        )
        self.assertEqual(
            result["discovered"],
            [
                {
                    "shell": "bash",
                    "discovery_urls": ["https://example.invalid/bash"],
                    "error": "boom",
                },
                {
                    "shell": "zsh",
                    "version": "5.9",
                    "release_tag": "zsh-5.9",
                    "discovery_url": "https://example.invalid/zsh",
                    "release_exists": False,
                    "source_sha256s": {"x86_64-linux-gnu": "b" * 64},
                },
            ],
        )

    def test_discover_pending_builds_skips_missing_source_sha256(self) -> None:
        catalog = {
            "bash": {
                "display_name": "Bash",
                "release_source": {
                    "kind": "build",
                    "builder": "scripts/build_bash_release.sh",
                    "supported_platforms": ["x86_64-linux-gnu"],
                },
                "upstream": {
                    "discovery_urls": ["https://example.invalid/bash"],
                    "version_pattern": r"bash-([0-9]+(?:\.[0-9]+)*)\.tar\.gz",
                    "source_sha256s": {},
                },
            },
        }

        with tempfile.TemporaryDirectory() as tempdir:
            catalog_path = Path(tempdir) / "shells.json"
            catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
            old_value = os.environ.get("SHUCK_SHELLS_CATALOG_PATH")
            os.environ["SHUCK_SHELLS_CATALOG_PATH"] = str(catalog_path)
            try:
                with patch(
                    "discover_upstream_versions.iter_repo_releases",
                    return_value=[],
                ):
                    result = discover_pending_builds(
                        "owner/repo",
                        page_fetcher=lambda url: "bash-5.3.tar.gz",
                    )
            finally:
                if old_value is None:
                    os.environ.pop("SHUCK_SHELLS_CATALOG_PATH", None)
                else:
                    os.environ["SHUCK_SHELLS_CATALOG_PATH"] = old_value

        self.assertEqual(result["pending_builds"], [])
        self.assertEqual(
            result["discovered"],
            [
                {
                    "shell": "bash",
                    "version": "5.3",
                    "release_tag": "bash-5.3",
                    "discovery_url": "https://example.invalid/bash",
                    "release_exists": False,
                    "source_sha256_missing": True,
                    "error": "shell `bash` version `5.3` is missing upstream source_sha256",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
