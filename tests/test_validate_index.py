from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import textwrap
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from index_lib import IndexError  # noqa: E402
from validate_index import validate_index_file  # noqa: E402


class ValidateIndexTest(unittest.TestCase):
    def write_temp_index(self, body: str) -> str:
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        with handle:
            handle.write(textwrap.dedent(body).strip() + "\n")
        return handle.name

    def test_validate_accepts_canonical_index(self) -> None:
        path = self.write_temp_index(
            """
            {
              "version": 1,
              "shells": {
                "bash": {
                  "versions": {
                    "5.2.21": {
                      "platforms": {
                        "x86_64-linux": {
                          "url": "https://example.invalid/bash-5.2.21-x86_64-linux.tar.gz",
                          "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                        }
                      }
                    }
                  }
                }
              }
            }
            """
        )
        validate_index_file(path)

    def test_validate_rejects_duplicate_keys(self) -> None:
        path = self.write_temp_index(
            """
            {
              "version": 1,
              "version": 2,
              "shells": {}
            }
            """
        )
        with self.assertRaises(IndexError):
            validate_index_file(path)

    def test_validate_rejects_unsorted_versions(self) -> None:
        path = self.write_temp_index(
            """
            {
              "version": 1,
              "shells": {
                "bash": {
                  "versions": {
                    "5.1.16": {
                      "platforms": {
                        "x86_64-linux": {
                          "url": "https://example.invalid/bash-5.1.16-x86_64-linux.tar.gz",
                          "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                        }
                      }
                    },
                    "5.2.21": {
                      "platforms": {
                        "x86_64-linux": {
                          "url": "https://example.invalid/bash-5.2.21-x86_64-linux.tar.gz",
                          "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
                        }
                      }
                    }
                  }
                }
              }
            }
            """
        )
        with self.assertRaises(IndexError):
            validate_index_file(path)

    def test_validate_rejects_invalid_sha256(self) -> None:
        path = self.write_temp_index(
            """
            {
              "version": 1,
              "shells": {
                "bash": {
                  "versions": {
                    "5.2.21": {
                      "platforms": {
                        "x86_64-linux": {
                          "url": "https://example.invalid/bash-5.2.21-x86_64-linux.tar.gz",
                          "sha256": "not-a-digest"
                        }
                      }
                    }
                  }
                }
              }
            }
            """
        )
        with self.assertRaises(IndexError):
            validate_index_file(path)

    def test_validate_rejects_unsupported_platform(self) -> None:
        path = self.write_temp_index(
            """
            {
              "version": 1,
              "shells": {
                "bash": {
                  "versions": {
                    "5.2.21": {
                      "platforms": {
                        "ppc64le-linux": {
                          "url": "https://example.invalid/bash-5.2.21-ppc64le-linux.tar.gz",
                          "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                        }
                      }
                    }
                  }
                }
              }
            }
            """
        )
        with self.assertRaises(IndexError):
            validate_index_file(path)

    def test_validate_rejects_non_https_url(self) -> None:
        path = self.write_temp_index(
            """
            {
              "version": 1,
              "shells": {
                "bash": {
                  "versions": {
                    "5.2.21": {
                      "platforms": {
                        "x86_64-linux": {
                          "url": "http://example.invalid/bash-5.2.21-x86_64-linux.tar.gz",
                          "sha256": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
                        }
                      }
                    }
                  }
                }
              }
            }
            """
        )
        with self.assertRaises(IndexError):
            validate_index_file(path)


if __name__ == "__main__":
    unittest.main()
