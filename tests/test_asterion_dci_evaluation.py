from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.dci.evaluation import DciEvaluationError, evaluate_run_directory
from asterion.dci.judge import JudgeConfig


class AsterionDciEvaluationTests(unittest.TestCase):
    def test_reuses_only_an_exact_judge_request_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = _write_native_run(Path(temporary_directory))
            with patch("asterion.dci.evaluation.judge_answer_sync", return_value=_verdict()) as judge:
                first = evaluate_run_directory(output_dir, gold_answer="gold", judge_config=_config())
                second = evaluate_run_directory(output_dir, gold_answer="gold", judge_config=_config())

        self.assertEqual(judge.call_count, 1)
        self.assertEqual(first["judge_request_fingerprint"], second["judge_request_fingerprint"])

    def test_changed_request_shape_rejudges_without_reusing_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = _write_native_run(Path(temporary_directory))
            with patch("asterion.dci.evaluation.judge_answer_sync", return_value=_verdict()) as judge:
                evaluate_run_directory(output_dir, gold_answer="gold", judge_config=_config())
                evaluate_run_directory(output_dir, gold_answer="changed", judge_config=_config())

        self.assertEqual(judge.call_count, 2)

    def test_persists_only_safe_evaluation_state_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = _write_native_run(Path(temporary_directory))
            with patch("asterion.dci.evaluation.judge_answer_sync", return_value=_verdict()):
                evaluate_run_directory(output_dir, gold_answer="gold", judge_config=_config())
            state = json.loads((output_dir / "state.json").read_text())

        self.assertTrue(state["evaluation"]["is_correct"])
        self.assertNotIn("api_key", repr(state["evaluation"]))
        self.assertNotIn("SECRET", repr(state["evaluation"]))

    def test_invalid_native_state_fails_before_judge_transport(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            output_dir.mkdir()
            (output_dir / "state.json").write_text('{"status":"failed","question":"SECRET"}')
            with patch("asterion.dci.evaluation.judge_answer_sync") as judge:
                with self.assertRaisesRegex(DciEvaluationError, "native run is not completed") as raised:
                    evaluate_run_directory(output_dir, gold_answer="gold", judge_config=_config())

        judge.assert_not_called()
        self.assertNotIn("SECRET", str(raised.exception))


def _config() -> JudgeConfig:
    return JudgeConfig(base_url="https://judge.example.test/v1", model="fixture")


def _verdict() -> dict[str, object]:
    return {
        **_config().public_dict(),
        "judged_at": "2026-07-13T00:00:00+00:00",
        "judge_request_fingerprint": "transport-value-is-replaced",
        "is_correct": True,
        "normalized_prediction": "answer",
        "reason": "same",
        "usage": {},
        "cost_estimate_usd": {"total_cost": 0.0},
    }


def _write_native_run(root: Path) -> Path:
    output_dir = root / "run"
    output_dir.mkdir()
    (output_dir / "state.json").write_text(json.dumps({"status": "completed", "question": "question"}))
    (output_dir / "final.txt").write_text("answer\n")
    return output_dir


if __name__ == "__main__":
    unittest.main()
