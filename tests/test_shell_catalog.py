from __future__ import annotations

from pathlib import Path
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from shell_catalog import (  # noqa: E402
    build_script,
    load_shell_catalog,
    release_source_kind,
    shell_display_name,
)


class ShellCatalogTest(unittest.TestCase):
    def test_catalog_keys_are_sorted_and_contains_expected_shells(self) -> None:
        catalog = load_shell_catalog()
        self.assertEqual(list(catalog.keys()), ["bash", "dash", "mksh", "zsh"])

    def test_buildable_shells_have_build_scripts(self) -> None:
        self.assertEqual(build_script("bash"), "scripts/build_bash_release.sh")
        self.assertEqual(build_script("dash"), "scripts/build_dash_release.sh")
        self.assertEqual(build_script("mksh"), "scripts/build_mksh_release.sh")
        self.assertEqual(build_script("zsh"), "scripts/build_zsh_release.sh")

    def test_temporary_github_release_shell_is_not_buildable(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            catalog_path = Path(tempdir) / "shells.json"
            catalog_path.write_text(
                json.dumps(
                    {
                        "testsh": {
                            "display_name": "testsh",
                            "release_source": {"kind": "github_release"},
                        }
                    }
                ),
                encoding="utf-8",
            )
            old_value = os.environ.get("SHUCK_SHELLS_CATALOG_PATH")
            os.environ["SHUCK_SHELLS_CATALOG_PATH"] = str(catalog_path)
            try:
                self.assertEqual(release_source_kind("testsh"), "github_release")
                with self.assertRaisesRegex(ValueError, "not buildable"):
                    build_script("testsh")
            finally:
                if old_value is None:
                    os.environ.pop("SHUCK_SHELLS_CATALOG_PATH", None)
                else:
                    os.environ["SHUCK_SHELLS_CATALOG_PATH"] = old_value

    def test_shell_display_name(self) -> None:
        self.assertEqual(shell_display_name("bash"), "Bash")
        self.assertEqual(shell_display_name("dash"), "dash")
        self.assertEqual(shell_display_name("mksh"), "mksh")
        self.assertEqual(shell_display_name("zsh"), "Zsh")

    def test_cli_lists_buildable_shells(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        script_path = repo_root / "scripts" / "shell_catalog.py"
        result = subprocess.run(
            [sys.executable, str(script_path), "buildable-shells"],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip().splitlines(), ["bash", "dash", "mksh", "zsh"])


if __name__ == "__main__":
    unittest.main()
