from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.dci.config import (
    load_asterion_dci_env,
    resolve_dci_paths,
    resolve_dci_runtime_options,
)


class AsterionDciConfigTests(unittest.TestCase):
    def test_shared_paths_win_over_compatibility_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            environment = {
                "DCI_PI_DIR": "shared/pi",
                "DCI_PI_PACKAGE_DIR": "shared/coding-agent",
                "DCI_PI_AGENT_DIR": "shared/pi-agent",
                "ASTERION_DCI_PI_DIR": "vendor/pi",
                "ASTERION_DCI_PI_PACKAGE_DIR": "build/coding-agent",
                "ASTERION_DCI_PI_AGENT_DIR": "state/pi-agent",
                "ASTERION_DCI_OUTPUT_ROOT": "asterion-runs",
            }
            with patch.dict(os.environ, environment, clear=True):
                paths = resolve_dci_paths(root)

        self.assertEqual(paths.pi.repo_dir, root / "shared/pi")
        self.assertEqual(paths.pi.package_dir, root / "shared/coding-agent")
        self.assertEqual(paths.pi.agent_dir, root / "shared/pi-agent")
        self.assertEqual(paths.output_root, root / "asterion-runs")

    def test_compatibility_path_aliases_are_fallbacks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            with patch.dict(
                os.environ,
                {"ASTERION_DCI_PI_DIR": "compat/pi"},
                clear=True,
            ):
                paths = resolve_dci_paths(root)

        self.assertEqual(paths.pi.repo_dir, root / "compat/pi")

    def test_runtime_options_merge_shared_env_and_explicit_values(self) -> None:
        with patch.dict(
            os.environ,
            {
                "DCI_PROVIDER": "openai",
                "DCI_MODEL": "gpt-test",
                "DCI_RPC_TIMEOUT_SECONDS": "45",
            },
            clear=True,
        ):
            options = resolve_dci_runtime_options({"model": "explicit-model"})

        self.assertEqual(
            (options.provider, options.model, options.timeout_seconds),
            ("openai", "explicit-model", 45.0),
        )

    def test_runtime_options_reject_invalid_timeout_and_heap(self) -> None:
        with patch.dict(os.environ, {"DCI_RPC_TIMEOUT_SECONDS": "not-a-number"}, clear=True):
            with self.assertRaises(ValueError):
                resolve_dci_runtime_options()
        with patch.dict(
            os.environ,
            {"DCI_NODE_MAX_OLD_SPACE_SIZE_MB": "0"},
            clear=True,
        ):
            with self.assertRaises(ValueError):
                resolve_dci_runtime_options()

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
