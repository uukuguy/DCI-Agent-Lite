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

    def test_package_and_assembly_objects_are_compatibility_aliases(self) -> None:
        from asterion.assembly.protocol import AssemblyPlan as NewPlan
        from asterion.packages.catalog import PackageCatalog as NewCatalog
        from asterion.packages.composition import PackageComposition as NewComposition
        from asterion.services.executor_protocol import ExecutorProtocolError as NewError
        from dci.framework.assembly import AssemblyPlan as OldPlan
        from dci.framework.executor_protocol import ExecutorProtocolError as OldError
        from dci.framework.package_catalog import PackageCatalog as OldCatalog
        from dci.framework.packages import PackageComposition as OldComposition

        self.assertIs(OldPlan, NewPlan)
        self.assertIs(OldCatalog, NewCatalog)
        self.assertIs(OldComposition, NewComposition)
        self.assertIs(OldError, NewError)

    def test_dci_framework_compatibility_modules_define_no_behavior(self) -> None:
        import ast

        for path in (ROOT / "src/dci/framework").glob("*.py"):
            if path.name == "__init__.py":
                continue
            tree = ast.parse(path.read_text())
            definitions = [
                node
                for node in tree.body
                if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
            ]
            self.assertEqual(definitions, [], path)

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


if __name__ == "__main__":
    unittest.main()
