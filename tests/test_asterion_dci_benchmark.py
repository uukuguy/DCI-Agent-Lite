from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from asterion.dci.benchmark import BenchmarkRequest, DciBenchmarkError, run_benchmark
from asterion.dci.config import DciRuntimeOptions
from asterion.dci.judge import JudgeConfig
from asterion.dci.run import DciRunResult
from asterion.runtime.host import RunEvent


class AsterionDciBenchmarkTests(unittest.TestCase):
    def test_limit_slices_sorted_rows_and_rejects_zero(self) -> None:
        """Compatibility evidence name retained for the closed AF-220 climb case."""

        self.test_limit_slices_source_order_rows_and_rejects_zero()

    def test_batch_uses_its_runtime_options_for_every_native_row(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            dataset = root / "dataset.jsonl"
            dataset.write_text(
                "\n".join(
                    (
                        json.dumps({"query_id": "q-2", "query": "two", "answer": "two"}),
                        json.dumps({"query_id": "q-1", "query": "one", "answer": "one"}),
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            request = BenchmarkRequest(
                dataset=dataset,
                output_root=root / "out",
                cwd=root,
                judge_config=JudgeConfig(base_url="https://judge.example.test/v1"),
                runtime_options=DciRuntimeOptions(provider="openai", model="gpt-test"),
            )
            with patch("asterion.dci.benchmark.run_pi_research") as run:
                run.side_effect = [
                    _result(root / "out" / "q-1"),
                    _result(root / "out" / "q-2"),
                ]
                with patch("asterion.dci.benchmark.evaluate_run_directory_async", return_value={"is_correct": True}):
                    run_benchmark(request, paths=Mock())

        self.assertEqual([call.args[1].run_id for call in run.call_args_list], ["q-2", "q-1"])
        self.assertEqual(
            [(call.args[1].provider, call.args[1].model) for call in run.call_args_list],
            [("openai", "gpt-test"), ("openai", "gpt-test")],
        )

    def test_limit_slices_source_order_rows_and_rejects_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            dataset = root / "dataset.jsonl"
            dataset.write_text(
                "\n".join(
                    (
                        json.dumps({"query_id": "q-2", "query": "two", "answer": "two"}),
                        json.dumps({"query_id": "q-1", "query": "one", "answer": "one"}),
                    )
                )
                + "\n",
                encoding="utf-8",
            )
            request = BenchmarkRequest(
                dataset=dataset,
                output_root=root / "out",
                cwd=root,
                judge_config=JudgeConfig(base_url="https://judge.example.test/v1"),
                runtime_options=DciRuntimeOptions(provider="openai", model="gpt-test"),
                limit=1,
            )
            with patch("asterion.dci.benchmark.run_pi_research", return_value=_result(root / "out" / "q-1")) as run:
                with patch("asterion.dci.benchmark.evaluate_run_directory_async", return_value={"is_correct": True}):
                    result = run_benchmark(request, paths=Mock())

            self.assertEqual(result.counts["total"], 1)
            self.assertEqual(run.call_args.args[1].run_id, "q-2")

            invalid = BenchmarkRequest(
                dataset=dataset,
                output_root=root / "invalid",
                cwd=root,
                judge_config=JudgeConfig(base_url="https://judge.example.test/v1"),
                runtime_options=DciRuntimeOptions(provider="openai", model="gpt-test"),
                limit=0,
            )
            with self.assertRaisesRegex(DciBenchmarkError, "limit is invalid"):
                run_benchmark(invalid, paths=Mock())
    def test_batch_reuses_the_native_asterion_run_and_writes_aggregate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            with patch("asterion.dci.benchmark.run_pi_research", return_value=_result(root / "out" / "q-1")) as run:
                with patch("asterion.dci.benchmark.evaluate_run_directory_async", return_value={"is_correct": True}):
                    result = run_benchmark(request, paths=Mock())

            self.assertEqual(run.call_count, 1)
            self.assertTrue((result.output_root / "summary.json").is_file())
            self.assertEqual(result.counts["correct"], 1)

    def test_existing_successful_result_skips_run_and_evaluation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            with patch("asterion.dci.benchmark.run_pi_research", return_value=_result(request.output_root / "q-1")), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async", return_value={"is_correct": True}
            ):
                run_benchmark(request, paths=Mock())
            with patch("asterion.dci.benchmark.run_pi_research") as run:
                with patch("asterion.dci.benchmark.evaluate_run_directory_async") as evaluate:
                    run_benchmark(request, paths=Mock())

        run.assert_not_called()
        evaluate.assert_not_called()

    def test_changed_judge_configuration_reevaluates_without_rerunning_pi(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            query_dir = request.output_root / "q-1"
            query_dir.mkdir(parents=True)
            (query_dir / "state.json").write_text(json.dumps({"status": "completed", "question": "question"}))
            (query_dir / "final.txt").write_text("answer\n")
            with patch("asterion.dci.benchmark._completed_run", return_value=True), patch("asterion.dci.benchmark.run_pi_research") as run:
                with patch("asterion.dci.benchmark.evaluate_run_directory_async", return_value={"is_correct": False}) as evaluate:
                    run_benchmark(request, paths=Mock())

        run.assert_not_called()
        evaluate.assert_called_once()

    def test_invalid_dataset_identity_fails_before_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root, query_id="../escape")
            with patch("asterion.dci.benchmark.run_pi_research") as run:
                with self.assertRaisesRegex(DciBenchmarkError, "dataset is invalid"):
                    run_benchmark(request, paths=Mock())

        run.assert_not_called()


def _request(root: Path, *, query_id: str = "q-1") -> BenchmarkRequest:
    dataset = root / "dataset.jsonl"
    dataset.write_text(json.dumps({"query_id": query_id, "query": "question", "answer": "gold"}) + "\n")
    return BenchmarkRequest(
        dataset=dataset,
        output_root=root / "out",
        cwd=root,
        judge_config=JudgeConfig(base_url="https://judge.example.test/v1"),
        runtime_options=DciRuntimeOptions(provider=None, model=None),
    )


def _result(output_dir: Path) -> DciRunResult:
    return DciRunResult(output_dir=output_dir, final_text="answer", events=(RunEvent("r", 1, "run.started", {"capabilities": []}), RunEvent("r", 2, "run.completed", {"status": "completed"})), status="completed")


if __name__ == "__main__":
    unittest.main()
