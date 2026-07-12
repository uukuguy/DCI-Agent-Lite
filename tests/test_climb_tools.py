from __future__ import annotations

import csv
import json
import os
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
        hypotheses = yaml.safe_load(
            (REPO_ROOT / "docs/status/climb/hypotheses.yaml").read_text()
        )["hypotheses"]
        expected_active = {
            item["id"]
            for item in hypotheses
            if item["status"] in {"pending", "in-flight"}
        }
        expected_confirmed = {
            item["id"] for item in hypotheses if item["status"] == "confirmed"
        }
        self.assertEqual({item["id"] for item in tree["active"]}, expected_active)
        self.assertEqual(
            {item["id"] for item in tree["confirmed"]}, expected_confirmed
        )

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

    def test_h002_local_eval_identifies_read_only_upgrade_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-002"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-002")
            self.assertEqual(evaluation["total"], 4)

    def test_h003_local_eval_identifies_rpc_protocol_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-003"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-003")
            self.assertEqual(evaluation["total"], 4)

    def test_h004_local_eval_identifies_run_provenance_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-004"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-004")
            self.assertEqual(evaluation["total"], 4)

    def test_h005_local_eval_identifies_pre_run_warning_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-005"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-005")
            self.assertEqual(evaluation["total"], 4)

    def test_h006_local_eval_identifies_judge_preflight_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-006"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-006")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "shared_transport": 1,
                    "missing_key_safety": 1,
                    "safe_output": 1,
                    "make_and_adapter": 1,
                },
            )

    def test_h007_local_eval_identifies_judge_key_provenance_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-007"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-007")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "dotenv_source": 1,
                    "process_source": 1,
                    "shadow_warning": 1,
                    "safe_output": 1,
                },
            )

    def test_h008_local_eval_identifies_no_request_config_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-008"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-008")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "config_only_safety": 1,
                    "dotenv_source": 1,
                    "shadow_warning": 1,
                    "make_and_adapter": 1,
                },
            )

    def test_record_cycle_confirms_four_of_four_and_advances(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / "climb"
            shutil.copytree(REPO_ROOT / "docs/status/climb", state_dir)
            hypothesis_path = state_dir / "hypotheses.yaml"
            isolated_hypotheses = yaml.safe_load(hypothesis_path.read_text())
            isolated_hypotheses["hypotheses"] = [
                hypothesis
                for hypothesis in isolated_hypotheses["hypotheses"]
                if hypothesis["id"] in {"H-001", "H-002", "H-003"}
            ]
            for hypothesis in isolated_hypotheses["hypotheses"]:
                hypothesis["results"] = []
                hypothesis["status"] = (
                    "in-flight" if hypothesis["id"] == "H-001" else "pending"
                )
            hypothesis_path.write_text(
                yaml.safe_dump(
                    isolated_hypotheses, sort_keys=False, allow_unicode=True
                )
            )
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

            command = [
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
            ]
            result = subprocess.run(
                command,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )
            replay = subprocess.run(
                command,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            state = yaml.safe_load((state_dir / "hypotheses.yaml").read_text())
            h001 = next(h for h in state["hypotheses"] if h["id"] == "H-001")
            self.assertEqual(h001["status"], "confirmed")
            self.assertEqual(h001["results"][-1]["local"], 4)
            self.assertEqual(
                sum(
                    result["run"] == "dci-climb-h001-test"
                    for result in h001["results"]
                ),
                1,
            )
            runs_path = state_dir / "runs.csv"
            with runs_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[-1]["verdict"], "confirmed 4/4")
            self.assertEqual(
                sum(row["run_id"] == "dci-climb-h001-test" for row in rows), 1
            )
            self.assertEqual(
                rows[-1]["manifest_path"],
                "runs/climb/dci-climb-h001-test/manifest.json",
            )
            self.assertNotIn(b"\r", runs_path.read_bytes())
            session = json.loads((state_dir / "session-state.json").read_text())
            self.assertEqual(session["next_hypothesis"], "H-002")
            self.assertIn("H-001 confirmed 4/4", journal.read_text())

    def test_record_cycle_recovers_hypothesis_specific_partial_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / "climb"
            shutil.copytree(REPO_ROOT / "docs/status/climb", state_dir)
            hypothesis_path = state_dir / "hypotheses.yaml"
            state = yaml.safe_load(hypothesis_path.read_text())
            state["hypotheses"] = [
                hypothesis
                for hypothesis in state["hypotheses"]
                if hypothesis["id"] == "H-006"
            ]
            h006 = state["hypotheses"][0]
            h006["status"] = "confirmed"
            h006["results"] = [
                {
                    "session": "2026-07-12-pi-revision",
                    "cycle": 6,
                    "run": "dci-climb-h006-test",
                    "local": 4,
                    "local_per_task": {
                        "shared_transport": 1,
                        "missing_key_safety": 1,
                        "safe_output": 1,
                        "make_and_adapter": 1,
                    },
                    "online": None,
                    "verdict": "confirmed 4/4",
                    "decision_reason": "deterministic local setup-policy acceptance",
                }
            ]
            hypothesis_path.write_text(
                yaml.safe_dump(state, sort_keys=False, allow_unicode=True)
            )
            journal = root / "JOURNAL.md"
            journal.write_text("# Test Journal\n\n## 2026-07-12\n")
            run_dir = root / "run-h006"
            run_dir.mkdir()
            (run_dir / "local-eval.json").write_text(
                json.dumps(
                    {
                        "total": 4,
                        "per_task": {
                            "shared_transport": 1,
                            "missing_key_safety": 1,
                            "safe_output": 1,
                            "make_and_adapter": 1,
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
                    "H-006",
                    "--run-id",
                    "dci-climb-h006-test",
                    "--run-dir",
                    str(run_dir),
                    "--cycle",
                    "6",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            recovered = yaml.safe_load(hypothesis_path.read_text())["hypotheses"][0]
            self.assertEqual(len(recovered["results"]), 1)
            with (state_dir / "runs.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            row = rows[-1]
            self.assertEqual(row["hypothesis_id"], "H-006")
            self.assertEqual(row["local_score"], "4")
            self.assertEqual(row["immutable_resolution"], "")
            self.assertEqual(row["repeat_validation"], "")
            self.assertEqual(row["dirty_checkout_safety"], "")
            self.assertEqual(row["override_compatibility"], "")

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

    def test_h003_train_runs_the_real_model_free_probe(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("scripts/check_pi_rpc.py", train_script)
        self.assertIn("uv run python", train_script)

    def test_h004_train_runs_runtime_acceptance(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("make runtime-example", train_script)

    def test_h006_train_runs_the_live_judge_preflight(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("tests.test_check_judge", train_script)
        self.assertIn("make check-judge", train_script)

    def test_h007_train_checks_dotenv_provenance(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-007", train_script)
        self.assertIn("env -u DEEPSEEK_API_KEY make check-judge", train_script)

    def test_h008_train_checks_config_without_request(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-008", train_script)
        self.assertIn(
            "env -u DEEPSEEK_API_KEY make check-judge-config", train_script
        )


if __name__ == "__main__":
    unittest.main()
