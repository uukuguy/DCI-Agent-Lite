from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CHECKER = REPO_ROOT / "tools/project_scope_check.py"


class ProjectScopeCheckTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.write(
            "docs/architecture/agent-framework.md",
            "# Agent Application Framework\n",
        )
        self.write(
            "docs/status/WORKLIST.md",
            "\n".join(
                [
                    "# Framework Worklist",
                    "",
                    "> Project lifecycle: active",
                    "",
                    "## AF-000 — Framework control plane",
                    "",
                    "- Status: in_progress",
                    "- Parent objective: Agent Application Framework",
                    "- Scope: scope audit",
                    "- Dependencies: none",
                    "- Acceptance: valid state passes",
                    "- Design: `docs/design.md`",
                    "- Plan: `docs/plan.md`",
                    "",
                ]
            ),
        )
        self.write(
            "docs/status/CURRENT-STATE.md",
            "- Framework north star: `docs/architecture/agent-framework.md`\n",
        )
        self.write(
            "docs/status/RESUME-NEXT-SESSION.md",
            "Active work package: AF-000\n",
        )
        self.write(
            "docs/status/climb/session-state.json",
            json.dumps({"phase": "hard-pause"}),
        )
        self.write("docs/status/climb/hypotheses.yaml", "hypotheses: []\n")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def write(self, relative_path: str, content: str) -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)

    def run_check(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(CHECKER), "--root", str(self.root), *args],
            text=True,
            capture_output=True,
        )

    def test_valid_repository_state_reports_the_single_active_package(self) -> None:
        result = self.run_check()

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["lifecycle"], "active")
        self.assertEqual(payload["active_package"], "AF-000")
        self.assertEqual(payload["errors"], [])

    def test_complete_lifecycle_accepts_zero_active_completed_packages(self) -> None:
        self.write(
            "docs/status/WORKLIST.md",
            "\n".join(
                [
                    "# Framework Worklist",
                    "",
                    "> Project lifecycle: complete",
                    "",
                    "## AF-000 — Framework control plane",
                    "",
                    "- Status: completed",
                    "",
                ]
            ),
        )
        self.write(
            "docs/status/RESUME-NEXT-SESSION.md",
            "Active work package: none\n",
        )

        result = self.run_check()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["lifecycle"], "complete")
        self.assertIsNone(payload["active_package"])
        self.assertEqual(payload["errors"], [])

    def test_complete_lifecycle_rejects_in_progress_package(self) -> None:
        worklist = (self.root / "docs/status/WORKLIST.md").read_text()
        self.write(
            "docs/status/WORKLIST.md",
            worklist.replace("Project lifecycle: active", "Project lifecycle: complete"),
        )

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertTrue(
            any(
                error.startswith("complete lifecycle requires zero in_progress packages")
                for error in json.loads(result.stdout)["errors"]
            )
        )

    def test_complete_lifecycle_rejects_non_completed_package(self) -> None:
        self.write(
            "docs/status/WORKLIST.md",
            "\n".join(
                [
                    "# Framework Worklist",
                    "",
                    "> Project lifecycle: complete",
                    "",
                    "## AF-000 — Framework control plane",
                    "",
                    "- Status: blocked",
                    "",
                ]
            ),
        )
        self.write("docs/status/RESUME-NEXT-SESSION.md", "Active work package: none\n")

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "complete lifecycle requires every package completed: AF-000=blocked",
            json.loads(result.stdout)["errors"],
        )

    def test_complete_lifecycle_rejects_active_climb_session(self) -> None:
        self.write(
            "docs/status/WORKLIST.md",
            "\n".join(
                [
                    "# Framework Worklist",
                    "",
                    "> Project lifecycle: complete",
                    "",
                    "## AF-000 — Framework control plane",
                    "",
                    "- Status: completed",
                    "",
                ]
            ),
        )
        self.write("docs/status/RESUME-NEXT-SESSION.md", "Active work package: none\n")
        self.write(
            "docs/status/climb/session-state.json",
            json.dumps({"phase": "implementation", "work_package_id": "AF-000"}),
        )

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "active climb session cannot run in complete lifecycle",
            json.loads(result.stdout)["errors"],
        )

    def test_complete_lifecycle_rejects_requested_climb_hypothesis(self) -> None:
        self.write(
            "docs/status/WORKLIST.md",
            "\n".join(
                [
                    "# Framework Worklist",
                    "",
                    "> Project lifecycle: complete",
                    "",
                    "## AF-000 — Framework control plane",
                    "",
                    "- Status: completed",
                    "",
                ]
            ),
        )
        self.write("docs/status/RESUME-NEXT-SESSION.md", "Active work package: none\n")
        self.write(
            "docs/status/climb/hypotheses.yaml",
            "hypotheses:\n- id: AF-000-H-001\n  work_package_id: AF-000\n",
        )

        result = self.run_check("--climb-hypothesis", "AF-000-H-001")

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "climb hypothesis AF-000-H-001 cannot dispatch without an active package",
            json.loads(result.stdout)["errors"],
        )

    def test_missing_or_unknown_lifecycle_is_rejected(self) -> None:
        worklist = (self.root / "docs/status/WORKLIST.md").read_text()
        self.write(
            "docs/status/WORKLIST.md",
            worklist.replace("> Project lifecycle: active\n\n", ""),
        )

        missing = self.run_check()

        self.assertEqual(missing.returncode, 1)
        self.assertIn(
            "worklist must contain exactly one project lifecycle marker",
            json.loads(missing.stdout)["errors"],
        )

        self.write(
            "docs/status/WORKLIST.md",
            worklist.replace("Project lifecycle: active", "Project lifecycle: paused"),
        )

        unknown = self.run_check()

        self.assertEqual(unknown.returncode, 1)
        self.assertIn(
            "unknown project lifecycle paused",
            json.loads(unknown.stdout)["errors"],
        )

    def test_active_lifecycle_rejects_zero_active_packages(self) -> None:
        worklist = (self.root / "docs/status/WORKLIST.md").read_text()
        self.write(
            "docs/status/WORKLIST.md",
            worklist.replace("- Status: in_progress", "- Status: completed"),
        )

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "active lifecycle requires exactly one in_progress package, found 0",
            json.loads(result.stdout)["errors"],
        )

    def test_resume_package_mismatch_is_rejected(self) -> None:
        self.write("docs/status/RESUME-NEXT-SESSION.md", "Active work package: AF-999\n")

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertTrue(
            any(
                error.startswith("resume names AF-999")
                for error in json.loads(result.stdout)["errors"]
            )
        )

    def test_missing_north_star_marker_is_rejected(self) -> None:
        self.write("docs/status/CURRENT-STATE.md", "# Current State\n")

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertIn("CURRENT-STATE missing framework north-star marker", json.loads(result.stdout)["errors"])

    def test_multiple_active_packages_are_rejected(self) -> None:
        worklist = (self.root / "docs/status/WORKLIST.md").read_text()
        self.write(
            "docs/status/WORKLIST.md",
            worklist
            + "\n## AF-010 — Protocol\n\n- Status: in_progress\n- Scope: contract\n"
            + "- Dependencies: AF-000\n- Acceptance: contract fixtures\n"
            + "- Design: `docs/design.md`\n- Plan: `docs/plan.md`\n",
        )

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "active lifecycle requires exactly one in_progress package, found 2",
            json.loads(result.stdout)["errors"],
        )

    def test_active_package_missing_required_fields_is_rejected(self) -> None:
        self.write(
            "docs/status/WORKLIST.md",
            "## AF-000 — Framework control plane\n\n- Status: in_progress\n",
        )

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "AF-000 missing required field Scope",
            json.loads(result.stdout)["errors"],
        )

    def test_active_climb_session_without_parent_package_is_rejected(self) -> None:
        self.write(
            "docs/status/climb/session-state.json",
            json.dumps({"phase": "implementation", "next_hypothesis": "AF-000-H-001"}),
        )

        result = self.run_check()

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "active climb session lacks work_package_id",
            json.loads(result.stdout)["errors"],
        )

    def test_requested_unparented_climb_hypothesis_is_rejected(self) -> None:
        self.write(
            "docs/status/climb/hypotheses.yaml",
            "hypotheses:\n- id: H-001\n  status: confirmed\n",
        )

        result = self.run_check("--climb-hypothesis", "H-001")

        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "unparented climb hypothesis H-001",
            json.loads(result.stdout)["errors"],
        )


if __name__ == "__main__":
    unittest.main()
