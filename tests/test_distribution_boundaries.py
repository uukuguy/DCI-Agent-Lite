from __future__ import annotations

import re
import os
import subprocess
import tempfile
import tomllib
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASTERION_PROJECT = ROOT / "packages/python/asterion-core"
ASTERION_SOURCE = ASTERION_PROJECT / "src/asterion"
BASELINE_SOURCE = ROOT / "src/dci"


def python_source(root: Path) -> str:
    return "\n".join(
        path.read_text()
        for path in sorted(root.rglob("*.py"))
        if "__pycache__" not in path.parts
    )


class SourceDistributionBoundaryTests(unittest.TestCase):
    def test_asterion_core_has_an_independent_project_and_source_root(self) -> None:
        self.assertTrue((ASTERION_PROJECT / "pyproject.toml").is_file())
        self.assertTrue((ASTERION_SOURCE / "__init__.py").is_file())
        self.assertFalse((ROOT / "src/asterion").exists())

    def test_asterion_core_never_imports_the_dci_baseline(self) -> None:
        source = python_source(ASTERION_SOURCE)
        self.assertNotRegex(source, r"(?:from|import)\s+dci(?:\.|\s|$)")

    def test_dci_baseline_never_imports_asterion(self) -> None:
        source = python_source(BASELINE_SOURCE)
        self.assertNotRegex(source, r"(?:from|import)\s+asterion(?:\.|\s|$)")

    def test_root_is_a_non_buildable_workspace_with_one_member(self) -> None:
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertNotIn("build-system", pyproject)
        self.assertTrue(pyproject["tool"]["uv"]["package"] is False)
        self.assertEqual(
            pyproject["tool"]["uv"]["workspace"]["members"],
            ["packages/python/asterion-core"],
        )
        self.assertNotIn("scripts", pyproject["project"])

    def test_baseline_framework_modules_are_not_compatibility_reexports(self) -> None:
        framework = python_source(BASELINE_SOURCE / "framework")
        self.assertNotIn("Compatibility exports", framework)
        self.assertNotRegex(framework, re.compile(r"(?:from|import)\s+asterion"))

    def test_asterion_dci_operator_documentation_is_independent_and_scoped(self) -> None:
        environment = (ROOT / ".env.template").read_text()
        readme = (ROOT / "README.md").read_text()
        execution = (ROOT / "docs/architecture/capability-execution.md").read_text()
        for variable in (
            "ASTERION_DCI_PI_DIR",
            "ASTERION_DCI_PI_PACKAGE_DIR",
            "ASTERION_DCI_PI_AGENT_DIR",
            "ASTERION_DCI_OUTPUT_ROOT",
        ):
            self.assertIn(variable, environment)
        self.assertIn("asterion-dci run", readme)
        self.assertIn("AF-190", readme)
        self.assertIn("AF-200", readme)
        self.assertIn("DciRunResult", execution)
        self.assertIn("project_dci_run", execution)
        self.assertRegex(execution.lower(), r"generic\s+asterion cli")


    def test_source_baseline_remains_runnable_without_installation(self) -> None:
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        completed = subprocess.run(
            ["uv", "run", "python", "-m", "dci.benchmark.pi_rpc_runner", "--help"],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)


class BuiltDistributionBoundaryTests(unittest.TestCase):
    def test_asterion_is_the_only_buildable_wheel(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            subprocess.run(
                ["uv", "build", "--package", "asterion", "--wheel", "--out-dir", temp_dir],
                cwd=ROOT,
                check=True,
                text=True,
                capture_output=True,
            )
            wheels = list(Path(temp_dir).glob("*.whl"))
            self.assertEqual(len(wheels), 1)
            self.assertEqual(self.wheel_top_levels(wheels[0]), {"asterion"})
            self.assertNotIn("Requires-Dist: dci", self.metadata(wheels[0]))
            with zipfile.ZipFile(wheels[0]) as archive:
                names = archive.namelist()
                self.assertIn("asterion/dci/cli.py", names)
                self.assertIn("asterion/dci/run.py", names)
                self.assertNotIn("dci/benchmark/pi_rpc_runner.py", names)
                entry_points = archive.read(
                    next(name for name in names if name.endswith("entry_points.txt"))
                ).decode()
                self.assertIn("asterion-dci = asterion.dci.cli:main", entry_points)
                manifests = [
                    name for name in archive.namelist() if "/dci_research/manifests/" in name
                ]
                controlled_manifests = [
                    name
                    for name in archive.namelist()
                    if "/controlled_code/manifests/" in name
                ]
                assemblies = [
                    name
                    for name in archive.namelist()
                    if "/assemblies/" in name
                ]
            self.assertEqual(len(manifests), 4)
            self.assertEqual(len(manifests), len(set(manifests)))
            self.assertEqual(len(controlled_manifests), 4)
            self.assertEqual(len(controlled_manifests), len(set(controlled_manifests)))
            self.assertEqual(
                {Path(name).name for name in assemblies},
                {
                    "controlled-code-validation.json",
                    "dci-local-research.json",
                    "dci-research-capability-claude.json",
                    "dci-research-capability.json",
                },
            )
            self.assertEqual(len(assemblies), len(set(assemblies)))

    def test_no_capability_or_baseline_project_remains(self) -> None:
        self.assertFalse((ROOT / "capabilities/dci-research/pyproject.toml").exists())
        pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())
        self.assertNotEqual(pyproject["project"]["name"], "dci")
        self.assertFalse((ROOT / "capabilities/dci-research/src").exists())

    def wheel_top_levels(self, wheel: Path) -> set[str]:
        with zipfile.ZipFile(wheel) as archive:
            return {
                name.split("/", 1)[0]
                for name in archive.namelist()
                if "/" in name and ".dist-info" not in name.split("/", 1)[0]
            }

    def metadata(self, wheel: Path) -> str:
        with zipfile.ZipFile(wheel) as archive:
            metadata_path = next(
                name for name in archive.namelist() if name.endswith(".dist-info/METADATA")
            )
            return archive.read(metadata_path).decode()


if __name__ == "__main__":
    unittest.main()
