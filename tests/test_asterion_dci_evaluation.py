from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.dci.evaluation import (
    DciEvaluationError,
    evaluate_run_directory,
    evaluate_run_directory_async,
)
from asterion.dci.artifacts import DciArtifactError, DciRunLock, DciRunRecorder
from asterion.dci.config import resolve_dci_paths
from asterion.dci.run import DciRunRequest
from asterion.dci.judge import DciJudgeError, JudgeConfig


class AsterionDciEvaluationTests(unittest.TestCase):
    def test_reuses_only_an_exact_judge_request_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = _write_native_run(Path(temporary_directory))
            with patch(
                "asterion.dci.evaluation.judge_answer_sync", return_value=_verdict()
            ) as judge:
                first = evaluate_run_directory(
                    output_dir, gold_answer="gold", judge_config=_config()
                )
                second = evaluate_run_directory(
                    output_dir, gold_answer="gold", judge_config=_config()
                )

        self.assertEqual(judge.call_count, 1)
        self.assertEqual(
            first["judge_request_fingerprint"], second["judge_request_fingerprint"]
        )

    def test_changed_request_shape_rejudges_without_reusing_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = _write_native_run(Path(temporary_directory))
            with patch(
                "asterion.dci.evaluation.judge_answer_sync", return_value=_verdict()
            ) as judge:
                evaluate_run_directory(
                    output_dir, gold_answer="gold", judge_config=_config()
                )
                evaluate_run_directory(
                    output_dir, gold_answer="changed", judge_config=_config()
                )

        self.assertEqual(judge.call_count, 2)

    def test_persists_only_safe_evaluation_state_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = _write_native_run(Path(temporary_directory))
            with patch(
                "asterion.dci.evaluation.judge_answer_sync", return_value=_verdict()
            ):
                evaluate_run_directory(
                    output_dir, gold_answer="gold", judge_config=_config()
                )
            state = json.loads((output_dir / "state.json").read_text())

        self.assertTrue(state["evaluation"]["is_correct"])
        self.assertNotIn("api_key", repr(state["evaluation"]))
        self.assertNotIn("SECRET", repr(state["evaluation"]))

    def test_invalid_native_state_fails_before_judge_transport(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            output_dir.mkdir()
            (output_dir / "state.json").write_text(
                '{"status":"failed","question":"SECRET"}'
            )
            with patch("asterion.dci.evaluation.judge_answer_sync") as judge:
                with self.assertRaisesRegex(
                    DciEvaluationError, "evaluation failed"
                ) as raised:
                    evaluate_run_directory(
                        output_dir, gold_answer="gold", judge_config=_config()
                    )

        judge.assert_not_called()
        self.assertNotIn("SECRET", str(raised.exception))

    def test_concurrent_evaluators_share_writer_lock_and_one_judge(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = _write_native_run(Path(temporary_directory))
            entered = threading.Event()
            release = threading.Event()
            results = []

            def judged(**_kwargs: object) -> dict[str, object]:
                entered.set()
                release.wait(2)
                return _verdict()

            def evaluate() -> None:
                results.append(
                    evaluate_run_directory(
                        output_dir, gold_answer="gold", judge_config=_config()
                    )
                )

            with patch(
                "asterion.dci.evaluation.judge_answer_sync", side_effect=judged
            ) as judge:
                first = threading.Thread(target=evaluate)
                second = threading.Thread(target=evaluate)
                first.start()
                self.assertTrue(entered.wait(1))
                second.start()
                time.sleep(0.05)
                self.assertEqual(judge.call_count, 1)
                release.set()
                first.join()
                second.join()
            self.assertEqual(len(results), 2)
            self.assertEqual(judge.call_count, 1)

    def test_malformed_or_symlink_evidence_fails_before_judge_without_mutation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = _write_native_run(root)
            before = {
                p.name: p.read_bytes() for p in output_dir.iterdir() if p.is_file()
            }
            (output_dir / "final.txt").unlink()
            (output_dir / "final.txt").symlink_to(root / "secret")
            with patch("asterion.dci.evaluation.judge_answer_sync") as judge:
                with self.assertRaises(DciEvaluationError):
                    evaluate_run_directory(
                        output_dir, gold_answer="gold", judge_config=_config()
                    )
            judge.assert_not_called()
            self.assertFalse((output_dir / "eval_result.json").exists())
            self.assertEqual(
                before["state.json"], (output_dir / "state.json").read_bytes()
            )

    def test_malformed_cache_and_digest_mismatch_fail_before_judge(self) -> None:
        for target in ("eval_result.json", "final.txt"):
            with (
                self.subTest(target=target),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                output_dir = _write_native_run(Path(temporary_directory))
                if target == "eval_result.json":
                    (output_dir / target).write_text("{bad", encoding="utf-8")
                else:
                    (output_dir / target).write_text("changed\n", encoding="utf-8")
                state_before = (output_dir / "state.json").read_bytes()
                with patch("asterion.dci.evaluation.judge_answer_sync") as judge:
                    with self.assertRaises(DciEvaluationError):
                        evaluate_run_directory(
                            output_dir, gold_answer="gold", judge_config=_config()
                        )
                judge.assert_not_called()
                self.assertEqual(state_before, (output_dir / "state.json").read_bytes())

    def test_async_cancellation_drains_http_before_releasing_writer_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = _write_native_run(Path(temporary_directory))
            started = threading.Event()
            release = threading.Event()

            def blocking(**kwargs: object) -> dict[str, object]:
                started.set()
                release.wait(2)
                if kwargs["cancel_event"].is_set():
                    raise DciJudgeError("cancelled")
                return _verdict()

            async def scenario() -> None:
                with patch(
                    "asterion.dci.evaluation.judge_answer_sync", side_effect=blocking
                ):
                    task = asyncio.create_task(
                        evaluate_run_directory_async(
                            output_dir, gold_answer="gold", judge_config=_config()
                        )
                    )
                    await asyncio.to_thread(started.wait, 1)
                    task.cancel()
                    await asyncio.sleep(0)
                    self.assertFalse(task.done())
                    task.cancel()
                    await asyncio.sleep(0)
                    self.assertFalse(task.done())
                    with self.assertRaises(DciArtifactError):
                        DciRunLock.acquire_existing(output_dir, wait=False)
                    release.set()
                    with self.assertRaises(asyncio.CancelledError):
                        await task

            asyncio.run(scenario())
            self.assertFalse((output_dir / "eval_result.json").exists())
            lock = DciRunLock.acquire_existing(output_dir, wait=False)
            lock.release()

    def test_scripts_bcplus_eval_run_bcplus_eval_py_cache_rule_completed_native_run_judge_only(
        self,
    ) -> None:
        self.test_reuses_only_an_exact_judge_request_fingerprint()

    def test_scripts_bcplus_eval_run_bcplus_eval_py_cache_rule_completed_result_exact_judge_config(
        self,
    ) -> None:
        self.test_changed_request_shape_rejudges_without_reusing_cache()

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_build_failed_judge_result(
        self,
    ) -> None:
        self.test_invalid_native_state_fails_before_judge_transport()

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_judge_result_succeeded(
        self,
    ) -> None:
        self.test_reuses_only_an_exact_judge_request_fingerprint()


def _config() -> JudgeConfig:
    return JudgeConfig(base_url="https://judge.example.test/v1", model="fixture")


def _verdict() -> dict[str, object]:
    return {
        **_config().public_dict(),
        "judged_at": "2026-07-13T00:00:00+00:00",
        "attempts": 1,
        "judge_request_fingerprint": "transport-value-is-replaced",
        "is_correct": True,
        "normalized_prediction": "answer",
        "reason": "same",
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "cost_estimate_usd": {
            "input_cost": 0.0,
            "cached_input_cost": 0.0,
            "output_cost": 0.0,
            "total_cost": 0.0,
        },
    }


def _write_native_run(root: Path) -> Path:
    root = root.resolve()
    output_dir = root / "run"
    recorder = DciRunRecorder(
        output_dir=output_dir,
        request=DciRunRequest(run_id="run-1", question="question", cwd=root),
        paths=resolve_dci_paths(root),
    )
    recorder.record_event(
        {
            "type": "message_update",
            "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
        }
    )
    recorder.finalize(status="completed", final_text="answer")
    return output_dir


if __name__ == "__main__":
    unittest.main()
