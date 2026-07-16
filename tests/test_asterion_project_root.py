from __future__ import annotations

import ast
import tomllib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "asterion"


class AsterionProjectRootTests(unittest.TestCase):
    def test_primary_python_project_has_the_converged_root(self) -> None:
        self.assertTrue((PROJECT / "pyproject.toml").is_file())
        self.assertTrue((PROJECT / "src/asterion/cli.py").is_file())
        self.assertFalse((ROOT / "packages/python/asterion-core").exists())

        workspace = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertEqual(workspace["tool"]["uv"]["workspace"]["members"], ["asterion"])
        self.assertEqual(
            workspace["tool"]["uv"]["sources"]["asterion"],
            {"workspace": True},
        )

        project = tomllib.loads((PROJECT / "pyproject.toml").read_text())
        self.assertEqual(project["project"]["name"], "asterion")
        self.assertEqual(project["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"], ["src/asterion"])

    def test_cross_language_assets_live_inside_asterion(self) -> None:
        expected = (
            "schemas/agent-runtime/v1/event.schema.json",
            "schemas/assembly/v1/assembly.schema.json",
            "schemas/executor/v1/request.schema.json",
            "schemas/packages/v1/package-manifest.schema.json",
            "packages/typescript/asterion-runtime/package.json",
            "packages/rust/controlled-executor/Cargo.toml",
        )
        for relative in expected:
            self.assertTrue((PROJECT / relative).is_file(), relative)
        for obsolete in (ROOT / "schemas", ROOT / "packages/typescript", ROOT / "packages/rust"):
            self.assertFalse(obsolete.exists(), str(obsolete))

    def test_examples_and_launchers_are_project_owned(self) -> None:
        self.assertTrue((PROJECT / "examples/applications/dci_research.py").is_file())
        self.assertTrue((PROJECT / "examples/applications/controlled_code.py").is_file())
        launchers = sorted((PROJECT / "scripts").glob("**/run_*.sh"))
        self.assertEqual(len(launchers), 12)
        self.assertFalse((ROOT / "applications").exists())
        self.assertFalse((ROOT / "scripts/asterion").exists())

    def test_product_documentation_is_project_owned(self) -> None:
        required = (
            "docs/README.md",
            "docs/architecture/agent-framework.md",
            "docs/architecture/asterion-framework-capability-integration.md",
            "docs/architecture/asterion-standalone-extraction.md",
            "docs/guides/asterion-dci-complete-reference.md",
            "docs/verification/asterion-dci-validation-guide.md",
        )
        for relative in required:
            self.assertTrue((PROJECT / relative).is_file(), relative)

    def test_project_local_tests_and_fixtures_exist(self) -> None:
        self.assertTrue((PROJECT / "tests/test_project_boundary.py").is_file())
        self.assertTrue(
            (PROJECT / "tests/fixtures/agent_runtime/v1/valid-research.jsonl").is_file()
        )

    def test_no_obsolete_asterion_product_roots_remain(self) -> None:
        for relative in (
            "packages/python/asterion-core",
            "packages/typescript/asterion-runtime",
            "packages/rust/controlled-executor",
            "applications/dci-agent-lite",
            "applications/controlled-code",
            "scripts/asterion",
            "schemas",
        ):
            self.assertFalse((ROOT / relative).exists(), relative)

    def test_mixed_root_retains_baseline_and_migration_evidence(self) -> None:
        self.assertTrue((ROOT / "src/dci/benchmark/pi_rpc_runner.py").is_file())
        self.assertTrue((ROOT / "assets/dci/product-parity.json").is_file())
        self.assertTrue((ROOT / "assets/dci/product-acceptance.json").is_file())
        self.assertTrue((ROOT / "docs/status/WORKLIST.md").is_file())

    def test_root_dci_tests_bootstrap_source_for_direct_discovery(self) -> None:
        missing: list[str] = []
        for path in sorted((ROOT / "tests").glob("test_*.py")):
            tree = ast.parse(path.read_text(), filename=str(path))
            imports_dci = any(
                (
                    isinstance(node, ast.Import)
                    and any(
                        alias.name == "dci" or alias.name.startswith("dci.")
                        for alias in node.names
                    )
                )
                or (
                    isinstance(node, ast.ImportFrom)
                    and node.module is not None
                    and (node.module == "dci" or node.module.startswith("dci."))
                )
                for node in tree.body
            )
            if not imports_dci:
                continue
            imports_bootstrap = any(
                isinstance(node, ast.ImportFrom)
                and node.module == "tests"
                and any(
                    alias.name == "SOURCE_ROOT" and alias.asname == "_SOURCE_ROOT"
                    for alias in node.names
                )
                for node in tree.body
            )
            if not imports_bootstrap:
                missing.append(path.name)
        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
