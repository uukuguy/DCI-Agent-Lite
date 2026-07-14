from __future__ import annotations

import asyncio
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock, patch

from asterion.dci.benchmark import (
    BenchmarkRequest,
    DciBenchmarkError,
    _Directory,
    _next_generation,
    _prepare,
    run_benchmark_async,
)
from asterion.dci.artifacts import DciConversationFeatures
from asterion.dci.config import DciRuntimeOptions, resolve_dci_paths
from asterion.dci.judge import JudgeConfig
from asterion.dci.run import DciRunResult
from asterion.runtime.host import RunEvent


class _FixtureClient:
    def __init__(self, **_kwargs: object) -> None:
        pass

    def start(self) -> None:
        pass

    def prompt_and_wait(self, _message: str, *, on_event, **_kwargs: object) -> str:
        for event in (
            {"type": "response", "id": "py-1", "success": True},
            {"type": "agent_start"},
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
            },
            {"type": "agent_end"},
        ):
            on_event(event)
        return "answer"

    def get_stderr(self) -> str:
        return ""

    def stop(self) -> None:
        pass


class _FailingFixtureClient(_FixtureClient):
    def prompt_and_wait(self, _message: str, *, on_event, **_kwargs: object) -> str:
        raise RuntimeError("fixture failure")


class AsterionDciBatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_forged_native_generation_cannot_escape_query_authority(self) -> None:
        for attack in ("../foreign", "/absolute/foreign", "nested/foreign"):
            with self.subTest(attack=attack), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory).resolve()
                request = _request(root, mode="ir", ir=True)
                with patch("asterion.dci.run.PiRpcClient", _FixtureClient):
                    await run_benchmark_async(request, paths=resolve_dci_paths(root))
                result_path = request.output_root / "q-0" / "result.json"
                result = json.loads(result_path.read_text())
                native = request.output_root / "q-0" / result["native_generation"]
                if attack == "../foreign":
                    native.rename(request.output_root / "foreign")
                elif attack.startswith("/"):
                    foreign = root / "absolute-foreign"
                    native.rename(foreign)
                    attack = str(foreign)
                else:
                    nested = request.output_root / "q-0" / "nested"
                    nested.mkdir()
                    native.rename(nested / "foreign")
                result["native_generation"] = attack
                result_path.write_text(json.dumps(result))
                with self.assertRaisesRegex(DciBenchmarkError, "result evidence is invalid"):
                    await run_benchmark_async(request, paths=resolve_dci_paths(root))

    async def test_native_generation_symlink_is_rejected_but_safe_component_reuses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root, mode="ir", ir=True)
            with patch("asterion.dci.run.PiRpcClient", _FixtureClient):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            result_path = request.output_root / "q-0" / "result.json"
            result = json.loads(result_path.read_text())
            safe_generation = result["native_generation"]
            with patch("asterion.dci.benchmark._run_pi_async") as run:
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            run.assert_not_called()
            symlink_generation = "native-generation-9999"
            (request.output_root / "q-0" / symlink_generation).symlink_to(safe_generation)
            result["native_generation"] = symlink_generation
            result_path.write_text(json.dumps(result))
            with self.assertRaisesRegex(DciBenchmarkError, "destination is unsafe"):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))

    async def test_forged_result_never_reuses_without_native_evaluation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            request = _request(Path(temporary_directory))
            _rows, _root, config, items, _snapshots = _prepare(request)
            request.output_root.mkdir(mode=0o700)
            query = request.output_root / "q-0"
            query.mkdir(mode=0o700)
            (request.output_root / "config.json").write_text(json.dumps(config))
            (query / "item.json").write_text(json.dumps(items[0]))
            (query / "result.json").write_text(json.dumps({
                "schema": "wrong", "query_id": "attacker", "status": "completed",
                "row_fingerprint": items[0]["row_fingerprint"], "is_correct": True,
                "judge_configuration_fingerprint": items[0]["judge_configuration_fingerprint"],
                "extra": "forged",
            }))
            with patch("asterion.dci.benchmark._run_pi_async") as run, patch(
                "asterion.dci.benchmark.evaluate_run_directory_async"
            ) as evaluate:
                with self.assertRaises(DciBenchmarkError):
                    await run_benchmark_async(request, paths=Mock())
            run.assert_not_called()
            evaluate.assert_not_called()

    async def test_root_rebinding_keeps_native_and_aggregates_on_locked_inode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            moved = root / "moved"

            async def run_native(_paths: object, native_request: object, *, output_dir: Path, **_kwargs: object) -> DciRunResult:
                request.output_root.rename(moved)
                request.output_root.mkdir(mode=0o700)
                descriptor = os.open(
                    "provider-marker",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=_kwargs["output_directory_fd"],
                )
                os.write(descriptor, b"provider")
                os.close(descriptor)
                return _result(Path(output_dir))

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ):
                await run_benchmark_async(request, paths=Mock())
            self.assertTrue((moved / "summary.json").is_file())
            self.assertTrue(tuple(moved.glob("q-0/**/provider-marker")))
            self.assertFalse(tuple(request.output_root.glob("q-0/**/provider-marker")))

    async def test_query_rebinding_keeps_result_on_locked_query_inode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            moved_query = request.output_root / "moved-query"

            async def run_native(
                _paths: object,
                _native_request: object,
                *,
                output_dir: Path,
                **kwargs: object,
            ) -> DciRunResult:
                (request.output_root / "q-0").rename(moved_query)
                (request.output_root / "q-0").mkdir(mode=0o700)
                descriptor = os.open(
                    "provider-marker",
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL,
                    0o600,
                    dir_fd=kwargs["output_directory_fd"],
                )
                os.write(descriptor, b"provider")
                os.close(descriptor)
                return _result(Path(output_dir))

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ):
                await run_benchmark_async(request, paths=Mock())
            self.assertTrue((moved_query / "result.json").is_file())
            self.assertTrue(tuple(moved_query.glob("native-generation-*/provider-marker")))
            self.assertFalse((request.output_root / "q-0" / "result.json").exists())

    async def test_cancellation_publishes_terminal_batch_and_not_started_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            request = _request(Path(temporary_directory), rows=2, max_concurrency=1)
            entered = asyncio.Event()

            async def run_native(*_args: object, **_kwargs: object) -> DciRunResult:
                entered.set()
                await asyncio.Future()

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native):
                task = asyncio.create_task(run_benchmark_async(request, paths=Mock()))
                await entered.wait()
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            state = json.loads((request.output_root / "batch-state.json").read_text())
            results = [json.loads(line) for line in (request.output_root / "results.jsonl").read_text().splitlines()]
            self.assertEqual(state["status"], "cancelled")
            self.assertEqual([row["status"] for row in results], ["cancelled", "not_started"])

    async def test_cancelled_batch_compatible_rerun_completes_without_forged_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            request = _request(Path(temporary_directory))
            entered = asyncio.Event()

            async def block(*_args: object, **_kwargs: object) -> DciRunResult:
                entered.set()
                await asyncio.Future()

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=block):
                task = asyncio.create_task(run_benchmark_async(request, paths=Mock()))
                await entered.wait()
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

            calls: list[Path] = []

            async def complete(
                _paths: object,
                _native_request: object,
                *,
                output_dir: Path,
                **_kwargs: object,
            ) -> DciRunResult:
                calls.append(output_dir)
                return _result(output_dir)

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=complete), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ):
                result = await run_benchmark_async(request, paths=Mock())
            durable = json.loads((request.output_root / "q-0" / "result.json").read_text())
            self.assertEqual(len(calls), 1)
            self.assertEqual(durable["status"], "completed")
            self.assertEqual(result.counts, {"total": 1, "correct": 1, "failed": 0})

    async def test_fresh_policy_creates_new_generation_and_never_reuses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            request = _request(Path(temporary_directory))
            calls: list[Path] = []

            async def run_native(_paths: object, _native_request: object, *, output_dir: Path, **_kwargs: object) -> DciRunResult:
                calls.append(Path(output_dir))
                return _result(Path(output_dir))

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ):
                await run_benchmark_async(request, paths=Mock())
                await run_benchmark_async(replace(request, resume_policy="fresh"), paths=Mock())
            self.assertEqual(len(calls), 2)
            self.assertNotEqual(calls[0], calls[1])

    async def test_prompt_resources_are_immutable_private_snapshots(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            prompt = root / "system.md"
            prompt.write_text("trusted")
            request = replace(_request(root), system_prompt_file=prompt)

            async def run_native(_paths: object, native_request: object, **_kwargs: object) -> DciRunResult:
                prompt.write_text("changed-after-fingerprint")
                snapshot = _kwargs["system_prompt_override"]
                self.assertEqual(snapshot.read_text(), "trusted")
                self.assertEqual(native_request.system_prompt_file, prompt)
                return _result(Path(_kwargs["output_dir"]))

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ):
                await run_benchmark_async(request, paths=Mock())

    async def test_config_and_item_self_fingerprint_forgery_fails_before_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            request = _request(Path(temporary_directory))
            with patch("asterion.dci.benchmark._run_pi_async", return_value=_result(request.output_root / "q-0")), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ):
                await run_benchmark_async(request, paths=Mock())
            config_path = request.output_root / "config.json"
            item_path = request.output_root / "q-0" / "item.json"
            config = json.loads(config_path.read_text())
            item = json.loads(item_path.read_text())
            config["runtime"]["provider"] = "attacker"
            item["prompt"] = "attacker prompt"
            config_path.write_text(json.dumps(config))
            item_path.write_text(json.dumps(item))
            with patch("asterion.dci.benchmark._run_pi_async") as run:
                with self.assertRaises(DciBenchmarkError):
                    await run_benchmark_async(request, paths=Mock())
            run.assert_not_called()

    async def test_batch_native_worker_preserves_the_complete_run_artifact_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)

            class FixtureClient:
                def __init__(self, **_kwargs: object) -> None:
                    pass

                def start(self) -> None:
                    pass

                def prompt_and_wait(self, _message: str, *, on_event, **_kwargs: object) -> str:
                    for event in (
                        {"type": "response", "id": "py-1", "success": True},
                        {"type": "agent_start"},
                        {"type": "message_update", "assistantMessageEvent": {"type": "text_delta", "delta": "answer"}},
                        {"type": "agent_end"},
                    ):
                        on_event(event)
                    return "answer"

                def get_stderr(self) -> str:
                    return ""

                def stop(self) -> None:
                    pass

            with patch("asterion.dci.run.PiRpcClient", FixtureClient), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            result = json.loads((request.output_root / "q-0" / "result.json").read_text())
            query = request.output_root / "q-0" / result["native_generation"]
            for name in (
                "conversation_full.json",
                "conversation.json",
                "events.jsonl",
                "final.txt",
                "latest_model_context.json",
                "question.txt",
                "state.json",
                "stderr.txt",
            ):
                with self.subTest(name=name):
                    self.assertTrue((query / name).is_file())
                    self.assertEqual((query / name).stat().st_mode & 0o777, 0o600)

    async def test_docs_superpowers_plans_2026_07_14_af_240_batch_evaluation_export_parity_md_target_feature_cooperative_cancellation(self) -> None:
        await self.test_batch_lock_is_retained_until_cancelled_native_work_drains()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_cache_rule_dataset_order_aggregate_publication(self) -> None:
        await self.test_bounds_live_native_calls_and_orders_incremental_results()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_cache_rule_failed_or_incomplete_compatible_resume(self) -> None:
        await self.test_compatible_failed_run_resupplies_private_args_to_resume()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_cache_rule_malformed_evidence_fail_closed(self) -> None:
        await self.test_malformed_completed_evidence_becomes_safe_failed_result()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_config_json(self) -> None:
        await self.test_persisted_config_allowlists_runtime_and_fingerprints_raw_extra_args()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_input_question_txt(self) -> None:
        await self.test_bounds_live_native_calls_and_orders_incremental_results()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_item_json(self) -> None:
        await self.test_changed_row_fails_before_mutation_or_provider()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_result_json(self) -> None:
        await self.test_sibling_failure_is_a_safe_result()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_results_jsonl(self) -> None:
        await self.test_bounds_live_native_calls_and_orders_incremental_results()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_summary_json(self) -> None:
        await self.test_bounds_live_native_calls_and_orders_incremental_results()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_conversation_full_json(self) -> None:
        await self.test_batch_native_worker_preserves_the_complete_run_artifact_boundary()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_conversation_json(self) -> None:
        await self.test_batch_native_worker_preserves_the_complete_run_artifact_boundary()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_events_jsonl(self) -> None:
        await self.test_batch_native_worker_preserves_the_complete_run_artifact_boundary()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_final_txt(self) -> None:
        await self.test_batch_native_worker_preserves_the_complete_run_artifact_boundary()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_latest_model_context_json(self) -> None:
        await self.test_batch_native_worker_preserves_the_complete_run_artifact_boundary()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_question_txt(self) -> None:
        await self.test_batch_native_worker_preserves_the_complete_run_artifact_boundary()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_state_json(self) -> None:
        await self.test_batch_native_worker_preserves_the_complete_run_artifact_boundary()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_stderr_txt(self) -> None:
        await self.test_batch_native_worker_preserves_the_complete_run_artifact_boundary()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_aggregate_results(self) -> None:
        await self.test_bounds_live_native_calls_and_orders_incremental_results()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_existing_result_succeeded(self) -> None:
        await self.test_exact_result_is_reused_without_native_or_judge_work()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_existing_run_has_error(self) -> None:
        await self.test_malformed_completed_evidence_becomes_safe_failed_result()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_has_core_run_artifacts(self) -> None:
        await self.test_batch_native_worker_preserves_the_complete_run_artifact_boundary()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_load_existing_query_result(self) -> None:
        await self.test_exact_result_is_reused_without_native_or_judge_work()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_main(self) -> None:
        await self.test_bounds_live_native_calls_and_orders_incremental_results()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_main_async(self) -> None:
        await self.test_bounds_live_native_calls_and_orders_incremental_results()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_persist_aggregate(self) -> None:
        await self.test_bounds_live_native_calls_and_orders_incremental_results()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_prepare_query_dir_for_run(self) -> None:
        await self.test_changed_row_fails_before_mutation_or_provider()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_query_needs_execution_or_judging(self) -> None:
        await self.test_stale_judge_configuration_is_judge_only()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_run_single_query(self) -> None:
        await self.test_sibling_failure_is_a_safe_result()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_worker(self) -> None:
        await self.test_bounds_live_native_calls_and_orders_incremental_results()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_write_json(self) -> None:
        await self.test_persisted_config_allowlists_runtime_and_fingerprints_raw_extra_args()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_write_jsonl(self) -> None:
        await self.test_bounds_live_native_calls_and_orders_incremental_results()

    async def test_bounds_live_native_calls_and_orders_incremental_results(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            request = _request(root, rows=4, max_concurrency=2)
            live = 0
            maximum = 0
            release = asyncio.Event()

            async def run_native(_paths: object, native_request: object, **_kwargs: object) -> DciRunResult:
                nonlocal live, maximum
                live += 1
                maximum = max(maximum, live)
                if maximum == 2:
                    release.set()
                await release.wait()
                await asyncio.sleep(0.01 * (4 - int(native_request.run_id.removeprefix("q-"))))
                live -= 1
                return _result(request.output_root / native_request.run_id)

            async def evaluate(*_args: object, **_kwargs: object) -> dict[str, object]:
                return {"is_correct": True, "judge_request_fingerprint": "f" * 64}

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async", side_effect=evaluate
            ):
                result = await run_benchmark_async(request, paths=Mock())

            self.assertEqual(maximum, 2)
            rows = [json.loads(line) for line in (result.output_root / "results.jsonl").read_text().splitlines()]
            self.assertEqual([row["query_id"] for row in rows], ["q-0", "q-1", "q-2", "q-3"])
            self.assertEqual(result.counts, {"total": 4, "correct": 4, "failed": 0})
            config = json.loads((result.output_root / "config.json").read_text())
            item = json.loads((result.output_root / "q-0" / "item.json").read_text())
            summary = json.loads((result.output_root / "summary.json").read_text())
            self.assertEqual(config["schema"], "asterion.dci.batch/v1")
            self.assertEqual(item["schema"], "asterion.dci.batch-item/v1")
            self.assertEqual(item["query_id"], "q-0")
            self.assertEqual((result.output_root / "q-0" / "input_question.txt").read_text(), "question 0")
            self.assertEqual(summary["counts"], result.counts)
            self.assertEqual((result.output_root.stat().st_mode & 0o777), 0o700)
            private_files = [
                result.output_root / name
                for name in ("config.json", "results.jsonl", "summary.json")
            ] + [
                result.output_root / f"q-{index}" / name
                for index in range(4)
                for name in ("item.json", "input_question.txt", "result.json")
            ]
            self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in private_files))

    async def test_sibling_failure_is_a_safe_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            request = _request(root, rows=2)

            async def run_native(_paths: object, native_request: object, **_kwargs: object) -> DciRunResult:
                if native_request.run_id == "q-0":
                    raise RuntimeError("secret provider body")
                return _result(request.output_root / native_request.run_id)

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ):
                result = await run_benchmark_async(request, paths=Mock())

            failed = json.loads((request.output_root / "q-0" / "result.json").read_text())
            self.assertEqual(failed["status"], "failed")
            self.assertNotIn("secret", json.dumps(failed))
            self.assertEqual(result.counts, {"total": 2, "correct": 1, "failed": 1})

    async def test_changed_row_fails_before_mutation_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            original = _request(root)
            with patch("asterion.dci.benchmark._run_pi_async", return_value=_result(original.output_root / "q-0")), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ):
                await run_benchmark_async(original, paths=Mock())
            before = (original.output_root / "q-0" / "item.json").read_bytes()
            original.dataset.write_text(json.dumps({"query_id": "q-0", "query": "changed", "answer": "gold"}) + "\n")
            with patch("asterion.dci.benchmark._run_pi_async") as run:
                with self.assertRaisesRegex(DciBenchmarkError, "incompatible"):
                    await run_benchmark_async(original, paths=Mock())
            run.assert_not_called()
            self.assertEqual((original.output_root / "q-0" / "item.json").read_bytes(), before)

    async def test_persisted_config_allowlists_runtime_and_fingerprints_raw_extra_args(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            request = _request(root, extra_args=("--token super-secret",))
            with patch("asterion.dci.benchmark._run_pi_async", return_value=_result(request.output_root / "q-0")), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ):
                await run_benchmark_async(request, paths=Mock())
            text = (request.output_root / "config.json").read_text()
            self.assertNotIn("super-secret", text)
            config = json.loads(text)
            self.assertEqual(config["runtime"]["extra_args_count"], 1)
            self.assertRegex(config["runtime"]["extra_args_fingerprint"], r"^[0-9a-f]{64}$")

    async def test_ir_skips_judge_and_requires_gold_documents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            request = _request(root, mode="ir", ir=True)
            with patch("asterion.dci.benchmark._run_pi_async", return_value=_result(request.output_root / "q-0")), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async"
            ) as evaluate:
                result = await run_benchmark_async(request, paths=Mock())
            evaluate.assert_not_called()
            self.assertEqual(result.counts["correct"], 0)

    async def test_exact_result_is_reused_without_native_or_judge_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            with patch("asterion.dci.run.PiRpcClient", _FixtureClient), patch(
                "asterion.dci.evaluation.judge_answer_sync",
                return_value=_verdict(request.judge_config),
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            with patch("asterion.dci.benchmark._run_pi_async") as run, patch(
                "asterion.dci.benchmark.evaluate_run_directory_async"
            ) as evaluate:
                result = await run_benchmark_async(request, paths=resolve_dci_paths(root))
            run.assert_not_called()
            evaluate.assert_not_called()
            self.assertEqual(result.counts["correct"], 1)

    async def test_stale_judge_configuration_is_judge_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            with patch("asterion.dci.run.PiRpcClient", _FixtureClient), patch(
                "asterion.dci.evaluation.judge_answer_sync",
                return_value=_verdict(request.judge_config),
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            changed = replace(request, judge_config=JudgeConfig(base_url="https://other.example.test/v1"))
            with patch("asterion.dci.benchmark._run_pi_async") as run, patch(
                "asterion.dci.evaluation.judge_answer_sync",
                return_value=_verdict(changed.judge_config, correct=False),
            ) as evaluate:
                result = await run_benchmark_async(changed, paths=resolve_dci_paths(root))
            run.assert_not_called()
            evaluate.assert_called_once()
            self.assertEqual(result.counts["correct"], 0)

    async def test_completed_run_without_result_is_judge_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            with patch("asterion.dci.run.PiRpcClient", _FixtureClient), patch(
                "asterion.dci.evaluation.judge_answer_sync",
                return_value=_verdict(request.judge_config),
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            (request.output_root / "q-0" / "result.json").unlink()
            with patch("asterion.dci.benchmark._run_pi_async") as run, patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ) as evaluate:
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            run.assert_not_called()
            evaluate.assert_called_once()

    async def test_compatible_failed_run_resupplies_private_args_to_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root, extra_args=("--private value",))
            with patch("asterion.dci.run.PiRpcClient", _FailingFixtureClient):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            resumed = Mock(run_id="q-0")
            with patch(
                "asterion.dci.benchmark.resume_request_from_output_dir", return_value=resumed
            ) as reconstruct, patch(
                "asterion.dci.benchmark._run_pi_async", return_value=_result(request.output_root / "q-0")
            ) as run, patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            self.assertEqual(reconstruct.call_args.kwargs["extra_args"], ("--private value",))
            self.assertIs(run.call_args.args[1], resumed)

    async def test_malformed_completed_evidence_becomes_safe_failed_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            with patch("asterion.dci.run.PiRpcClient", _FixtureClient), patch(
                "asterion.dci.evaluation.judge_answer_sync",
                return_value=_verdict(request.judge_config),
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            result_path = request.output_root / "q-0" / "result.json"
            result = json.loads(result_path.read_text())
            query = request.output_root / "q-0" / result["native_generation"]
            (query / "state.json").write_text(json.dumps({"status": "completed"}))
            result_path.unlink()
            with patch("asterion.dci.benchmark._run_pi_async") as run:
                result = await run_benchmark_async(request, paths=resolve_dci_paths(root))
            run.assert_not_called()
            self.assertEqual(result.counts["failed"], 1)
            self.assertNotIn("private", (request.output_root / "q-0" / "result.json").read_text())

    async def test_cancellation_drains_native_work_before_returning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            request = _request(root)
            entered = asyncio.Event()
            drained = asyncio.Event()

            async def run_native(*_args: object, **_kwargs: object) -> DciRunResult:
                entered.set()
                try:
                    await asyncio.Future()
                finally:
                    await asyncio.sleep(0.02)
                    drained.set()

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native):
                task = asyncio.create_task(run_benchmark_async(request, paths=Mock()))
                await entered.wait()
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
                self.assertTrue(drained.is_set())
                terminal = json.loads((request.output_root / "q-0" / "result.json").read_text())
                self.assertEqual(terminal["status"], "cancelled")

    async def test_batch_lock_is_retained_until_cancelled_native_work_drains(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            request = _request(Path(temporary_directory))
            entered = asyncio.Event()
            finish_drain = asyncio.Event()

            async def run_native(*_args: object, **_kwargs: object) -> DciRunResult:
                entered.set()
                try:
                    await asyncio.Future()
                finally:
                    await finish_drain.wait()
                raise AssertionError("unreachable")

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native):
                task = asyncio.create_task(run_benchmark_async(request, paths=Mock()))
                await entered.wait()
                task.cancel()
                await asyncio.sleep(0)
                with self.assertRaisesRegex(DciBenchmarkError, "already running"):
                    await run_benchmark_async(request, paths=Mock())
                finish_drain.set()
                with self.assertRaises(asyncio.CancelledError):
                    await task


class AsterionDciBatchValidationTests(unittest.TestCase):
    def test_descriptor_relative_name_apis_require_one_safe_component(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            descriptor = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            directory = _Directory(descriptor)
            try:
                attacks = ("", ".", "..", "../foreign", "nested/foreign", str(root / "absolute"), "nul\0name")
                operations = (
                    lambda name: directory.read_optional_json(name),
                    lambda name: directory.write_json(name, {}),
                    lambda name: directory.write_text(name, "value"),
                    lambda name: directory.write_bytes(name, b"value"),
                    lambda name: directory.open_query(name),
                    lambda name: directory.open_existing_query(name),
                )
                for name in attacks:
                    for operation in operations:
                        with self.subTest(name=name, operation=operation):
                            with self.assertRaises(DciBenchmarkError):
                                operation(name)
                directory.write_json("safe.json", {"safe": True})
                self.assertEqual(directory.read_optional_json("safe.json"), {"safe": True})
                child = directory.open_query("safe-child")
                child.close()
                (root / "unsafe-child").symlink_to(root / "safe-child", target_is_directory=True)
                with self.assertRaises(DciBenchmarkError):
                    directory.open_existing_query("unsafe-child")
            finally:
                directory.close()

    def test_generation_allocation_remains_in_grammar_after_9999(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            for name in ("native-generation-9998", "native-generation-9999"):
                (root / name).mkdir()
            directory = _Directory(os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)))
            try:
                self.assertEqual(_next_generation(directory), "native-generation-10000")
            finally:
                directory.close()

    def test_every_run_and_row_control_changes_its_schema_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            corpus_a = root / "corpus-a"
            corpus_b = root / "corpus-b"
            corpus_a.mkdir()
            corpus_b.mkdir()
            system = root / "system.md"
            append = root / "append.md"
            system.write_text("system one")
            append.write_text("append one")
            base = replace(
                _request(root),
                corpus=corpus_a,
                system_prompt_file=system,
                append_system_prompt_file=append,
            )
            _rows, _output, base_config, base_items, _snapshots = _prepare(base)
            base_run = base_config["run_fingerprint"]
            base_row = base_items[0]["row_fingerprint"]
            runtime = base.runtime_options
            mutations = {
                "profile": replace(base, profile="profile-b"),
                "corpus": replace(base, corpus=corpus_b),
                "corpus_hint": replace(base, corpus_hint="different structure"),
                "cwd": replace(base, cwd=root / "other-cwd"),
                "max_turns": replace(base, max_turns=7),
                "resume_policy": replace(base, resume_policy="fresh"),
                "provider": replace(base, runtime_options=replace(runtime, provider="p")),
                "model": replace(base, runtime_options=replace(runtime, model="m")),
                "tools": replace(base, runtime_options=replace(runtime, tools="read")),
                "timeout": replace(base, runtime_options=replace(runtime, timeout_seconds=1.0)),
                "context": replace(base, runtime_options=replace(runtime, runtime_context_level="level3")),
                "thinking": replace(base, runtime_options=replace(runtime, thinking_level="high")),
                "heap": replace(base, runtime_options=replace(runtime, node_max_old_space_size_mb=4096)),
                "session": replace(base, runtime_options=replace(runtime, keep_session=True)),
                "raw extras": replace(base, runtime_options=replace(runtime, extra_args=("--private",))),
                "clear tool results": replace(base, conversation_features=DciConversationFeatures(clear_tool_results=True)),
                "clear keep last": replace(base, conversation_features=DciConversationFeatures(clear_tool_results_keep_last=9)),
                "externalize": replace(base, conversation_features=DciConversationFeatures(externalize_tool_results=True)),
                "strip thinking": replace(base, conversation_features=DciConversationFeatures(strip_thinking=True)),
                "strip usage": replace(base, conversation_features=DciConversationFeatures(strip_usage=True)),
            }
            for name, changed in mutations.items():
                with self.subTest(name=name):
                    _rows, _output, config, items, _snapshots = _prepare(changed)
                    if name == "resume_policy":
                        self.assertEqual(config["run_fingerprint"], base_run)
                    else:
                        self.assertNotEqual(config["run_fingerprint"], base_run)
                        self.assertNotEqual(items[0]["row_fingerprint"], base_row)
            system.write_text("system two")
            _rows, _output, config, items, _snapshots = _prepare(base)
            self.assertNotEqual(config["run_fingerprint"], base_run)
            self.assertNotEqual(items[0]["row_fingerprint"], base_row)
            system.write_text("system one")
            append.write_text("append two")
            _rows, _output, config, items, _snapshots = _prepare(base)
            self.assertNotEqual(config["run_fingerprint"], base_run)
            self.assertNotEqual(items[0]["row_fingerprint"], base_row)
            ir = replace(_request(root, mode="ir", ir=True), corpus=corpus_a)
            _rows, _output, ir_config, ir_items, _snapshots = _prepare(ir)
            self.assertNotEqual(ir_config["run_fingerprint"], base_run)
            self.assertNotEqual(ir_items[0]["row_fingerprint"], base_row)

    def test_portable_collision_fails_before_output_creation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            dataset = root / "dataset.jsonl"
            dataset.write_text("\n".join(json.dumps({"query_id": qid, "query": qid, "answer": "gold"}) for qid in ("Q-01", "q-1")) + "\n")
            request = BenchmarkRequest(dataset=dataset, output_root=root / "out", cwd=root, judge_config=JudgeConfig(base_url="https://judge.example.test/v1"), runtime_options=DciRuntimeOptions(None, None))
            with self.assertRaisesRegex(DciBenchmarkError, "dataset"):
                asyncio.run(run_benchmark_async(request, paths=Mock()))
            self.assertFalse(request.output_root.exists())

    def test_symlink_output_component_is_rejected_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "target"
            target.mkdir()
            link = root / "link"
            link.symlink_to(target, target_is_directory=True)
            request = replace(_request(root), output_root=link / "out")
            with self.assertRaisesRegex(DciBenchmarkError, "unsafe"):
                asyncio.run(run_benchmark_async(request, paths=Mock()))
            self.assertFalse((target / "out").exists())

    def test_changed_nonselected_dataset_row_rejects_existing_config(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = replace(_request(root, rows=2), limit=1)
            with patch("asterion.dci.benchmark._run_pi_async", return_value=_result(request.output_root / "q-0")), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                return_value={"is_correct": True, "judge_request_fingerprint": "f" * 64},
            ):
                asyncio.run(run_benchmark_async(request, paths=Mock()))
            lines = request.dataset.read_text().splitlines()
            lines[1] = json.dumps({"query_id": "q-1", "query": "changed", "answer": "gold"})
            request.dataset.write_text("\n".join(lines) + "\n")
            with self.assertRaisesRegex(DciBenchmarkError, "configuration is incompatible"):
                asyncio.run(run_benchmark_async(request, paths=Mock()))


def _request(root: Path, *, rows: int = 1, max_concurrency: int = 1, mode: str = "qa", ir: bool = False, extra_args: tuple[str, ...] = ()) -> BenchmarkRequest:
    root = root.resolve()
    dataset = root / "dataset.jsonl"
    values = []
    for index in range(rows):
        value: dict[str, object] = {"query_id": f"q-{index}", "query": f"question {index}"}
        value["gold_docs" if ir else "answer"] = [f"doc-{index}"] if ir else "gold"
        values.append(value)
    dataset.write_text("\n".join(json.dumps(value) for value in values) + "\n")
    return BenchmarkRequest(dataset=dataset, output_root=root / "out", cwd=root, judge_config=JudgeConfig(base_url="https://judge.example.test/v1"), runtime_options=DciRuntimeOptions(None, None, extra_args=extra_args), mode=mode, max_concurrency=max_concurrency)


def _result(output_dir: Path) -> DciRunResult:
    return DciRunResult(output_dir=output_dir, final_text="answer", events=(RunEvent("r", 1, "run.completed", {"status": "completed"}),), status="completed")


def _verdict(config: JudgeConfig, *, correct: bool = True) -> dict[str, object]:
    return {
        **config.public_dict(),
        "judged_at": "2026-07-14T00:00:00+00:00",
        "attempts": 1,
        "judge_request_fingerprint": "replaced-by-evaluator",
        "is_correct": correct,
        "normalized_prediction": "answer",
        "reason": "fixture",
        "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
        "cost_estimate_usd": {
            "input_cost": 0.0,
            "cached_input_cost": 0.0,
            "output_cost": 0.0,
            "total_cost": 0.0,
        },
    }
