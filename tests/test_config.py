from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401
from dci.config import (
    ConfigLayers,
    load_project_env,
    resolve_original_runtime,
    resolve_pi_paths,
)


class PiPathConfigTests(unittest.TestCase):
    def test_original_runtime_precedence_and_sources(self) -> None:
        layers = ConfigLayers(
            process={"DCI_PROVIDER": "environment-provider"},
            dotenv={"DCI_PROVIDER": "dotenv-provider", "DCI_MODEL": "dotenv-model"},
        )
        resolved = resolve_original_runtime(
            {"provider": "invocation-provider", "model": None}, layers
        )
        self.assertEqual(resolved.runtime, "pi")
        self.assertEqual(resolved.provider, "invocation-provider")
        self.assertEqual(resolved.model, "dotenv-model")
        self.assertEqual(resolved.sources["agent.provider"], "invocation")
        self.assertEqual(resolved.sources["agent.model"], "environment")

    def test_original_runtime_rejects_claude_code(self) -> None:
        with self.assertRaisesRegex(ValueError, "Original DCI runtime is unsupported"):
            resolve_original_runtime({"runtime": "claude-code"}, ConfigLayers({}, {}))

    def test_original_runtime_uses_dotenv_agent_controls(self) -> None:
        resolved = resolve_original_runtime(
            {},
            ConfigLayers(
                process={},
                dotenv={
                    "DCI_TOOLS": "read,grep",
                    "DCI_MAX_TURNS": "7",
                    "DCI_RPC_TIMEOUT_SECONDS": "42",
                },
            ),
        )

        self.assertEqual(resolved.tools, "read,grep")
        self.assertEqual(resolved.max_turns, 7)
        self.assertEqual(resolved.timeout_seconds, 42.0)
        self.assertEqual(resolved.sources["agent.tools"], "environment")
        self.assertEqual(resolved.sources["agent.max_turns"], "environment")
        self.assertEqual(resolved.sources["agent.timeout_seconds"], "environment")

    def test_empty_process_required_value_continues_to_dotenv(self) -> None:
        resolved = resolve_original_runtime(
            {},
            ConfigLayers(
                process={"DCI_PROVIDER": ""},
                dotenv={"DCI_PROVIDER": "dotenv-provider"},
            ),
        )

        self.assertEqual(resolved.provider, "dotenv-provider")
        self.assertEqual(resolved.sources["agent.provider"], "environment")

    def test_empty_required_layers_fall_to_truthful_runtime_defaults(self) -> None:
        resolved = resolve_original_runtime(
            {"model": ""},
            ConfigLayers(
                process={"DCI_MODEL": "", "DCI_TOOLS": "", "DCI_MAX_TURNS": ""},
                dotenv={"DCI_MODEL": "", "DCI_TOOLS": "", "DCI_MAX_TURNS": ""},
            ),
        )

        self.assertEqual(resolved.model, "gpt-5.6-luna")
        self.assertEqual(resolved.tools, "read,bash")
        self.assertEqual(resolved.max_turns, 100)
        self.assertEqual(resolved.sources["agent.model"], "runtime-default")
        self.assertEqual(resolved.sources["agent.tools"], "runtime-default")
        self.assertEqual(resolved.sources["agent.max_turns"], "runtime-default")

    def test_empty_optional_environment_values_remain_explicit(self) -> None:
        resolved = resolve_original_runtime(
            {},
            ConfigLayers(
                process={
                    "DCI_PI_THINKING_LEVEL": "",
                    "DCI_RUNTIME_CONTEXT_LEVEL": "",
                },
                dotenv={
                    "DCI_PI_THINKING_LEVEL": "high",
                    "DCI_RUNTIME_CONTEXT_LEVEL": "level4",
                },
            ),
        )

        self.assertIsNone(resolved.thinking_level)
        self.assertIsNone(resolved.context_profile)
        self.assertEqual(resolved.sources["agent.thinking_level"], "environment")
        self.assertEqual(resolved.sources["context.profile"], "environment")

    def test_config_layers_snapshot_dotenv_and_materialize_missing_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            (root / ".env").write_text(
                "DCI_PROVIDER=dotenv-provider\nDCI_MODEL=dotenv-model\n",
                encoding="utf-8",
            )
            target = {"DCI_PROVIDER": "process-provider"}
            layers = ConfigLayers.from_repo(root, target)
            layers.materialize(target)

        self.assertEqual(layers.process["DCI_PROVIDER"], "process-provider")
        self.assertEqual(target["DCI_PROVIDER"], "process-provider")
        self.assertEqual(target["DCI_MODEL"], "dotenv-model")

    def test_load_project_env_remains_backward_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            env_path = root / ".env"
            env_path.write_text("DCI_MODEL=dotenv-model\n", encoding="utf-8")
            with patch.dict(os.environ, {"DCI_MODEL": "process-model"}, clear=True):
                returned = load_project_env(root)
                self.assertEqual(os.environ["DCI_MODEL"], "process-model")

        self.assertEqual(returned, env_path)

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
