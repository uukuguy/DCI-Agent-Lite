from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AsterionStructureTests(unittest.TestCase):
    def test_runtime_objects_are_authoritative_and_compatible(self) -> None:
        from asterion.runtime.host import AgentRuntimeClient as NewClient
        from asterion.runtime.protocol import PROTOCOL_VERSION as new_version
        from dci.framework.host import AgentRuntimeClient as OldClient
        from dci.framework.protocol import PROTOCOL_VERSION as old_version

        self.assertEqual(new_version, "dci.agent-runtime/v1")
        self.assertIs(OldClient, NewClient)
        self.assertEqual(old_version, new_version)

    def test_runtime_adapters_are_authoritative_and_compatible(self) -> None:
        from asterion.adapters.claude_code import (
            ClaudeCodeProtocolAdapter as NewClaudeAdapter,
        )
        from asterion.adapters.pi import PiProtocolAdapter as NewPiAdapter
        from asterion.runtimes.claude_code import run_claude_code as new_run
        from dci.framework.adapters.claude_code import (
            ClaudeCodeProtocolAdapter as OldClaudeAdapter,
        )
        from dci.framework.adapters.pi import PiProtocolAdapter as OldPiAdapter
        from dci.framework.runtimes.claude_code import run_claude_code as old_run

        self.assertIs(OldPiAdapter, NewPiAdapter)
        self.assertIs(OldClaudeAdapter, NewClaudeAdapter)
        self.assertIs(old_run, new_run)

    def test_asterion_never_imports_dci(self) -> None:
        source_root = ROOT / "src/asterion"
        self.assertTrue(source_root.is_dir())
        source = "\n".join(path.read_text() for path in source_root.rglob("*.py"))
        self.assertNotRegex(source, r"(?:from|import)\s+dci(?:\.|\s|$)")

    def test_wheel_contains_both_transition_packages(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text()
        self.assertIn('packages = ["src/asterion", "src/dci"]', pyproject)


if __name__ == "__main__":
    unittest.main()
