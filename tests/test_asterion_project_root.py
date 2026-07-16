from __future__ import annotations

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


if __name__ == "__main__":
    unittest.main()
