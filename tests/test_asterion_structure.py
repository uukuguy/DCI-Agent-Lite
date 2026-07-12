from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AsterionStructureTests(unittest.TestCase):
    def test_runtime_objects_are_independent_and_wire_compatible(self) -> None:
        from asterion.runtime.host import AgentRuntimeClient as NewClient
        from asterion.runtime.protocol import PROTOCOL_VERSION as new_version
        from dci.framework.host import AgentRuntimeClient as OldClient
        from dci.framework.protocol import PROTOCOL_VERSION as old_version

        self.assertEqual(new_version, "dci.agent-runtime/v1")
        self.assertIsNot(OldClient, NewClient)
        self.assertEqual(old_version, new_version)

    def test_runtime_adapters_are_independent_and_capability_compatible(self) -> None:
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

        self.assertIsNot(OldPiAdapter, NewPiAdapter)
        self.assertIsNot(OldClaudeAdapter, NewClaudeAdapter)
        self.assertIsNot(old_run, new_run)
        self.assertEqual(
            OldPiAdapter.__module__, "dci.framework.adapters.pi"
        )
        self.assertEqual(
            NewPiAdapter.__module__, "asterion.adapters.pi"
        )

    def test_asterion_never_imports_dci(self) -> None:
        source_root = ROOT / "packages/python/asterion-core/src/asterion"
        self.assertTrue(source_root.is_dir())
        source = "\n".join(path.read_text() for path in source_root.rglob("*.py"))
        self.assertNotRegex(source, r"(?:from|import)\s+dci(?:\.|\s|$)")

    def test_core_and_baseline_have_independent_wheel_roots(self) -> None:
        baseline = (ROOT / "pyproject.toml").read_text()
        core = (ROOT / "packages/python/asterion-core/pyproject.toml").read_text()
        self.assertIn('packages = ["src/dci"]', baseline)
        self.assertNotIn('"src/asterion"', baseline)
        self.assertIn('packages = ["src/asterion"]', core)
        self.assertNotIn('"src/dci"', core)

    def test_package_and_assembly_objects_are_independent_wire_implementations(self) -> None:
        from asterion.assembly.protocol import AssemblyPlan as NewPlan
        from asterion.packages.catalog import PackageCatalog as NewCatalog
        from asterion.packages.composition import PackageComposition as NewComposition
        from asterion.services.executor_protocol import ExecutorProtocolError as NewError
        from dci.framework.assembly import AssemblyPlan as OldPlan
        from dci.framework.executor_protocol import ExecutorProtocolError as OldError
        from dci.framework.package_catalog import PackageCatalog as OldCatalog
        from dci.framework.packages import PackageComposition as OldComposition

        self.assertIsNot(OldPlan, NewPlan)
        self.assertIsNot(OldCatalog, NewCatalog)
        self.assertIsNot(OldComposition, NewComposition)
        self.assertIsNot(OldError, NewError)

    def test_dci_framework_is_frozen_baseline_owned_behavior(self) -> None:
        source = "\n".join(
            path.read_text() for path in (ROOT / "src/dci/framework").rglob("*.py")
        )
        self.assertNotIn("Compatibility exports", source)
        self.assertNotRegex(source, r"(?:from|import)\s+asterion(?:\.|\s|$)")
        self.assertIn("class ProtocolError", source)
        self.assertIn("class PiProtocolAdapter", source)

    def test_extracted_wire_protocol_literals_remain_stable(self) -> None:
        from asterion.assembly.protocol import ASSEMBLY_PROTOCOL_VERSION
        from asterion.packages.protocol import PACKAGE_PROTOCOL_VERSION
        from asterion.runtime.protocol import PROTOCOL_VERSION
        from asterion.services.executor_protocol import EXECUTOR_PROTOCOL_VERSION

        self.assertEqual(PROTOCOL_VERSION, "dci.agent-runtime/v1")
        self.assertEqual(PACKAGE_PROTOCOL_VERSION, "dci.package/v1")
        self.assertEqual(ASSEMBLY_PROTOCOL_VERSION, "dci.assembly/v1")
        self.assertEqual(EXECUTOR_PROTOCOL_VERSION, "dci.executor/v1")

    def test_declarative_assets_have_product_level_owners(self) -> None:
        capabilities = ROOT / "capabilities"
        applications = ROOT / "applications"
        self.assertEqual(
            {path.name for path in capabilities.iterdir()},
            {"controlled-code", "dci-research"},
        )
        self.assertTrue(
            (
                applications
                / "dci-agent-lite/assemblies/dci-local-research.json"
            ).is_file()
        )
        package_ids = set()
        for path in capabilities.glob("*/manifests/*.json"):
            import json

            package_ids.add(json.loads(path.read_text())["package_id"])
        self.assertEqual(
            package_ids,
            {
                "dci.evaluation",
                "dci.research",
                "evaluation.code-quality",
                "observability.execution-audit",
                "policy.controlled-code-check",
                "policy.local-corpus",
                "protocol.observability",
                "workflow.code-quality",
            },
        )

    def test_cross_language_working_directories_are_asterion_owned(self) -> None:
        self.assertTrue((ROOT / "packages/typescript/asterion-runtime").is_dir())
        self.assertTrue((ROOT / "packages/rust/controlled-executor").is_dir())
        self.assertFalse((ROOT / "packages/typescript/agent-runtime").exists())
        self.assertFalse((ROOT / "packages/rust/executor").exists())

    def test_verified_dci_examples_keep_the_product_cli(self) -> None:
        for name in ("dci_basic_example.sh", "dci_runtime_context_example.sh"):
            source = (ROOT / "scripts/examples" / name).read_text()
            self.assertIn("uv run dci-agent-lite", source)
            self.assertIn('source "$REPO_ROOT/.env"', source)

    def test_examples_build_cli_commands_in_an_isolated_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "scripts/examples").mkdir(parents=True)
            (repo / "corpus/wiki_corpus").mkdir(parents=True)
            (repo / "corpus/bc_plus_docs").mkdir(parents=True)
            (repo / ".env").write_text("DCI_PROVIDER=test-provider\nDCI_MODEL=test-model\n")
            log = repo / "uv-args.txt"
            bin_dir = repo / "bin"
            bin_dir.mkdir()
            uv = bin_dir / "uv"
            uv.write_text('#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> "$UV_ARGS_LOG"\n')
            uv.chmod(0o755)
            env = {
                **os.environ,
                "PATH": f"{bin_dir}:{os.environ['PATH']}",
                "UV_ARGS_LOG": str(log),
            }
            for name in ("dci_basic_example.sh", "dci_runtime_context_example.sh"):
                shutil.copy(ROOT / "scripts/examples" / name, repo / "scripts/examples" / name)
                result = subprocess.run(
                    ["bash", str(repo / "scripts/examples" / name)],
                    cwd=repo,
                    env=env,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertNotIn("test-provider", result.stdout + result.stderr)
                self.assertNotIn("test-model", result.stdout + result.stderr)
            commands = log.read_text().splitlines()
            self.assertEqual(len(commands), 2)
            self.assertTrue(all(command.startswith("run dci-agent-lite ") for command in commands))

    def test_distribution_preserves_existing_console_scripts(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text()
        for command in (
            "dci-agent-lite",
            "dci-run-pi-rpc",
            "dci-print-pi-system-prompt",
        ):
            self.assertIn(command, pyproject)

    def test_layout_guide_defines_framework_ownership(self) -> None:
        guide = (ROOT / "docs/architecture/asterion-framework-layout.md").read_text()
        self.assertIn("Asterion owns framework contracts", guide)
        self.assertIn("Asterion must not import DCI", guide)
        self.assertIn("dci-agent-lite", guide)
        self.assertIn("dci.agent-runtime/v1", guide)


if __name__ == "__main__":
    unittest.main()
