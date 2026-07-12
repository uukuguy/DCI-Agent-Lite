from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


class ClimbToolTests(unittest.TestCase):
    def test_regen_tree_serializes_tracked_hypothesis_state(self) -> None:
        result = subprocess.run(
            ["python3", "tools/climb/regen-tree.py"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        tree = json.loads(
            (REPO_ROOT / "docs/status/climb/research-tree.json").read_text()
        )
        self.assertEqual(tree["active"][0]["id"], "H-001")
        self.assertEqual(len(tree["active"]), 3)

    def test_h001_local_eval_reports_all_policy_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                evaluation["per_task"],
                {
                    "immutable_resolution": 1,
                    "repeat_validation": 1,
                    "dirty_checkout_safety": 1,
                    "override_compatibility": 1,
                },
            )

    def test_record_cycle_confirms_four_of_four_and_advances(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / "climb"
            shutil.copytree(REPO_ROOT / "docs/status/climb", state_dir)
            journal = root / "JOURNAL.md"
            journal.write_text("# Test Journal\n\n## 2026-07-12\n")
            run_dir = root / "run-h001"
            run_dir.mkdir()
            (run_dir / "local-eval.json").write_text(
                json.dumps(
                    {
                        "total": 4,
                        "per_task": {
                            "immutable_resolution": 1,
                            "repeat_validation": 1,
                            "dirty_checkout_safety": 1,
                            "override_compatibility": 1,
                        },
                    }
                )
            )

            result = subprocess.run(
                [
                    "python3",
                    "tools/climb/record-cycle.py",
                    "--state-dir",
                    str(state_dir),
                    "--journal",
                    str(journal),
                    "--hypothesis-id",
                    "H-001",
                    "--run-id",
                    "dci-climb-h001-test",
                    "--run-dir",
                    str(run_dir),
                    "--cycle",
                    "1",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            state = yaml.safe_load((state_dir / "hypotheses.yaml").read_text())
            h001 = next(h for h in state["hypotheses"] if h["id"] == "H-001")
            self.assertEqual(h001["status"], "confirmed")
            self.assertEqual(h001["results"][-1]["local"], 4)
            with (state_dir / "runs.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[-1]["verdict"], "confirmed 4/4")
            session = json.loads((state_dir / "session-state.json").read_text())
            self.assertEqual(session["next_hypothesis"], "H-002")
            self.assertIn("H-001 confirmed 4/4", journal.read_text())

    def test_cycle_adapter_shell_scripts_pass_syntax_validation(self) -> None:
        scripts = [
            "tools/climb/train.sh",
            "tools/climb/eval-local.sh",
            "tools/climb/push.sh",
            "tools/climb/apply-lb-score.sh",
            "tools/climb/cycle.sh",
        ]

        result = subprocess.run(
            ["bash", "-n", *scripts],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
