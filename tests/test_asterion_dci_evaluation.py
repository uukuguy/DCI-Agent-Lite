from __future__ import annotations

import asyncio
import hashlib
import json
import math
import tempfile
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import asterion.dci.artifacts as artifacts
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

    def test_completed_evidence_mutations_fail_before_judge_without_mutation(
        self,
    ) -> None:
        for mutation in ("terminal_status", "protocol_text", "conversation_shape"):
            with (
                self.subTest(mutation=mutation),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                output_dir = _write_native_run(Path(temporary_directory))
                if mutation in {"terminal_status", "protocol_text"}:
                    path = output_dir / "protocol/attempt-0001.events.jsonl"
                    events = [
                        json.loads(line) for line in path.read_text().splitlines()
                    ]
                    if mutation == "terminal_status":
                        events[-1]["payload"]["status"] = "cancelled"
                    else:
                        next(
                            event for event in events if event["type"] == "text.delta"
                        )["payload"]["text"] = "SECRET-FORGED"
                    path.write_text(
                        "".join(json.dumps(event) + "\n" for event in events),
                        encoding="utf-8",
                    )
                else:
                    path = output_dir / "conversation.json"
                    value = json.loads(path.read_text())
                    value["messages"] = "SECRET-FORGED"
                    path.write_text(json.dumps(value), encoding="utf-8")
                before = _snapshot(output_dir)
                with patch("asterion.dci.evaluation.judge_answer_sync") as judge:
                    with self.assertRaises(DciEvaluationError) as raised:
                        evaluate_run_directory(
                            output_dir, gold_answer="gold", judge_config=_config()
                        )
                judge.assert_not_called()
                self.assertEqual(before, _snapshot(output_dir))
                self.assertNotIn("SECRET", str(raised.exception))

    def test_cache_usage_and_cost_arithmetic_must_be_exact(self) -> None:
        mutations = {
            "token_total": lambda result: result["usage"].__setitem__(
                "total_tokens", 999
            ),
            "cached_overflow": lambda result: result["usage"][
                "input_tokens_details"
            ].__setitem__("cached_tokens", 99),
            "token_bool": lambda result: result["usage"].__setitem__(
                "input_tokens", True
            ),
            "token_negative": lambda result: result["usage"].__setitem__(
                "output_tokens", -1
            ),
            "token_nonfinite": lambda result: result["usage"].__setitem__(
                "total_tokens", math.inf
            ),
            "input_cost": lambda result: result["cost_estimate_usd"].__setitem__(
                "input_cost", 1.0
            ),
            "cached_cost": lambda result: result["cost_estimate_usd"].__setitem__(
                "cached_input_cost", 1.0
            ),
            "output_cost": lambda result: result["cost_estimate_usd"].__setitem__(
                "output_cost", 1.0
            ),
            "total_cost": lambda result: result["cost_estimate_usd"].__setitem__(
                "total_cost", 1.0
            ),
            "cost_bool": lambda result: result["cost_estimate_usd"].__setitem__(
                "total_cost", True
            ),
            "cost_negative": lambda result: result["cost_estimate_usd"].__setitem__(
                "output_cost", -1.0
            ),
            "cost_nonfinite": lambda result: result["cost_estimate_usd"].__setitem__(
                "input_cost", math.nan
            ),
        }
        for name, mutate in mutations.items():
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                output_dir = _write_native_run(Path(temporary_directory))
                with patch(
                    "asterion.dci.evaluation.judge_answer_sync",
                    return_value=_priced_verdict(),
                ) as judge:
                    evaluate_run_directory(
                        output_dir, gold_answer="gold", judge_config=_config()
                    )
                    result = json.loads((output_dir / "eval_result.json").read_text())
                    mutate(result)
                    _write_bound_cache(output_dir, result)
                    evaluate_run_directory(
                        output_dir, gold_answer="gold", judge_config=_config()
                    )
                self.assertEqual(judge.call_count, 2)

    def test_pair_transaction_failure_boundaries_never_expose_split_commit(
        self,
    ) -> None:
        cases = (
            ("prepare_eval", "_prepare_json_at", 1),
            ("prepare_state", "_prepare_json_at", 2),
            ("write_eval", "_write_prepared_bytes", 1),
            ("write_state", "_write_prepared_bytes", 2),
            ("publish_state", "_publish_prepared_at", 1),
            ("publish_eval", "_publish_prepared_at", 2),
            ("fsync_eval", "os.fsync", 1),
            ("fsync_state", "os.fsync", 2),
            ("fsync_directory", "os.fsync", 3),
        )
        for name, patch_name, fail_at in cases:
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                output_dir = _write_native_run(Path(temporary_directory))
                target = (
                    getattr(artifacts, patch_name.split(".")[-1])
                    if "." not in patch_name
                    else artifacts.os.fsync
                )
                calls = 0

                def fail_boundary(*args: object, **kwargs: object) -> object:
                    nonlocal calls
                    calls += 1
                    if calls == fail_at:
                        raise OSError("SECRET injected failure")
                    return target(*args, **kwargs)

                with patch(
                    f"asterion.dci.artifacts.{patch_name}", side_effect=fail_boundary
                ):
                    with patch(
                        "asterion.dci.evaluation.judge_answer_sync",
                        return_value=_verdict(),
                    ):
                        with self.assertRaises(DciEvaluationError) as raised:
                            evaluate_run_directory(
                                output_dir, gold_answer="gold", judge_config=_config()
                            )
                self.assertNotIn("SECRET", str(raised.exception))
                self.assertFalse(
                    any("evaluation-tmp" in path.name for path in output_dir.iterdir())
                )
                _assert_no_split_pair(output_dir)
                with patch(
                    "asterion.dci.evaluation.judge_answer_sync", return_value=_verdict()
                ):
                    evaluate_run_directory(
                        output_dir, gold_answer="gold", judge_config=_config()
                    )
                _assert_committed_pair(output_dir)

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
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = _write_native_run(Path(temporary_directory))
            with patch(
                "asterion.dci.judge._open_judge_request",
                side_effect=urllib.error.URLError("SECRET provider body"),
            ) as opened:
                with patch("asterion.dci.judge._wait_before_retry"):
                    for _ in range(2):
                        with self.assertRaises(DciEvaluationError) as raised:
                            evaluate_run_directory(
                                output_dir,
                                gold_answer="gold",
                                judge_config=_config(),
                            )
                        self.assertNotIn("SECRET", str(raised.exception))
            self.assertEqual(opened.call_count, 6)
            self.assertFalse((output_dir / "eval_result.json").exists())
            self.assertNotIn(
                "evaluation", json.loads((output_dir / "state.json").read_text())
            )

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


def _priced_verdict() -> dict[str, object]:
    value = _verdict()
    value["usage"] = {
        "input_tokens": 10,
        "output_tokens": 4,
        "total_tokens": 14,
        "input_tokens_details": {"cached_tokens": 2},
    }
    value["cost_estimate_usd"] = {
        "input_cost": 8 / 1_000_000 * _config().input_price_per_1m,
        "cached_input_cost": 2 / 1_000_000 * _config().cached_input_price_per_1m,
        "output_cost": 4 / 1_000_000 * _config().output_price_per_1m,
        "total_cost": (
            8 / 1_000_000 * _config().input_price_per_1m
            + 2 / 1_000_000 * _config().cached_input_price_per_1m
            + 4 / 1_000_000 * _config().output_price_per_1m
        ),
    }
    return value


def _write_bound_cache(output_dir: Path, result: dict[str, object]) -> None:
    raw = artifacts.json_document_bytes(result)
    (output_dir / "eval_result.json").write_bytes(raw)
    state = json.loads((output_dir / "state.json").read_text())
    state["evaluation"].update(
        {
            "usage": result["usage"],
            "cost_estimate_usd": result["cost_estimate_usd"],
            "eval_result_sha256": hashlib.sha256(raw).hexdigest(),
        }
    )
    (output_dir / "state.json").write_bytes(artifacts.json_document_bytes(state))


def _snapshot(output_dir: Path) -> dict[str, bytes]:
    return {
        str(path.relative_to(output_dir)): path.read_bytes()
        for path in output_dir.rglob("*")
        if path.is_file()
    }


def _assert_no_split_pair(output_dir: Path) -> None:
    eval_path = output_dir / "eval_result.json"
    state = json.loads((output_dir / "state.json").read_text())
    if not eval_path.exists():
        return
    result = json.loads(eval_path.read_text())
    binding = state.get("evaluation")
    assert isinstance(binding, dict)
    raw = eval_path.read_bytes()
    assert binding.get("eval_result_sha256") == hashlib.sha256(raw).hexdigest()
    assert binding.get("evaluation_commit_id") == result.get("evaluation_commit_id")


def _assert_committed_pair(output_dir: Path) -> None:
    eval_path = output_dir / "eval_result.json"
    state = json.loads((output_dir / "state.json").read_text())
    result = json.loads(eval_path.read_text())
    binding = state["evaluation"]
    assert (
        binding["eval_result_sha256"]
        == hashlib.sha256(eval_path.read_bytes()).hexdigest()
    )
    assert binding["evaluation_commit_id"] == result["evaluation_commit_id"]
    assert (eval_path.stat().st_mode & 0o777) == 0o600
    assert ((output_dir / "state.json").stat().st_mode & 0o777) == 0o600


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
