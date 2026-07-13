from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from asterion.dci.benchmark import BenchmarkRequest, DciBenchmarkError, run_benchmark
from asterion.dci.judge import JudgeConfig
from asterion.dci.run import DciRunResult
from asterion.runtime.host import RunEvent


class AsterionDciBenchmarkTests(unittest.TestCase):
    def test_batch_reuses_the_native_asterion_run_and_writes_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            request = _request(root)
            with patch("asterion.dci.benchmark.run_pi_research", return_value=_result(root / "out" / "q-1")) as run:
                with patch("asterion.dci.benchmark.evaluate_run_directory", return_value={"is_correct": True}):
                    result = run_benchmark(request, paths=Mock())

            self.assertEqual(run.call_count, 1)
            self.assertTrue((result.output_root / "summary.json").is_file())
            self.assertEqual(result.counts["correct"], 1)

    def test_existing_successful_result_skips_run_and_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            request = _request(root)
            query_dir = request.output_root / "q-1"
            query_dir.mkdir(parents=True)
            (query_dir / "result.json").write_text(json.dumps({"is_correct": True}))
            with patch("asterion.dci.benchmark.run_pi_research") as run:
                with patch("asterion.dci.benchmark.evaluate_run_directory") as evaluate:
                    run_benchmark(request, paths=Mock())

        run.assert_not_called()
        evaluate.assert_not_called()

    def test_changed_judge_configuration_reevaluates_without_rerunning_pi(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            request = _request(root)
            query_dir = request.output_root / "q-1"
            query_dir.mkdir(parents=True)
            (query_dir / "state.json").write_text(json.dumps({"status": "completed", "question": "question"}))
            (query_dir / "final.txt").write_text("answer\n")
            with patch("asterion.dci.benchmark.run_pi_research") as run:
                with patch("asterion.dci.benchmark.evaluate_run_directory", return_value={"is_correct": False}) as evaluate:
                    run_benchmark(request, paths=Mock())

        run.assert_not_called()
        evaluate.assert_called_once()

    def test_invalid_dataset_identity_fails_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            request = _request(root, query_id="../escape")
            with patch("asterion.dci.benchmark.run_pi_research") as run:
                with self.assertRaisesRegex(DciBenchmarkError, "dataset is invalid"):
                    run_benchmark(request, paths=Mock())

        run.assert_not_called()


def _request(root: Path, *, query_id: str = "q-1") -> BenchmarkRequest:
    dataset = root / "dataset.jsonl"
    dataset.write_text(json.dumps({"query_id": query_id, "query": "question", "answer": "gold"}) + "\n")
    return BenchmarkRequest(dataset=dataset, output_root=root / "out", cwd=root, judge_config=JudgeConfig(base_url="https://judge.example.test/v1"))


def _result(output_dir: Path) -> DciRunResult:
    return DciRunResult(output_dir=output_dir, final_text="answer", events=(RunEvent("r", 1, "run.started", {"capabilities": []}), RunEvent("r", 2, "run.completed", {"status": "completed"})), status="completed")


if __name__ == "__main__":
    unittest.main()
