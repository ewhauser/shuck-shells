from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from index_lib import IndexError  # noqa: E402
from validate_index import validate_registry  # noqa: E402


class ValidateIndexTest(unittest.TestCase):
    def write_file(self, root: Path, relative_path: str, body: str) -> None:
        target = root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body.strip() + "\n", encoding="utf-8")

    def write_valid_registry(self, root: Path) -> None:
        self.write_file(
            root,
            "index.json",
            """
{
  "version": 2,
  "kind": "shuck.shells.index",
  "shells": {
    "bash": {
      "versions_url": "shells/bash/index.json"
    }
  }
}
            """,
        )
        self.write_file(
            root,
            "shells/bash/index.json",
            """
{
  "version": 2,
  "kind": "shuck.shells.versions",
  "shell": "bash",
  "versions": {
    "5.2.21": {
      "manifest_url": "5.2.21.json"
    }
  }
}
            """,
        )
        self.write_file(
            root,
            "shells/bash/5.2.21.json",
            """
{
  "version": 2,
  "kind": "shuck.shells.release",
  "shell": "bash",
  "release": "5.2.21",
  "platforms": {
    "x86_64-linux": {
      "url": "https://example.invalid/bash-5.2.21-x86_64-linux.tar.gz",
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  }
}
            """,
        )

    def test_validate_accepts_canonical_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_valid_registry(root)
            validate_registry(str(root))

    def test_validate_rejects_duplicate_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_file(
                root,
                "index.json",
                """
{
  "version": 2,
  "version": 3,
  "kind": "shuck.shells.index",
  "shells": {}
}
                """,
            )
            with self.assertRaises(IndexError):
                validate_registry(str(root))

    def test_validate_rejects_unsorted_versions(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_valid_registry(root)
            self.write_file(
                root,
                "shells/bash/index.json",
                """
{
  "version": 2,
  "kind": "shuck.shells.versions",
  "shell": "bash",
  "versions": {
    "5.1.16": {
      "manifest_url": "5.1.16.json"
    },
    "5.2.21": {
      "manifest_url": "5.2.21.json"
    }
  }
}
                """,
            )
            self.write_file(
                root,
                "shells/bash/5.1.16.json",
                """
{
  "version": 2,
  "kind": "shuck.shells.release",
  "shell": "bash",
  "release": "5.1.16",
  "platforms": {
    "x86_64-linux": {
      "url": "https://example.invalid/bash-5.1.16-x86_64-linux.tar.gz",
      "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
    }
  }
}
                """,
            )
            with self.assertRaises(IndexError):
                validate_registry(str(root))

    def test_validate_rejects_invalid_sha256(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_valid_registry(root)
            self.write_file(
                root,
                "shells/bash/5.2.21.json",
                """
{
  "version": 2,
  "kind": "shuck.shells.release",
  "shell": "bash",
  "release": "5.2.21",
  "platforms": {
    "x86_64-linux": {
      "url": "https://example.invalid/bash-5.2.21-x86_64-linux.tar.gz",
      "sha256": "not-a-digest"
    }
  }
}
                """,
            )
            with self.assertRaises(IndexError):
                validate_registry(str(root))

    def test_validate_rejects_unsupported_platform(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_valid_registry(root)
            self.write_file(
                root,
                "shells/bash/5.2.21.json",
                """
{
  "version": 2,
  "kind": "shuck.shells.release",
  "shell": "bash",
  "release": "5.2.21",
  "platforms": {
    "ppc64le-linux": {
      "url": "https://example.invalid/bash-5.2.21-ppc64le-linux.tar.gz",
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  }
}
                """,
            )
            with self.assertRaises(IndexError):
                validate_registry(str(root))

    def test_validate_rejects_non_https_url(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_valid_registry(root)
            self.write_file(
                root,
                "shells/bash/5.2.21.json",
                """
{
  "version": 2,
  "kind": "shuck.shells.release",
  "shell": "bash",
  "release": "5.2.21",
  "platforms": {
    "x86_64-linux": {
      "url": "http://example.invalid/bash-5.2.21-x86_64-linux.tar.gz",
      "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
    }
  }
}
                """,
            )
            with self.assertRaises(IndexError):
                validate_registry(str(root))

    def test_validate_rejects_missing_referenced_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self.write_file(
                root,
                "index.json",
                """
{
  "version": 2,
  "kind": "shuck.shells.index",
  "shells": {
    "bash": {
      "versions_url": "shells/bash/index.json"
    }
  }
}
                """,
            )
            self.write_file(
                root,
                "shells/bash/index.json",
                """
{
  "version": 2,
  "kind": "shuck.shells.versions",
  "shell": "bash",
  "versions": {
    "5.2.21": {
      "manifest_url": "5.2.21.json"
    }
  }
}
                """,
            )
            with self.assertRaises(IndexError):
                validate_registry(str(root))


if __name__ == "__main__":
    unittest.main()
