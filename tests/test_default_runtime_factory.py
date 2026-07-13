from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.runtime.factory import RuntimeFactoryContext


class DefaultRuntimeFactoryTests(unittest.TestCase):
    def test_claude_factory_is_exact_and_constructs_without_starting_a_process(self) -> None:
        from asterion.runtime.defaults import default_runtime_factory_registry

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with (
                patch.dict(
                    os.environ,
                    {
                        "ASTERION_CLAUDE_EXECUTABLE": "claude",
                        "ASTERION_RUNTIME_CWD": str(root),
                    },
                    clear=False,
                ),
                patch("asterion.runtime.defaults.shutil.which", return_value="/tool/claude"),
            ):
                binding = default_runtime_factory_registry().select(
                    "claude-code.reference"
                )
                runtime = binding.factory(
                    RuntimeFactoryContext(
                        provider_id="dci-agent-lite",
                        application_id="dci.research-capability",
                        application_version="1.0.0",
                        runtime_id="claude-code.reference",
                        assembly_path=root / "assembly.json",
                        options={},
                    )
                )

        self.assertEqual(binding.capabilities, ("filesystem.read", "shell"))
        self.assertEqual(runtime.manifest.runtime_id, "claude-code.reference")

    def test_missing_claude_executable_fails_without_echoing_the_path(self) -> None:
        from asterion.runtime.defaults import default_runtime_factory_registry
        from asterion.runtime.factory import RuntimeFactoryError

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.dict(
                os.environ,
                {
                    "ASTERION_CLAUDE_EXECUTABLE": "/SECRET/missing",
                    "ASTERION_RUNTIME_CWD": str(root),
                },
                clear=False,
            ):
                binding = default_runtime_factory_registry().select(
                    "claude-code.reference"
                )
                with self.assertRaises(RuntimeFactoryError) as caught:
                    binding.factory(
                        RuntimeFactoryContext(
                            provider_id="dci-agent-lite",
                            application_id="dci.research-capability",
                            application_version="1.0.0",
                            runtime_id="claude-code.reference",
                            assembly_path=root / "assembly.json",
                            options={},
                        )
                    )
        self.assertNotIn("SECRET", str(caught.exception))

    def test_pi_reference_factory_uses_explicit_environment_paths(self) -> None:
        from asterion.runtime.defaults import default_runtime_factory_registry

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            package = root / "pi/packages/coding-agent"
            agent = root / "agent"
            corpus = root / "corpus"
            (package / "dist").mkdir(parents=True)
            (package / "dist/cli.js").write_text("")
            agent.mkdir()
            corpus.mkdir()
            environment = {
                "DCI_PI_PACKAGE_DIR": str(package),
                "DCI_PI_AGENT_DIR": str(agent),
                "ASTERION_RUNTIME_CWD": str(corpus),
                "DCI_PROVIDER": "fixture-provider",
                "DCI_MODEL": "fixture-model",
            }
            with patch.dict(os.environ, environment, clear=False):
                binding = default_runtime_factory_registry().select("pi.reference")
                runtime = binding.factory(
                    RuntimeFactoryContext(
                        provider_id="dci-agent-lite",
                        application_id="dci.research-capability",
                        application_version="1.0.0",
                        runtime_id="pi.reference",
                        assembly_path=root / "assembly.json",
                        options={},
                    )
                )

        self.assertEqual(binding.capabilities, ("filesystem.read", "shell"))
        self.assertEqual(runtime.manifest.runtime_id, "pi.reference")
        self.assertEqual(runtime.manifest.capabilities, binding.capabilities)

    def test_missing_pi_cli_fails_without_exposing_the_path(self) -> None:
        from asterion.runtime.defaults import default_runtime_factory_registry
        from asterion.runtime.factory import RuntimeFactoryError

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.dict(
                os.environ,
                {
                    "DCI_PI_PACKAGE_DIR": str(root / "SECRET-PACKAGE"),
                    "DCI_PI_AGENT_DIR": str(root),
                    "ASTERION_RUNTIME_CWD": str(root),
                },
                clear=False,
            ):
                binding = default_runtime_factory_registry().select("pi.reference")
                with self.assertRaises(RuntimeFactoryError) as caught:
                    binding.factory(
                        RuntimeFactoryContext(
                            provider_id="dci-agent-lite",
                            application_id="dci.research-capability",
                            application_version="1.0.0",
                            runtime_id="pi.reference",
                            assembly_path=root / "assembly.json",
                            options={},
                        )
                    )
        self.assertNotIn("SECRET-PACKAGE", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
