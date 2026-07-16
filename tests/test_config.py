from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401
from dci.config import resolve_pi_paths


class PiPathConfigTests(unittest.TestCase):
    def test_new_pi_directory_is_preferred(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            (root / "pi").mkdir()
            (root / "pi-mono").mkdir()
            with patch.dict(os.environ, {}, clear=True):
                paths = resolve_pi_paths(root)

        self.assertEqual(paths.repo_dir, root / "pi")
        self.assertEqual(paths.package_dir, root / "pi" / "packages" / "coding-agent")
        self.assertEqual(paths.agent_dir, root / "pi" / ".pi" / "agent")

    def test_legacy_pi_mono_directory_is_a_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            (root / "pi-mono").mkdir()
            with patch.dict(os.environ, {}, clear=True):
                paths = resolve_pi_paths(root)

        self.assertEqual(paths.repo_dir, root / "pi-mono")

    def test_environment_can_override_all_pi_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            environment = {
                "DCI_PI_DIR": "vendor/pi",
                "DCI_PI_PACKAGE_DIR": "build/coding-agent",
                "DCI_PI_AGENT_DIR": "runtime/pi-agent",
            }
            with patch.dict(os.environ, environment, clear=True):
                paths = resolve_pi_paths(root)

        self.assertEqual(paths.repo_dir, root / "vendor" / "pi")
        self.assertEqual(paths.package_dir, root / "build" / "coding-agent")
        self.assertEqual(paths.agent_dir, root / "runtime" / "pi-agent")


if __name__ == "__main__":
    unittest.main()
