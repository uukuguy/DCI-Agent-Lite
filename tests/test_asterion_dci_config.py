from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.dci.config import load_asterion_dci_env, resolve_dci_paths


class AsterionDciConfigTests(unittest.TestCase):
    def test_uses_only_asterion_dci_path_namespace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            environment = {
                "ASTERION_DCI_PI_DIR": "vendor/pi",
                "ASTERION_DCI_PI_PACKAGE_DIR": "build/coding-agent",
                "ASTERION_DCI_PI_AGENT_DIR": "state/pi-agent",
                "ASTERION_DCI_OUTPUT_ROOT": "asterion-runs",
                "DCI_PI_DIR": "must-not-be-used",
            }
            with patch.dict(os.environ, environment, clear=True):
                paths = resolve_dci_paths(root)

        self.assertEqual(paths.pi.repo_dir, root / "vendor/pi")
        self.assertEqual(paths.pi.package_dir, root / "build/coding-agent")
        self.assertEqual(paths.pi.agent_dir, root / "state/pi-agent")
        self.assertEqual(paths.output_root, root / "asterion-runs")

    def test_defaults_never_select_legacy_dci_locations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            (root / "pi-mono").mkdir()
            with patch.dict(os.environ, {}, clear=True):
                paths = resolve_dci_paths(root)

        self.assertEqual(paths.pi.repo_dir, root / "pi")
        self.assertEqual(paths.pi.package_dir, root / "pi/packages/coding-agent")
        self.assertEqual(paths.pi.agent_dir, root / "pi/.pi/agent")
        self.assertEqual(paths.output_root, root / "outputs/asterion-dci-runs")

    def test_loads_the_new_product_env_without_overriding_process_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            env_path = root / ".env"
            env_path.write_text("ASTERION_DCI_OUTPUT_ROOT=from-file\n")
            with patch.dict(
                os.environ,
                {"ASTERION_DCI_OUTPUT_ROOT": "from-process"},
                clear=True,
            ):
                returned = load_asterion_dci_env(root)
                paths = resolve_dci_paths(root)

        self.assertEqual(returned, env_path)
        self.assertEqual(paths.output_root, root / "from-process")


if __name__ == "__main__":
    unittest.main()
