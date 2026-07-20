from __future__ import annotations

import asyncio
import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401

import scripts.bcplus_eval.run_bcplus_eval as source_batch
from dci.benchmark.judge import (
    JudgeConfig as SourceJudgeConfig,
    judge_public_identity as source_judge_public_identity,
)

from asterion.dci.analysis import (
    aggregate_results,
    compute_run_batch_timing,
    extract_agent_usage_metrics,
    extract_tool_metrics,
    gather_query_metrics,
    seconds_between,
)
from asterion.dci.benchmark import (
    BenchmarkRequest,
    DciBenchmarkError,
    _Directory,
    _corpus_content_identity as _real_corpus_content_identity,
    _fingerprint,
    _next_generation,
    _prepare,
    _run_pi_async as _real_run_pi_async,
    _utc_now,
    _validate_config_document,
    run_benchmark_async,
)
from asterion.dci.artifacts import DciConversationFeatures
from asterion.dci.config import (
    ConfigLayers,
    DciRuntimeOptions,
    resolve_asterion_runtime,
    resolve_dci_paths,
)
from asterion.dci.effective_config import AsterionEffectiveConfig
from asterion.dci.context_extension import resolve_context_extension
from asterion.dci.context_profiles import resolve_context_profile
from asterion.dci.judge import JudgeConfig, judge_public_identity
from asterion.dci.evaluation import evaluate_run_directory_async as _real_evaluate
from asterion.dci.pi_rpc import _pi_child_environment, expand_extra_args
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


def _emit_measured_failure_events(on_event) -> None:
    on_event({"type": "agent_start"})
    on_event({
        "type": "tool_execution_start", "toolCallId": "tool-1", "toolName": "read",
    })
    time.sleep(0.002)
    on_event({
        "type": "tool_execution_end", "toolCallId": "tool-1", "toolName": "read",
        "isError": True,
    })
    on_event({
        "type": "message_end",
        "message": {
            "role": "assistant",
            "usage": {"input": 7, "output": 3, "totalTokens": 10},
        },
    })


def _refingerprint_config(config: dict[str, object]) -> None:
    config["run_fingerprint"] = _fingerprint(
        {
            key: item
            for key, item in config.items()
            if key
            not in {
                "judge",
                "judge_configuration_fingerprint",
                "run_fingerprint",
                "batch_fingerprint",
            }
        }
    )
    config["batch_fingerprint"] = _fingerprint(
        {key: item for key, item in config.items() if key != "batch_fingerprint"}
    )


class _MeasuredFailingFixtureClient(_FixtureClient):
    def prompt_and_wait(self, _message: str, *, on_event, **_kwargs: object) -> str:
        _emit_measured_failure_events(on_event)
        raise RuntimeError("measured fixture failure")


class _MeasuredCancellingFixtureClient(_FixtureClient):
    entered = threading.Event()

    def prompt_and_wait(self, _message: str, *, on_event, cancel_event, **_kwargs: object) -> str:
        _emit_measured_failure_events(on_event)
        self.entered.set()
        while not cancel_event.is_set():
            time.sleep(0.001)
        raise RuntimeError("cancelled fixture")


async def _recorded_fixture_run(
    _paths: object, native_request: object, **kwargs: object
) -> DciRunResult:
    lock = getattr(_recorded_fixture_run, "lock", None)
    if lock is None or getattr(lock, "_loop", None) not in {None, asyncio.get_running_loop()}:
        lock = asyncio.Lock()
        _recorded_fixture_run.lock = lock
    async with lock:
        with patch("asterion.dci.run.PiRpcClient", _FixtureClient):
            return await _real_run_pi_async(
                resolve_dci_paths(Path(native_request.cwd)), native_request, **kwargs
            )


async def _recorded_fixture_evaluate(*args: object, **kwargs: object) -> dict[str, object]:
    config = kwargs["judge_config"]
    with patch(
        "asterion.dci.evaluation.judge_answer_sync", return_value=_verdict(config)
    ):
        return await _real_evaluate(*args, **kwargs)


class AsterionDciBatchTests(unittest.IsolatedAsyncioTestCase):
    def test_source_batch_full_selection_requires_explicit_invocation_authority(self) -> None:
        base = SimpleNamespace(
            limit=None,
            output_root=Path("unused"),
        )
        with self.assertRaisesRegex(ValueError, "coordinator-issued AF-340 authorization"):
            source_batch.require_execution_authorization(base, total_rows=50)

        bounded = SimpleNamespace(**{**vars(base), "limit": 1})
        self.assertFalse(
            source_batch.require_execution_authorization(bounded, total_rows=50)
        )
        calls = []
        self.assertTrue(
            source_batch.require_execution_authorization(
                base,
                total_rows=50,
                full_execution_authorizer=lambda args, count: calls.append(
                    (args, count)
                ),
            )
        )
        self.assertEqual(calls, [(base, 50)])

    def test_source_batch_reuse_requires_complete_safe_judge_identity(self) -> None:
        config = SourceJudgeConfig(api_key="credential-one")
        persisted = {**source_judge_public_identity(config), "is_correct": True}

        self.assertTrue(source_batch.judge_result_succeeded(persisted, config))
        for changed in (
            replace(config, responses_store=True),
            replace(config, output_price_per_1m=3.0),
            replace(config, api_key_env="OTHER_JUDGE_KEY"),
        ):
            with self.subTest(changed=changed):
                self.assertFalse(
                    source_batch.judge_result_succeeded(persisted, changed)
                )
        changed_prompt = {
            **source_judge_public_identity(config),
            "prompt_contract_sha256": "f" * 64,
        }
        with patch.object(
            source_batch,
            "judge_public_identity",
            return_value=changed_prompt,
            create=True,
        ):
            self.assertFalse(source_batch.judge_result_succeeded(persisted, config))
        self.assertTrue(
            source_batch.judge_result_succeeded(
                persisted, replace(config, api_key="credential-two")
            )
        )
        with patch.object(
            source_batch,
            "judge_answer_sync",
            return_value={"is_correct": True},
        ):
            produced = asyncio.run(source_batch.judge_answer_async(config=config))
        for key, value in source_judge_public_identity(config).items():
            self.assertEqual(produced[key], value)

    def test_asterion_batch_identity_includes_complete_safe_judge_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            request = _request(root)
            _rows, _output, config, _items, _snapshots = _prepare(request)
            identity = judge_public_identity(request.judge_config)

            self.assertEqual(config["judge"], identity)
            self.assertEqual(
                config["judge_configuration_fingerprint"],
                hashlib.sha256(
                    json.dumps(
                        identity,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                        allow_nan=False,
                    ).encode("utf-8")
                ).hexdigest(),
            )

            credential_only = replace(
                request,
                judge_config=replace(
                    request.judge_config, api_key="credential-only-change"
                ),
            )
            _rows, _output, unchanged, _items, _snapshots = _prepare(credential_only)
            self.assertEqual(
                config["judge_configuration_fingerprint"],
                unchanged["judge_configuration_fingerprint"],
            )

    def test_af240_task3_inventory_rows_have_executable_evidence(self) -> None:
        inventory = json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "assets/dci/batch-parity.json"
            ).read_text(encoding="utf-8")
        )
        rows = [
            row
            for row in inventory["rows"]
            if row.get("target_task") == "AF-240 Task 3"
        ]
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(row=row["id"]):
                self.assertEqual(row["implementation_status"], "implemented")
                self.assertTrue(row["current_asterion_owner"])
                self.assertTrue(row["current_symbol"])
                self.assertEqual(len(row["current_verification_tests"]), 1)

    async def test_failed_post_result_state_mutation_fails_analysis_closed(self) -> None:
        from asterion.dci import benchmark as benchmark_module

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            publish = benchmark_module._publish_aggregates

            def mutate_then_publish(*args: object, **kwargs: object) -> None:
                result = json.loads(
                    (request.output_root / "q-0" / "result.json").read_text()
                )
                native = request.output_root / "q-0" / result["native_generation"]
                state_path = native / "state.json"
                state = json.loads(state_path.read_text())
                state["started_at"] = "2000-01-01T00:00:00+00:00"
                state_path.write_text(json.dumps(state))
                publish(*args, **kwargs)

            with (
                patch("asterion.dci.run.PiRpcClient", _MeasuredFailingFixtureClient),
                patch(
                    "asterion.dci.benchmark._publish_aggregates",
                    side_effect=mutate_then_publish,
                ),
                self.assertRaisesRegex(DciBenchmarkError, "analysis evidence is invalid"),
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))

    async def test_terminal_fingerprint_missing_and_mismatch_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                request = _request(root)
                with patch("asterion.dci.run.PiRpcClient", _MeasuredFailingFixtureClient):
                    await run_benchmark_async(request, paths=resolve_dci_paths(root))
                result_path = request.output_root / "q-0" / "result.json"
                result = json.loads(result_path.read_text())
                result.pop("native_evidence_fingerprint")
                result_path.write_text(json.dumps(result))
                with (
                    patch("asterion.dci.benchmark._run_pi_async") as run,
                    self.assertRaisesRegex(DciBenchmarkError, "terminal result is invalid"),
                ):
                    await run_benchmark_async(request, paths=resolve_dci_paths(root))
                run.assert_not_called()

        from asterion.dci import benchmark as benchmark_module

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            request = _request(root)
            publish = benchmark_module._publish_aggregates

            def forge_then_publish(*args: object, **kwargs: object) -> None:
                results = args[1]
                for result in results.values():
                    result["native_evidence_fingerprint"] = "0" * 64
                publish(*args, **kwargs)

            with (
                patch("asterion.dci.run.PiRpcClient", _MeasuredFailingFixtureClient),
                patch(
                    "asterion.dci.benchmark._publish_aggregates",
                    side_effect=forge_then_publish,
                ),
                self.assertRaisesRegex(DciBenchmarkError, "analysis evidence is invalid"),
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))

    async def test_cancelled_post_result_message_mutation_fails_analysis_closed(self) -> None:
        from asterion.dci import benchmark as benchmark_module

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            request = _request(root)
            publish = benchmark_module._publish_aggregates
            _MeasuredCancellingFixtureClient.entered.clear()

            def mutate_then_publish(*args: object, **kwargs: object) -> None:
                result = json.loads(
                    (request.output_root / "q-0" / "result.json").read_text()
                )
                native = request.output_root / "q-0" / result["native_generation"]
                state_path = native / "state.json"
                state = json.loads(state_path.read_text())
                state["messages"][0]["message"]["usage"]["input"] = 999999
                state_path.write_text(json.dumps(state))
                publish(*args, **kwargs)

            with (
                patch("asterion.dci.run.PiRpcClient", _MeasuredCancellingFixtureClient),
                patch(
                    "asterion.dci.benchmark._publish_aggregates",
                    side_effect=mutate_then_publish,
                ),
            ):
                task = asyncio.create_task(
                    run_benchmark_async(request, paths=resolve_dci_paths(root))
                )
                await asyncio.to_thread(_MeasuredCancellingFixtureClient.entered.wait)
                task.cancel()
                with self.assertRaisesRegex(DciBenchmarkError, "analysis evidence is invalid"):
                    await task

    async def test_query_rename_and_replacement_fails_analysis_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root, mode="ir", ir=True)

            class RebindingClient(_FixtureClient):
                def prompt_and_wait(self, message: str, *, on_event, **kwargs: object) -> str:
                    query = request.output_root / "q-0"
                    query.rename(request.output_root / "detached-query")
                    query.mkdir(mode=0o700)
                    (query / "result.json").write_text("{}")
                    return super().prompt_and_wait(message, on_event=on_event, **kwargs)

            with (
                patch("asterion.dci.run.PiRpcClient", RebindingClient),
                self.assertRaisesRegex(DciBenchmarkError, "analysis evidence is invalid"),
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))

    async def test_post_result_native_mutation_fails_analysis_closed(self) -> None:
        from asterion.dci import benchmark as benchmark_module

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root, mode="ir", ir=True)
            publish = benchmark_module._publish_aggregates
            mutated = False

            def mutate_then_publish(*args: object, **kwargs: object) -> None:
                nonlocal mutated
                if not mutated:
                    result = json.loads(
                        (request.output_root / "q-0" / "result.json").read_text()
                    )
                    state_path = (
                        request.output_root / "q-0" / result["native_generation"] / "state.json"
                    )
                    state = json.loads(state_path.read_text())
                    state["started_at"] = "2026-07-14T00:00:00+00:00"
                    state_path.write_text(json.dumps(state))
                    mutated = True
                publish(*args, **kwargs)

            with (
                patch("asterion.dci.run.PiRpcClient", _FixtureClient),
                patch(
                    "asterion.dci.benchmark._publish_aggregates",
                    side_effect=mutate_then_publish,
                ),
                self.assertRaisesRegex(DciBenchmarkError, "result evidence is invalid"),
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))

    async def test_native_generation_rename_replacement_fails_analysis_closed(self) -> None:
        from asterion.dci import benchmark as benchmark_module

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root, mode="ir", ir=True)
            publish = benchmark_module._publish_aggregates
            rebound = False

            def rebind_then_publish(*args: object, **kwargs: object) -> None:
                nonlocal rebound
                if not rebound:
                    result = json.loads(
                        (request.output_root / "q-0" / "result.json").read_text()
                    )
                    native = request.output_root / "q-0" / result["native_generation"]
                    native.rename(request.output_root / "q-0" / "detached-native")
                    native.mkdir(mode=0o700)
                    rebound = True
                publish(*args, **kwargs)

            with (
                patch("asterion.dci.run.PiRpcClient", _FixtureClient),
                patch(
                    "asterion.dci.benchmark._publish_aggregates",
                    side_effect=rebind_then_publish,
                ),
                self.assertRaisesRegex(DciBenchmarkError, "analysis evidence is invalid"),
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))

    async def test_failed_native_metrics_are_preserved_in_analysis(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            with patch("asterion.dci.run.PiRpcClient", _MeasuredFailingFixtureClient):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            row = json.loads((request.output_root / "analysis.jsonl").read_text())
            self.assertEqual(row["run_status"], "failed")
            self.assertEqual(row["agent_total_tokens"], 10.0)
            self.assertEqual(row["tool_call_count"], 1.0)
            self.assertEqual(row["tool_error_count"], 1.0)
            self.assertGreater(row["tool_time_seconds"], 0.0)

    async def test_cancelled_measured_and_not_started_rows_remain_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root, rows=2, max_concurrency=1)
            _MeasuredCancellingFixtureClient.entered.clear()
            with patch("asterion.dci.run.PiRpcClient", _MeasuredCancellingFixtureClient):
                task = asyncio.create_task(
                    run_benchmark_async(request, paths=resolve_dci_paths(root))
                )
                await asyncio.to_thread(_MeasuredCancellingFixtureClient.entered.wait)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task
            rows = [
                json.loads(line)
                for line in (request.output_root / "analysis.jsonl").read_text().splitlines()
            ]
            self.assertEqual(rows[0]["agent_total_tokens"], 10.0)
            self.assertEqual(rows[0]["tool_call_count"], 1.0)
            self.assertIsNone(rows[1]["agent_total_tokens"])
            self.assertIsNone(rows[1]["tool_call_count"])
            self.assertIsNone(rows[1]["wall_time_seconds"])

    async def test_coordinator_names_are_rejected_before_output_mutation(self) -> None:
        for query_id in (
            ".inputs",
            "．INPUTS",
            "batch-state.json",
            "BATCH-STATE.JSON",
            ".asterion-dci-batch.lock",
        ):
            with self.subTest(query_id=query_id), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory).resolve()
                request = _request(root)
                request.dataset.write_text(
                    json.dumps(
                        {"query_id": query_id, "query": "q", "answer": "gold"}
                    )
                    + "\n"
                )
                with (
                    patch("asterion.dci.run.PiRpcClient") as client,
                    self.assertRaisesRegex(DciBenchmarkError, "dataset is invalid"),
                ):
                    await run_benchmark_async(request, paths=resolve_dci_paths(root))
                client.assert_not_called()
                self.assertFalse(request.output_root.exists())

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
                return await _recorded_fixture_run(
                    _paths, native_request, output_dir=output_dir, **_kwargs
                )

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
            ):
                await run_benchmark_async(request, paths=Mock())
            self.assertTrue((moved / "summary.json").is_file())
            self.assertTrue(tuple(moved.glob("q-0/**/provider-marker")))
            self.assertFalse(tuple(request.output_root.glob("q-0/**/provider-marker")))

    async def test_query_rebinding_fails_analysis_closed_on_locked_query_inode(self) -> None:
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
                return await _recorded_fixture_run(
                    _paths, _native_request, output_dir=output_dir, **kwargs
                )

            with (
                patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native),
                patch(
                    "asterion.dci.benchmark.evaluate_run_directory_async",
                    side_effect=_recorded_fixture_evaluate,
                ),
                self.assertRaisesRegex(DciBenchmarkError, "analysis evidence is invalid"),
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
            root = Path(temporary_directory).resolve()
            request = _request(root)
            _MeasuredCancellingFixtureClient.entered.clear()
            with patch("asterion.dci.run.PiRpcClient", _MeasuredCancellingFixtureClient):
                task = asyncio.create_task(
                    run_benchmark_async(request, paths=resolve_dci_paths(root))
                )
                await asyncio.to_thread(_MeasuredCancellingFixtureClient.entered.wait)
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
                return await _recorded_fixture_run(
                    _paths, _native_request, output_dir=output_dir, **_kwargs
                )

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=complete), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
            ):
                result = await run_benchmark_async(request, paths=resolve_dci_paths(root))
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
                return await _recorded_fixture_run(
                    _paths, _native_request, output_dir=output_dir, **_kwargs
                )

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
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
                return await _recorded_fixture_run(_paths, native_request, **_kwargs)

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
            ):
                await run_benchmark_async(request, paths=Mock())

    async def test_config_and_item_self_fingerprint_forgery_fails_before_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            request = _request(Path(temporary_directory))
            with patch("asterion.dci.benchmark._run_pi_async", side_effect=_recorded_fixture_run), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
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
                side_effect=_recorded_fixture_evaluate,
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

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_eval_result_json(self) -> None:
        await self.test_exact_result_is_reused_without_native_or_judge_work()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_launcher_stderr_txt(self) -> None:
        await self._assert_direct_transport_log_replacement()

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_durable_output_launcher_stdout_txt(self) -> None:
        await self._assert_direct_transport_log_replacement()

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

    async def test_scripts_bcplus_eval_run_bcplus_eval_py_function_build_run_command(self) -> None:
        await self._assert_native_request_replaces_source_subprocess_command()

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_build_subprocess_env(self) -> None:
        with patch.dict(os.environ, {"NODE_OPTIONS": "--trace-warnings"}, clear=True):
            environment = _pi_child_environment(
                agent_dir=Path("/private/fixture-agent"),
                node_bin="/private/fixture-node",
                node_max_old_space_size_mb=4096,
            )
        self.assertEqual(
            environment["NODE_OPTIONS"],
            "--trace-warnings --max-old-space-size=4096",
        )
        self.assertEqual(environment["PI_CODING_AGENT_DIR"], "/private/fixture-agent")
        self.assertEqual(environment["PATH"].split(os.pathsep)[0], "/private")

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_compute_run_batch_timing(self) -> None:
        self.assertEqual(
            compute_run_batch_timing(
                [
                    {
                        "agent_started_at": "2026-07-14T01:00:02+00:00",
                        "agent_finished_at": "2026-07-14T01:00:05+00:00",
                    },
                    {
                        "agent_started_at": "2026-07-14T01:00:00+00:00",
                        "agent_finished_at": "2026-07-14T01:00:09+00:00",
                    },
                ]
            ),
            {
                "started_at": "2026-07-14T01:00:00+00:00",
                "finished_at": "2026-07-14T01:00:09+00:00",
                "elapsed_wall_clock_seconds": 9.0,
            },
        )

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_expand_extra_args(self) -> None:
        self.assertEqual(
            expand_extra_args(("--thinking high", "--flag='two words'")),
            ["--thinking", "high", "--flag=two words"],
        )

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_extract_agent_usage_metrics(self) -> None:
        state = {
            "messages": [
                {
                    "event": "message_end",
                    "message": {
                        "role": "assistant",
                        "usage": {"input": 7, "output": 3, "totalTokens": 10},
                    },
                }
            ]
        }
        self.assertEqual(extract_agent_usage_metrics(state)["total_tokens"], 10.0)

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_extract_tool_metrics(self) -> None:
        state = {
            "tool_calls": [
                {
                    "event": "tool_execution_start",
                    "toolCallId": "t1",
                    "toolName": "read",
                    "recorded_at": "2026-07-14T01:00:00+00:00",
                },
                {
                    "event": "tool_execution_end",
                    "toolCallId": "t1",
                    "toolName": "read",
                    "recorded_at": "2026-07-14T01:00:02+00:00",
                    "isError": False,
                },
            ]
        }
        self.assertEqual(extract_tool_metrics(state)["duration_seconds"], 2.0)

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_gather_query_metrics(self) -> None:
        metrics = gather_query_metrics(
            row={"query_id": "q", "query": "question", "answer": "answer"},
            state={
                "status": "completed",
                "started_at": "2026-07-14T01:00:00+00:00",
                "finished_at": "2026-07-14T01:00:03+00:00",
                "messages": [],
                "tool_calls": [],
            },
            latest_model_context={"request_count": 2},
            final_text=" answer ",
        )
        self.assertEqual(metrics["final_text"], "answer")
        self.assertEqual(metrics["wall_time_seconds"], 3.0)
        self.assertEqual(metrics["request_count"], 2)

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_parse_args(self) -> None:
        from asterion.dci.cli import _parser

        arguments = _parser().parse_args(
            [
                "benchmark",
                "--dataset",
                "fixture.jsonl",
                "--output-root",
                "out",
                "--max-concurrency",
                "3",
            ]
        )
        self.assertEqual(arguments.command, "benchmark")
        self.assertEqual(arguments.dataset, Path("fixture.jsonl"))
        self.assertEqual(arguments.max_concurrency, 3)

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_effective_config_for_batch(self) -> None:
        invocation = {
            "runtime": "pi",
            "provider": "fixture-provider",
            "model": "fixture-model",
            "tools": "read,bash",
            "max_turns": 7,
            "timeout_seconds": 12,
            "thinking_level": "high",
            "context_profile": "level3",
        }
        runtime = resolve_asterion_runtime(invocation, ConfigLayers({}, {}))
        projection = AsterionEffectiveConfig(runtime).to_public_dict()
        self.assertEqual(projection["runtime"], "pi")
        self.assertEqual(projection["agent"]["provider"], "fixture-provider")
        self.assertEqual(projection["agent"]["model"], "fixture-model")

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_resolve_runtime_args(self) -> None:
        arguments = SimpleNamespace(
            runtime=None,
            provider=None,
            model=None,
            tools="read,bash",
            max_turns=7,
            rpc_timeout_seconds=None,
            pi_thinking_level=None,
            runtime_context_level=None,
        )
        resolved = source_batch.resolve_runtime_args(
            arguments,
            source_batch.ConfigLayers(
                {"DCI_PROVIDER": "fixture-provider"}, {"DCI_MODEL": "fixture-model"}
            ),
        )
        asterion = resolve_asterion_runtime(
            {"tools": "read,bash", "max_turns": 7},
            ConfigLayers(
                {"DCI_PROVIDER": "fixture-provider"}, {"DCI_MODEL": "fixture-model"}
            ),
        )
        self.assertEqual((resolved.runtime, resolved.provider, resolved.model), (asterion.runtime, asterion.provider, asterion.model))

    def test_scripts_bcplus_eval_run_bcplus_eval_py_cli_flag_runtime(self) -> None:
        from asterion.dci.cli import _parser

        source = SimpleNamespace(
            runtime="pi",
            provider=None,
            model=None,
            tools="read,bash",
            max_turns=7,
            rpc_timeout_seconds=None,
            pi_thinking_level=None,
            runtime_context_level=None,
        )
        resolved = source_batch.resolve_runtime_args(
            source, source_batch.ConfigLayers({}, {})
        )
        target = _parser().parse_args(["benchmark", "--runtime", "pi"])
        self.assertEqual(resolved.runtime, target.runtime)

    def test_scripts_bcplus_eval_run_bcplus_eval_py_cli_flag_rpc_timeout_seconds(self) -> None:
        from asterion.dci.cli import _parser

        target = _parser().parse_args(
            ["benchmark", "--rpc-timeout-seconds", "12"]
        )
        self.assertEqual(target.rpc_timeout_seconds, 12)

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_parse_iso8601(self) -> None:
        self.assertEqual(
            seconds_between("2026-07-14T01:00:00Z", "2026-07-14T01:00:01Z"),
            1.0,
        )
        self.assertIsNone(seconds_between("not-a-date", "2026-07-14T01:00:01Z"))

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_read_json_if_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            directory = _Directory(os.open(root, os.O_RDONLY))
            try:
                self.assertIsNone(directory.read_optional_json("result.json"))
                directory.write_json("result.json", {"status": "completed"})
                self.assertEqual(
                    directory.read_optional_json("result.json"),
                    {"status": "completed"},
                )
            finally:
                directory.close()

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_read_text_if_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            directory = _Directory(os.open(root, os.O_RDONLY))
            try:
                self.assertIsNone(directory.read_optional_text("final.txt"))
                directory.write_text("final.txt", "answer")
                self.assertEqual(directory.read_optional_text("final.txt"), "answer")
            finally:
                directory.close()

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_resolve_repo_relative_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            rows, output_root, _config, _items, _snapshots = _prepare(request)
        self.assertEqual(output_root, request.output_root)
        self.assertEqual(rows[0].query_id, "q-0")

    def test_af340_bound_paper_profiles_open_only_exact_limit_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            profiles = (
                "beir.arguana",
                "beir.scifact",
                "bright.biology",
                "bright.earth-science",
                "bright.economics",
                "bright.robotics",
                "bcplus.level3",
                "bcplus.openai",
                "qa.2wikimultihopqa",
                "qa.hotpotqa",
                "qa.musique",
                "qa.nq",
                "qa.triviaqa",
            )
            for profile in profiles:
                for limit in (None, 2):
                    with self.subTest(profile=profile, limit=limit), patch(
                        "asterion.dci.benchmark._read_input_snapshot"
                    ) as read_input, patch(
                        "asterion.dci.benchmark._run_pi_async"
                    ) as run:
                        with self.assertRaisesRegex(
                            DciBenchmarkError, "not executable in AF-320"
                        ):
                            asyncio.run(
                                run_benchmark_async(
                                    replace(request, profile=profile, limit=limit),
                                    paths=Mock(),
                                )
                            )
                        read_input.assert_not_called()
                        run.assert_not_called()

                with self.subTest(profile=profile, limit=1), patch(
                    "asterion.dci.benchmark._read_input_snapshot",
                    return_value=b"not-json\n",
                ) as read_input, patch(
                    "asterion.dci.benchmark._run_pi_async"
                ) as run:
                    with self.assertRaisesRegex(
                        DciBenchmarkError, "dataset is invalid"
                    ):
                        asyncio.run(
                            run_benchmark_async(
                                replace(request, profile=profile, limit=1),
                                paths=Mock(),
                            )
                        )
                    read_input.assert_called_once()
                    run.assert_not_called()

    def test_af340_bcplus_limit_one_runs_one_mocked_agent_and_judge_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = replace(
                _request(root),
                profile="bcplus.openai",
                limit=1,
                resume_policy="fresh",
            )
            paper_scope = "browsecomp-plus.main.all830"
            with patch(
                "asterion.dci.benchmark._run_pi_async"
            ) as mismatched_run, self.assertRaisesRegex(
                DciBenchmarkError, "paper scope does not match its profile"
            ):
                asyncio.run(run_benchmark_async(request, paths=Mock()))
            mismatched_run.assert_not_called()

            with patch(
                "asterion.dci.benchmark._paper_scope_for_rows",
                return_value=paper_scope,
            ), patch(
                "asterion.dci.benchmark._run_pi_async",
                side_effect=_recorded_fixture_run,
            ) as run, patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
            ) as judge:
                result = asyncio.run(run_benchmark_async(request, paths=Mock()))

            self.assertEqual(result.counts["total"], 1)
            run.assert_called_once()
            judge.assert_called_once()
            config = json.loads((result.output_root / "config.json").read_text())
            self.assertEqual(
                config["selection"],
                {
                    "schema": "asterion.dci.selection/v1",
                    "execution_class": "paper-bounded",
                    "id": "limit-1",
                    "paper_scope": paper_scope,
                    "selected_rows": 1,
                    "full_dataset": False,
                    "comparable": False,
                    "authorization_profile": None,
                },
            )
            _validate_config_document(
                config, expected_execution_class="paper-bounded"
            )
            for claim, value in (
                ("full_dataset", True),
                ("comparable", True),
                ("selected_rows", True),
                ("paper_scope", "qa.nq.main.random50"),
            ):
                with self.subTest(forged_claim=claim):
                    forged = json.loads(json.dumps(config))
                    forged["selection"][claim] = value
                    _refingerprint_config(forged)
                    with self.assertRaisesRegex(
                        DciBenchmarkError, "configuration evidence is invalid"
                    ):
                        _validate_config_document(
                            forged, expected_execution_class="paper-bounded"
                        )

            forged = json.loads(json.dumps(config))
            forged["profile"] = "qa.bamboogle"
            _refingerprint_config(forged)
            with self.assertRaisesRegex(
                DciBenchmarkError, "configuration evidence is invalid"
            ):
                _validate_config_document(
                    forged, expected_execution_class="paper-bounded"
                )

            for forged_selection in (
                None,
                {
                    "schema": "asterion.dci.selection/v1",
                    "execution_class": "non-paper",
                    "id": "request",
                    "paper_scope": None,
                    "selected_rows": 1,
                    "full_dataset": False,
                    "comparable": True,
                    "authorization_profile": None,
                },
                {
                    "schema": "asterion.dci.selection/v1",
                    "execution_class": "paper-full-authorized",
                    "id": "paper-full",
                    "paper_scope": paper_scope,
                    "selected_rows": 830,
                    "full_dataset": True,
                    "comparable": False,
                    "authorization_profile": "current-default/pi",
                },
            ):
                with self.subTest(cross_class=forged_selection):
                    forged = json.loads(json.dumps(config))
                    if forged_selection is None:
                        forged.pop("selection")
                    else:
                        forged["selection"] = forged_selection
                    _refingerprint_config(forged)
                    with self.assertRaisesRegex(
                        DciBenchmarkError, "configuration evidence is invalid"
                    ):
                        _validate_config_document(
                            forged, expected_execution_class="paper-bounded"
                        )

            for limit in (None, 2):
                with self.subTest(limit=limit), patch(
                    "asterion.dci.benchmark._run_pi_async"
                ) as blocked_run, patch(
                    "asterion.dci.benchmark.evaluate_run_directory_async"
                ) as blocked_judge, self.assertRaisesRegex(
                    DciBenchmarkError, "not executable in AF-320"
                ):
                    asyncio.run(
                        run_benchmark_async(
                            replace(
                                request,
                                limit=limit,
                                output_root=root / f"blocked-{limit}",
                            ),
                            paths=Mock(),
                        )
                    )
                blocked_run.assert_not_called()
                blocked_judge.assert_not_called()

            for invalid_limit in (0, True):
                with self.subTest(invalid_limit=invalid_limit), patch(
                    "asterion.dci.benchmark._read_input_snapshot"
                ) as read_input, patch(
                    "asterion.dci.benchmark._run_pi_async"
                ) as blocked_run, self.assertRaisesRegex(
                    DciBenchmarkError, "limit is invalid"
                ):
                    asyncio.run(
                        run_benchmark_async(
                            replace(
                                request,
                                limit=invalid_limit,
                                output_root=root / f"blocked-{invalid_limit}",
                            ),
                            paths=Mock(),
                        )
                    )
                read_input.assert_not_called()
                blocked_run.assert_not_called()

    def test_af340_exact_selected_ids_are_verified_before_limit_one_slice(self) -> None:
        from asterion.dci.paper_benchmarks import published_scope_selected_ids

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            selected = published_scope_selected_ids("qa.nq.main.random50")
            dataset = root / "nq-selected.jsonl"
            dataset.write_text(
                "\n".join(
                    json.dumps(
                        {"query_id": query_id, "query": "question", "answer": "gold"}
                    )
                    for query_id in selected
                )
                + "\n"
            )
            request = replace(
                _request(root),
                dataset=dataset,
                profile="qa.nq",
                limit=1,
                resume_policy="fresh",
            )
            with patch(
                "asterion.dci.benchmark._run_pi_async",
                side_effect=_recorded_fixture_run,
            ) as run, patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
            ) as judge:
                result = asyncio.run(run_benchmark_async(request, paths=Mock()))

            run.assert_called_once()
            judge.assert_called_once()
            self.assertEqual(result.counts["total"], 1)
            self.assertTrue((result.output_root / selected[0]).is_dir())

    def test_nonpaper_selection_is_explicit_and_legacy_resume_migrates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            with patch(
                "asterion.dci.benchmark._run_pi_async",
                side_effect=_recorded_fixture_run,
            ), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
            ):
                result = asyncio.run(run_benchmark_async(request, paths=Mock()))

            config_path = result.output_root / "config.json"
            config = json.loads(config_path.read_text())
            self.assertEqual(
                config["selection"],
                {
                    "schema": "asterion.dci.selection/v1",
                    "execution_class": "non-paper",
                    "id": "request",
                    "paper_scope": None,
                    "selected_rows": 1,
                    "full_dataset": False,
                    "comparable": False,
                    "authorization_profile": None,
                },
            )
            legacy = json.loads(json.dumps(config))
            legacy.pop("selection")
            _refingerprint_config(legacy)
            with self.assertRaisesRegex(
                DciBenchmarkError, "configuration evidence is invalid"
            ):
                _validate_config_document(
                    legacy, expected_execution_class="non-paper"
                )
            config_path.write_text(json.dumps(legacy))

            with patch(
                "asterion.dci.benchmark._run_pi_async"
            ) as run, patch(
                "asterion.dci.benchmark.evaluate_run_directory_async"
            ) as judge:
                asyncio.run(run_benchmark_async(request, paths=Mock()))
            run.assert_not_called()
            judge.assert_not_called()
            migrated = json.loads(config_path.read_text())
            self.assertEqual(migrated["selection"], config["selection"])

    def test_af320_copied_paper_dataset_is_digest_gated_without_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            request = replace(
                _request(Path(temporary_directory), mode="ir", ir=True),
                profile=None,
            )
            selected = __import__(
                "asterion.dci.paper_benchmarks",
                fromlist=["published_scope_selected_ids"],
            ).published_scope_selected_ids("beir.arguana.main.random50")
            beir_dataset = request.cwd / "copied-beir.jsonl"
            beir_dataset.write_text(
                "\n".join(
                    json.dumps(
                        {
                            "query_id": query_id,
                            "query": "query",
                            "answer": "",
                            "gold_ids": ["doc.txt"],
                        }
                    )
                    for query_id in selected
                )
                + "\n"
            )
            with patch(
                "asterion.dci.benchmark._run_pi_async"
            ) as run, self.assertRaisesRegex(
                DciBenchmarkError, "requires AF-340 authorization"
            ):
                asyncio.run(
                    run_benchmark_async(
                        replace(request, dataset=beir_dataset, limit=1),
                        paths=Mock(),
                    )
                )
            run.assert_not_called()

            with self.assertRaisesRegex(
                DciBenchmarkError, "requires AF-340 authorization"
            ):
                _prepare(replace(request, dataset=beir_dataset))

            with beir_dataset.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "query_id": "not-paper",
                            "query": "extra",
                            "answer": "",
                            "gold_ids": ["doc.txt"],
                        }
                    )
                    + "\n"
                )
            with self.assertRaisesRegex(
                DciBenchmarkError, "requires AF-340 authorization"
            ):
                _prepare(replace(request, dataset=beir_dataset, limit=50))

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_seconds_between(self) -> None:
        self.assertEqual(
            seconds_between(
                "2026-07-14T01:00:03+00:00",
                "2026-07-14T01:00:01+00:00",
            ),
            0.0,
        )

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_sum_dict_numbers(self) -> None:
        first = {"run_status": "completed", "wall_time_seconds": 2.0}
        second = {"run_status": "completed", "wall_time_seconds": 3.0}
        self.assertEqual(
            aggregate_results([first, second])["totals"]["wall_time_seconds"],
            5.0,
        )

    def test_scripts_bcplus_eval_run_bcplus_eval_py_function_utc_now(self) -> None:
        value = _utc_now()
        parsed = datetime.fromisoformat(value)
        self.assertIsNotNone(parsed.tzinfo)
        self.assertEqual(parsed.utcoffset(), timezone.utc.utcoffset(parsed))

    async def _assert_direct_transport_log_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            with patch("asterion.dci.run.PiRpcClient", _FixtureClient), patch(
                "asterion.dci.evaluation.judge_answer_sync",
                return_value=_verdict(request.judge_config),
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            result = json.loads(
                (request.output_root / "q-0" / "result.json").read_text()
            )
            native = request.output_root / "q-0" / result["native_generation"]
            self.assertTrue((native / "events.jsonl").is_file())
            self.assertTrue((native / "stderr.txt").is_file())
            self.assertFalse((native / "launcher_stdout.txt").exists())
            self.assertFalse((native / "launcher_stderr.txt").exists())

    async def _assert_native_request_replaces_source_subprocess_command(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            runtime = DciRuntimeOptions(
                runtime="pi",
                provider="openai",
                model="fixture-model",
                tools="read,bash",
                runtime_context_level="level3",
                thinking_level="high",
                node_max_old_space_size_mb=4096,
                extra_args=("--custom value",),
            )
            request = replace(_request(root), runtime_options=runtime, max_turns=7)
            captured: list[object] = []

            async def run_native(
                paths: object, native_request: object, **kwargs: object
            ) -> DciRunResult:
                captured.append(native_request)
                return await _recorded_fixture_run(paths, native_request, **kwargs)

            with patch(
                "asterion.dci.benchmark._run_pi_async", side_effect=run_native
            ), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
            ):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            native = captured[0]
            self.assertEqual(native.provider, "openai")
            self.assertEqual(native.model, "fixture-model")
            self.assertEqual(native.tools, "read,bash")
            self.assertEqual(native.runtime_context_level, "level3")
            self.assertEqual(native.thinking_level, "high")
            self.assertEqual(native.node_max_old_space_size_mb, 4096)
            self.assertEqual(native.extra_args, ("--custom value",))
            self.assertEqual(native.max_turns, 7)

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
                return await _recorded_fixture_run(_paths, native_request, **_kwargs)

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
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
            self.assertEqual(
                summary["counts"],
                {
                    "total": 4,
                    "judged": 4,
                    "correct": 4,
                    "incorrect_or_unjudged": 0,
                    "failed_runs": 0,
                },
            )
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
                return await _recorded_fixture_run(_paths, native_request, **_kwargs)

            with patch("asterion.dci.benchmark._run_pi_async", side_effect=run_native), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
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
            with patch("asterion.dci.benchmark._run_pi_async", side_effect=_recorded_fixture_run), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
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
            with patch("asterion.dci.benchmark._run_pi_async", side_effect=_recorded_fixture_run), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
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
            with patch("asterion.dci.benchmark._run_pi_async", side_effect=_recorded_fixture_run), patch(
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
                side_effect=_recorded_fixture_evaluate,
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
                "asterion.dci.benchmark._run_pi_async", side_effect=_recorded_fixture_run
            ) as run, patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
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
    def test_runtime_fingerprint_records_complete_context_policy_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            base = _request(root)
            for name in ("level0", "level1", "level2", "level3", "level4"):
                with self.subTest(profile=name):
                    request = replace(
                        base,
                        output_root=root / name,
                        runtime_options=replace(
                            base.runtime_options,
                            runtime_context_level=name,
                        ),
                    )
                    _rows, _output, config, items, _snapshots = _prepare(request)
                    identity = config["runtime"]["context_policy_identity"]
                    self.assertEqual(
                        identity["profile"],
                        resolve_context_profile(name).identity_payload(),
                    )
                    self.assertEqual(
                        identity["schema"], "dci.context-policy-identity/v1"
                    )
                    self.assertEqual(identity["status"], "effective")
                    with resolve_context_extension() as extension:
                        self.assertEqual(identity["extension_version"], extension.version)
                        self.assertEqual(identity["extension_sha256"], extension.sha256)
                    self.assertEqual(
                        items[0]["identity"]["runtime"]["context_policy_identity"],
                        identity,
                    )

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
            request = BenchmarkRequest(
                dataset=dataset,
                output_root=root / "out",
                cwd=root,
                judge_config=JudgeConfig(base_url="https://judge.example.test/v1"),
                runtime_options=DciRuntimeOptions(runtime="pi"),
            )
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
            with patch("asterion.dci.benchmark._run_pi_async", side_effect=_recorded_fixture_run), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
            ):
                asyncio.run(run_benchmark_async(request, paths=Mock()))
            lines = request.dataset.read_text().splitlines()
            lines[1] = json.dumps({"query_id": "q-1", "query": "changed", "answer": "gold"})
            request.dataset.write_text("\n".join(lines) + "\n")
            with self.assertRaisesRegex(DciBenchmarkError, "configuration is incompatible"):
                asyncio.run(run_benchmark_async(request, paths=Mock()))

    def test_paper_resolution_evidence_flows_to_batch_analysis_and_reuse_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            corpus = root / "corpus"
            corpus.mkdir()
            body = "gold evidence\n"
            document = corpus / "a.txt"
            document.write_text(body)
            manifest = root / "q-0.gold.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "dci.gold-document-manifest/v1",
                        "dataset_id": "fixture.qa",
                        "query_id": "q-0",
                        "documents": [
                            {
                                "id": "a.txt",
                                "path": "a.txt",
                                "sha256": hashlib.sha256(body.encode()).hexdigest(),
                                "evidence_spans": [{"start": 0, "end": 13}],
                            }
                        ],
                    }
                )
                + "\n"
            )
            original_manifest_digest = hashlib.sha256(manifest.read_bytes()).hexdigest()
            registry = root / "resolution-registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema": "dci.gold-document-registry/v1",
                        "dataset_id": "fixture.qa",
                        "manifests": [
                            {
                                "query_id": "q-0",
                                "path": manifest.name,
                                "sha256": original_manifest_digest,
                            }
                        ],
                    }
                )
                + "\n"
            )
            request = replace(
                request,
                corpus=corpus,
                resolution_registry=registry,
                resolution_segment_characters=8,
                conversation_features=DciConversationFeatures(
                    externalize_tool_results=True
                ),
                figures=False,
            )

            async def run_then_replace_inputs(
                *args: object, **kwargs: object
            ) -> DciRunResult:
                result = await _recorded_fixture_run(*args, **kwargs)
                changed_manifest = json.loads(manifest.read_text())
                changed_manifest["documents"][0]["evidence_spans"] = [
                    {"start": 1, "end": 13}
                ]
                manifest.write_text(json.dumps(changed_manifest) + "\n")
                changed_registry = json.loads(registry.read_text())
                changed_registry["manifests"][0]["sha256"] = hashlib.sha256(
                    manifest.read_bytes()
                ).hexdigest()
                registry.write_text(json.dumps(changed_registry) + "\n")
                return result

            with patch(
                "asterion.dci.benchmark._run_pi_async",
                side_effect=run_then_replace_inputs,
            ), patch(
                "asterion.dci.benchmark.evaluate_run_directory_async",
                side_effect=_recorded_fixture_evaluate,
            ), patch(
                "asterion.dci.benchmark._corpus_content_identity",
                wraps=_real_corpus_content_identity,
            ) as corpus_identity:
                asyncio.run(
                    run_benchmark_async(request, paths=resolve_dci_paths(root))
                )
            self.assertEqual(corpus_identity.call_count, 2)

            summary = json.loads((request.output_root / "summary.json").read_text())
            analysis_rows = [
                json.loads(line)
                for line in (request.output_root / "analysis.jsonl").read_text().splitlines()
            ]
            native = next((request.output_root / "q-0").glob("native-generation-*"))
            private = json.loads((native / "trajectory-resolution.json").read_text())
            self.assertEqual(
                private["identity"]["inputs"]["gold_manifest"]["sha256"],
                original_manifest_digest,
            )
            self.assertEqual(summary["resolution"]["coverage"]["any"], 0.0)
            self.assertEqual(analysis_rows[0]["coverage_mean"], 0.0)
            self.assertEqual(
                private["metrics"]["retained_coverage"]["unavailable_reason"],
                "final-context-unavailable",
            )

            # Restore the immutable configured inputs, then prove an unrelated
            # corpus byte invalidates compatible reuse before provider work.
            changed_manifest = json.loads(manifest.read_text())
            changed_manifest["documents"][0]["evidence_spans"] = [
                {"start": 0, "end": 13}
            ]
            manifest.write_text(json.dumps(changed_manifest) + "\n")
            changed_registry = json.loads(registry.read_text())
            changed_registry["manifests"][0]["sha256"] = original_manifest_digest
            registry.write_text(json.dumps(changed_registry) + "\n")
            distractor = corpus / "distractor.txt"
            distractor.write_text("new corpus byte\n")
            with patch("asterion.dci.benchmark._run_pi_async") as run, self.assertRaisesRegex(
                DciBenchmarkError, "configuration"
            ):
                asyncio.run(
                    run_benchmark_async(request, paths=resolve_dci_paths(root))
                )
            run.assert_not_called()
            distractor.unlink()

            changed = replace(request, resolution_segment_characters=16)
            with patch("asterion.dci.benchmark._run_pi_async") as run, self.assertRaisesRegex(
                DciBenchmarkError, "configuration"
            ):
                asyncio.run(
                    run_benchmark_async(changed, paths=resolve_dci_paths(root))
                )
            run.assert_not_called()

    def test_invalid_resolution_manifest_fails_before_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            request = _request(root)
            corpus = root / "corpus"
            corpus.mkdir()
            manifest = root / "manifest.json"
            manifest.write_text("{}\n")
            registry = root / "registry.json"
            registry.write_text(
                json.dumps(
                    {
                        "schema": "dci.gold-document-registry/v1",
                        "dataset_id": "fixture.qa",
                        "manifests": [
                            {
                                "query_id": "q-0",
                                "path": manifest.name,
                                "sha256": hashlib.sha256(
                                    manifest.read_bytes()
                                ).hexdigest(),
                            }
                        ],
                    }
                )
            )
            request = replace(
                request,
                corpus=corpus,
                resolution_registry=registry,
                resolution_segment_characters=8,
                conversation_features=DciConversationFeatures(
                    externalize_tool_results=True
                ),
            )
            with patch("asterion.dci.benchmark._run_pi_async") as run, self.assertRaisesRegex(
                DciBenchmarkError, "resolution manifest is invalid"
            ):
                asyncio.run(
                    run_benchmark_async(request, paths=resolve_dci_paths(root))
                )
            run.assert_not_called()


def _request(root: Path, *, rows: int = 1, max_concurrency: int = 1, mode: str = "qa", ir: bool = False, extra_args: tuple[str, ...] = ()) -> BenchmarkRequest:
    root = root.resolve()
    dataset = root / "dataset.jsonl"
    values = []
    for index in range(rows):
        value: dict[str, object] = {"query_id": f"q-{index}", "query": f"question {index}"}
        value["gold_docs" if ir else "answer"] = [f"doc-{index}"] if ir else "gold"
        values.append(value)
    dataset.write_text("\n".join(json.dumps(value) for value in values) + "\n")
    return BenchmarkRequest(
        dataset=dataset,
        output_root=root / "out",
        cwd=root,
        judge_config=JudgeConfig(base_url="https://judge.example.test/v1"),
        runtime_options=DciRuntimeOptions(runtime="pi", extra_args=extra_args),
        mode=mode,
        max_concurrency=max_concurrency,
    )


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
