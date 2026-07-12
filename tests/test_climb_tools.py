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
    def test_live_checkpoint_retains_scope_audit_package_marker(self) -> None:
        resume = (REPO_ROOT / "docs/status/RESUME-NEXT-SESSION.md").read_text()

        self.assertRegex(resume, r"(?m)^Active work package: AF-[0-9]+$")

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

    def test_h010_local_eval_identifies_judge_request_fingerprint_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-010"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-010")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "fingerprint_shape": 1,
                    "result_persistence": 1,
                    "reuse_contract": 1,
                    "adapter_integration": 1,
                },
            )

    def test_h011_local_eval_identifies_judge_error_redaction_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-011"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-011")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "invalid_response_redaction": 1,
                    "http_error_redaction": 1,
                    "retry_contract": 1,
                    "adapter_integration": 1,
                },
            )

    def test_h012_local_eval_identifies_judge_artifact_privacy_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-012"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-012")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "safe_result_projection": 1,
                    "invalid_error_redaction": 1,
                    "http_error_redaction": 1,
                    "adapter_integration": 1,
                },
            )

    def test_h013_local_eval_identifies_complete_judge_cache_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-013"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-013")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "matching_identity_reuse": 1,
                    "legacy_rejection": 1,
                    "incomplete_rejection": 1,
                    "adapter_integration": 1,
                },
            )

    def test_h014_local_eval_identifies_judge_input_privacy_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-014"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-014")
            self.assertEqual(evaluation["total"], 4)

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

    def test_record_cycle_uses_active_af050_session_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / "climb"
            shutil.copytree(REPO_ROOT / "docs/status/climb", state_dir)
            hypothesis_path = state_dir / "hypotheses.yaml"
            state = yaml.safe_load(hypothesis_path.read_text())
            state["hypotheses"] = [
                hypothesis
                for hypothesis in state["hypotheses"]
                if hypothesis["id"] in {"AF-050-H-001", "AF-050-H-002"}
            ]
            for hypothesis in state["hypotheses"]:
                hypothesis["results"] = []
                hypothesis["status"] = (
                    "in-flight"
                    if hypothesis["id"] == "AF-050-H-001"
                    else "pending"
                )
            session_path = state_dir / "session-state.json"
            session = json.loads(session_path.read_text())
            session["session"] = "2026-07-12-af-050-rust-executor"
            session_path.write_text(json.dumps(session, indent=2) + "\n")
            hypothesis_path.write_text(
                yaml.safe_dump(state, sort_keys=False, allow_unicode=True)
            )
            journal = root / "JOURNAL.md"
            journal.write_text("# Test Journal\n\n## 2026-07-12\n")
            run_dir = root / "run-af050-h001"
            run_dir.mkdir()
            (run_dir / "local-eval.json").write_text(
                json.dumps(
                    {
                        "total": 4,
                        "per_task": {
                            "unknown_program_denial": 1,
                            "cwd_containment": 1,
                            "policy_limits": 1,
                            "authorized_values": 1,
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
                    "AF-050-H-001",
                    "--run-id",
                    "dci-climb-af050-h001-test",
                    "--run-dir",
                    str(run_dir),
                    "--cycle",
                    "20",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            recorded = yaml.safe_load(hypothesis_path.read_text())["hypotheses"][0]
            self.assertEqual(
                recorded["results"][-1]["session"],
                "2026-07-12-af-050-rust-executor",
            )
            self.assertEqual(
                recorded["results"][-1]["decision_reason"],
                "deterministic local executor acceptance",
            )
            session = json.loads((state_dir / "session-state.json").read_text())
            self.assertEqual(session["next_hypothesis"], "AF-050-H-002")

    def test_record_cycle_classifies_af070_as_package_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / "climb"
            shutil.copytree(REPO_ROOT / "docs/status/climb", state_dir)
            hypothesis_path = state_dir / "hypotheses.yaml"
            state = yaml.safe_load(hypothesis_path.read_text())
            state["hypotheses"] = [
                hypothesis
                for hypothesis in state["hypotheses"]
                if hypothesis["id"] == "AF-070-H-001"
            ]
            hypothesis = state["hypotheses"][0]
            hypothesis["results"] = []
            hypothesis["status"] = "in-flight"
            hypothesis_path.write_text(
                yaml.safe_dump(state, sort_keys=False, allow_unicode=True)
            )
            journal = root / "JOURNAL.md"
            journal.write_text("# Test Journal\n\n## 2026-07-12\n")
            run_dir = root / "run-af070-h001"
            run_dir.mkdir()
            (run_dir / "local-eval.json").write_text(
                json.dumps(
                    {
                        "total": 4,
                        "per_task": {
                            "portable_manifests": 1,
                            "workflow_kind": 1,
                            "stable_graph": 1,
                            "forbidden_fields": 1,
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
                    "AF-070-H-001",
                    "--run-id",
                    "dci-climb-af070-h001-test",
                    "--run-dir",
                    str(run_dir),
                    "--cycle",
                    "31",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            recorded = yaml.safe_load(hypothesis_path.read_text())["hypotheses"][0]
            self.assertEqual(
                recorded["results"][-1]["decision_reason"],
                "deterministic local package acceptance",
            )
            self.assertIn("package acceptance recorded", journal.read_text())

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

    def test_cycle_runs_scope_audit_before_training(self) -> None:
        cycle_script = (REPO_ROOT / "tools/climb/cycle.sh").read_text()
        guard = (
            'python3 "$ROOT/tools/project_scope_check.py" '
            '--climb-hypothesis "$HYPOTHESIS_ID"'
        )

        self.assertIn(guard, cycle_script)
        self.assertLess(cycle_script.index(guard), cycle_script.index('run_dir="$(bash'))

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

    def test_h009_train_checks_strict_schema(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-009", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h010_train_checks_request_fingerprints(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-010", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h011_train_checks_malformed_response_redaction(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-011", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h012_train_checks_judge_artifact_privacy(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-012", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h013_train_checks_complete_judge_cache_results(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-013", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h014_train_checks_judge_input_privacy(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-014", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h016_train_checks_judge_origin_validation(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-016", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h017_train_checks_judge_redirect_containment(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-017", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h018_train_checks_official_responses_retention(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-018", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h019_train_checks_rpc_settlement_postcondition(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-019", train_script)
        self.assertIn("tests.test_pi_rpc_runner", train_script)

    def test_af050_h001_train_runs_rust_authorization_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-050-H-001", train_script)
        self.assertIn("--test authorization", train_script)

    def test_af050_h001_eval_reports_four_authorization_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-050-H-001"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-050-H-001")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "unknown_program_denial",
                    "cwd_containment",
                    "policy_limits",
                    "authorized_values",
                },
            )

    def test_af050_h002_train_runs_rust_process_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-050-H-002", train_script)
        self.assertIn("--test process", train_script)

    def test_af050_h002_eval_reports_four_process_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-050-H-002"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-050-H-002")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "literal_arguments",
                    "cleared_environment",
                    "closed_stdin",
                    "canonical_cwd",
                },
            )

    def test_af050_h003_train_runs_bounded_process_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-050-H-003", train_script)
        self.assertIn("H-003 bounded process resources", train_script)

    def test_af050_h003_eval_reports_four_resource_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-050-H-003"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-050-H-003")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "bounded_streams",
                    "exact_limit",
                    "deadline_kill_reap",
                    "direct_boundary_regression",
                },
            )

    def test_af050_h004_train_runs_concurrent_service_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-050-H-004", train_script)
        self.assertIn("--test service", train_script)

    def test_af050_h004_eval_reports_four_service_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-050-H-004"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-050-H-004")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "responsive_out_of_order",
                    "duplicate_id_denial",
                    "cancel_exactly_once",
                    "safe_parse_error",
                },
            )

    def test_af050_operator_docs_and_root_verification_targets_exist(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text()
        guide = (REPO_ROOT / "docs/operator/rust-executor.md").read_text()

        self.assertIn("test-rust-executor:", makefile)
        self.assertIn("check-rust-executor:", makefile)
        self.assertIn("not an operating-system sandbox", guide)
        self.assertIn("trusted operator configuration", guide)

    def test_af050_h005_train_runs_framework_closure_gate(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-050-H-005", train_script)
        self.assertIn("make test-rust-executor", train_script)
        self.assertIn("make check-rust-executor", train_script)

    def test_af050_h005_eval_reports_four_closure_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-050-H-005"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-050-H-005")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "operator_binary",
                    "operator_docs",
                    "root_test_target",
                    "root_check_target",
                },
            )

    def test_af060_h001_train_runs_package_manifest_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-060-H-001", train_script)
        self.assertIn("tests.test_package_composition", train_script)

    def test_af060_h001_eval_reports_four_manifest_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-060-H-001"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-060-H-001")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "valid_manifest",
                    "portable_kinds",
                    "closed_invalid_fixtures",
                    "sorted_unique_edges",
                },
            )

    def test_af060_h002_train_runs_package_composer_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-060-H-002", train_script)
        self.assertIn("PackageCompositionTests", train_script)

    def test_af060_h002_eval_reports_four_composition_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-060-H-002"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-060-H-002")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "stable_order",
                    "duplicate_and_ambiguity",
                    "missing_edges",
                    "cycle_rejection",
                },
            )

    def test_af060_h003_train_runs_dci_reference_graph_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-060-H-003", train_script)
        self.assertIn("DciReferencePackageTests", train_script)

    def test_af060_h003_eval_reports_four_reference_graph_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-060-H-003"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-060-H-003")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "portable_manifests",
                    "runtime_parity",
                    "research_audit_edges",
                    "capability_rejection",
                },
            )

    def test_af060_h004_train_runs_typescript_package_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-060-H-004", train_script)
        self.assertIn("npm --prefix packages/typescript/agent-runtime test", train_script)

    def test_af060_h004_eval_reports_four_typescript_parity_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-060-H-004"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-060-H-004")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "valid_fixture",
                    "invalid_fixtures",
                    "canonical_ordering",
                    "public_type_contract",
                },
            )

    def test_af060_h005_train_runs_full_framework_closure_gate(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-060-H-005", train_script)
        self.assertIn("python -m unittest discover -v", train_script)
        self.assertIn("make test-typescript-host", train_script)
        self.assertIn("make test-rust-executor", train_script)
        self.assertIn("make check-rust-executor", train_script)

    def test_af060_h005_eval_reports_four_documentation_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-060-H-005"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-060-H-005")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "static_boundary",
                    "manifest_example",
                    "composer_example",
                    "extension_security",
                },
            )

    def test_af070_h001_train_runs_controlled_code_manifest_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-070-H-001", train_script)
        self.assertIn("ControlledCodePackageTests", train_script)

    def test_af070_h001_eval_reports_four_manifest_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-070-H-001"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-070-H-001")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "portable_manifests",
                    "workflow_kind",
                    "stable_graph",
                    "forbidden_fields",
                },
            )


if __name__ == "__main__":
    unittest.main()
