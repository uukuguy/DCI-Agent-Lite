from __future__ import annotations

import re
import subprocess
import tempfile
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

    def test_root_distribution_packages_only_the_dci_baseline(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text()
        wheel_section = pyproject.split("[tool.hatch.build.targets.wheel]", 1)[1]
        self.assertRegex(wheel_section, r'packages\s*=\s*\[\s*"src/dci"\s*\]')
        self.assertNotIn('"src/asterion"', wheel_section)
        self.assertNotIn("asterion_dci_research", wheel_section)

    def test_baseline_framework_modules_are_not_compatibility_reexports(self) -> None:
        framework = python_source(BASELINE_SOURCE / "framework")
        self.assertNotIn("Compatibility exports", framework)
        self.assertNotRegex(framework, re.compile(r"(?:from|import)\s+asterion"))


class BuiltDistributionBoundaryTests(unittest.TestCase):
    def test_core_and_baseline_wheels_have_disjoint_top_level_packages(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            for package in ("asterion", "dci"):
                subprocess.run(
                    ["uv", "build", "--package", package, "--out-dir", temp_dir],
                    cwd=ROOT,
                    check=True,
                    text=True,
                    capture_output=True,
                )
            wheels = {path.name.split("-", 1)[0]: path for path in Path(temp_dir).glob("*.whl")}
            self.assertEqual(self.wheel_top_levels(wheels["asterion"]), {"asterion"})
            self.assertEqual(self.wheel_top_levels(wheels["dci"]), {"dci"})
            self.assertNotIn("Requires-Dist: dci", self.metadata(wheels["asterion"]))
            self.assertNotIn("Requires-Dist: asterion", self.metadata(wheels["dci"]))

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
