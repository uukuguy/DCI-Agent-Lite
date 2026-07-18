from __future__ import annotations

import copy
import contextlib
import asyncio
import hashlib
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401
import pyarrow as pa
import pyarrow.parquet as pq
import dci.benchmark.pi_rpc_runner as source_runner
import dci.benchmark.export_bc_plus_docs as source_bcplus_export
from dci.benchmark.export_bright_docs import export_subset as source_bright_export
import scripts.bcplus_eval.run_bcplus_eval as source_batch
from dci.benchmark.judge import (
    JudgeConfig as SourceJudgeConfig,
    build_judge_request as build_source_judge_request,
    judge_request_fingerprint as source_judge_fingerprint,
    judge_public_identity as source_judge_public_identity,
)
from asterion.dci.benchmark import BenchmarkRequest, run_benchmark
from asterion.dci.config import (
    DciRuntimeOptions,
    resolve_dci_paths,
    resolve_dci_runtime_options,
)
from asterion.dci.evaluation import evaluate_run_directory
from asterion.dci.judge import (
    JudgeConfig as AsterionJudgeConfig,
    build_judge_request as build_asterion_judge_request,
    judge_request_fingerprint as asterion_judge_fingerprint,
    judge_public_identity as asterion_judge_public_identity,
)
from asterion.dci.pi_rpc import build_pi_command as build_asterion_pi_command
from asterion.dci.export import export_bcplus, export_subset as asterion_bright_export
from asterion.dci.run import DciRunError, DciRunRequest, run_pi_research
from tests.asterion_dci_parity_helpers import (
    canonical_batch_semantics,
    canonical_judge_semantics,
    canonical_run_semantics,
)
import tools.verify_asterion_dci_product as product_verifier

from tools.verify_asterion_dci_product import (
    load_product_matrix,
    run_local_evidence,
    validate_product_matrix,
)


ROOT = Path(__file__).parents[1]
REQUIRED_PRODUCT_ROWS = {
    "configuration-and-pi-argv",
    "interactive-run-and-terminal",
    "native-artifacts-and-resume",
    "judge-and-exact-cache",
    "batch-ir-analysis-and-exports",
    "source-and-asterion-examples",
    "installed-wheel-boundary",
    "installed-pi-application",
}
REQUIRED_PROVIDER_CASES = {
    "source-basic",
    "source-runtime-context",
    "asterion-basic",
    "asterion-runtime-context",
    "installed-pi-application",
    "one-row-pi-judge",
    "one-row-exact-reuse",
}
REQUIRED_PRODUCT_OWNERS = {
    "configuration-and-pi-argv": "asterion.dci.config",
    "interactive-run-and-terminal": "asterion.dci.cli",
    "native-artifacts-and-resume": "asterion.dci.artifacts",
    "judge-and-exact-cache": "asterion.dci.evaluation",
    "batch-ir-analysis-and-exports": "asterion.dci.benchmark",
    "source-and-asterion-examples": "asterion.dci.cli",
    "installed-wheel-boundary": "asterion.distribution",
    "installed-pi-application": "asterion.applications.dci_agent_lite",
}
EXPECTED_BEHAVIOR_SELECTORS = {
    "configuration-and-pi-argv": {
        "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_configuration_precedence_and_effective_pi_argv_match",
        "tests.test_check_judge.CheckJudgeTests.test_make_config_target_is_independently_executable",
        "tests.test_config.PiPathConfigTests.test_environment_can_override_all_pi_paths",
        "tests.test_asterion_dci_config.AsterionDciConfigTests.test_runtime_options_merge_shared_env_and_explicit_values",
        "tests.test_asterion_dci_run.AsterionDciRunTests.test_runtime_options_map_to_native_pi_request",
    },
    "interactive-run-and-terminal": {
        "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_completed_native_runs_have_equal_stable_semantics",
        "tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_waits_for_agent_settled",
        "tests.test_asterion_dci_cli.AsterionDciCliTests.test_terminal_maps_operator_controls_without_artifacts",
        "tests.test_asterion_dci_pi_rpc.PiRpcCommandTests.test_terminal_uses_literal_argv_inherited_heap_and_exit_status",
    },
    "native-artifacts-and-resume": {
        "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_failed_and_resumed_lifecycle_is_not_normalized_away",
        "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_run_normalizer_rejects_missing_or_malformed_evidence",
        "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_run_semantics_retain_typed_max_turns",
        "tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_run_recorder_isolates_protocol_attempts_on_resume",
        "tests.test_asterion_dci_artifacts.AsterionDciArtifactTests.test_recorder_writes_original_durable_artifact_set",
        "tests.test_asterion_dci_run.AsterionDciRunTests.test_resume_reuses_failed_directory_and_creates_a_second_protocol_attempt",
    },
    "judge-and-exact-cache": {
        "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_judge_request_and_cache_invalidation_semantics_match",
        "tests.test_judge.JudgeTransportTests.test_judge_request_fingerprint_is_deterministic_and_endpoint_sensitive",
        "tests.test_judge.JudgeResultReuseTests.test_backend_identity_is_part_of_result_reuse",
        "tests.test_asterion_dci_evaluation.AsterionDciEvaluationTests.test_reuses_only_an_exact_judge_request_fingerprint",
    },
    "batch-ir-analysis-and-exports": {
        "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_batch_semantics_keep_counts_ndcg_exports_and_reuse",
        "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_bcplus_and_bright_export_transforms_match",
        "tests.test_climb_tools.Af240InventoryTests.test_af240_inventory_maps_complete_source_surface",
        "tests.test_asterion_dci_batch.AsterionDciBatchTests.test_exact_result_is_reused_without_native_or_judge_work",
        "tests.test_asterion_dci_metrics.AsterionDciMetricTests.test_normalization_matches_source_property_matrix",
        "tests.test_asterion_dci_export.AsterionDciExportTests.test_cli_failures_are_body_free_and_module_has_no_baseline_import",
    },
    "source-and-asterion-examples": {
        "tests.test_asterion_structure.AsterionStructureTests.test_examples_execute_with_pairwise_semantic_parity",
    },
    "installed-wheel-boundary": {
        "tests.test_distribution_boundaries.BuiltDistributionBoundaryTests.test_asterion_is_the_only_buildable_wheel",
        "tests.test_distribution_boundaries.SourceDistributionBoundaryTests.test_asterion_core_never_imports_the_dci_baseline",
    },
    "installed-pi-application": {
        "tests.test_builtin_dci_application.BuiltinDciApplicationTests.test_selected_provider_uses_one_asterion_resource_root",
        "tests.test_asterion_dci_application_executor.AsterionDciApplicationExecutorTests.test_maps_runtime_cwd_and_native_paths_to_one_pi_run",
        "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h003_fresh_installed_product_runs_outside_repository",
    },
}
EXPECTED_BEHAVIOR_SELECTORS["batch-ir-analysis-and-exports"].update(
    row["current_verification_tests"][0]
    for row in json.loads(
        (ROOT / "assets/dci/batch-parity.json").read_text(encoding="utf-8")
    )["rows"]
)


class _SourceFixturePiClient:
    command = ["node", "fixture-pi", "--provider", "fixture-provider"]

    def __init__(self, **_: object) -> None:
        self.calls = 0

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def get_stderr(self) -> str:
        return "fixture provider stderr"

    def prompt_and_wait(self, question: str, *, recorder, **_: object) -> str:
        self.calls += 1
        recorder.record_event(
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
            }
        )
        recorder.record_event({"type": "agent_end"})
        return "answer"


class _SourceFailingPiClient(_SourceFixturePiClient):
    def prompt_and_wait(self, question: str, *, recorder, **_: object) -> str:
        self.calls += 1
        recorder.record_event({"type": "agent_end"})
        raise RuntimeError(f"private provider failure for {question}")


class _AsterionFixturePiClient:
    def __init__(self, **_: object) -> None:
        self.calls = 0

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def get_stderr(self) -> str:
        return "fixture provider stderr"

    def prompt_and_wait(self, question: str, *, on_event, **_: object) -> str:
        self.calls += 1
        on_event(
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
            }
        )
        on_event({"type": "agent_end"})
        return "answer"


class _AsterionFailingPiClient(_AsterionFixturePiClient):
    def prompt_and_wait(self, question: str, *, on_event, **_: object) -> str:
        self.calls += 1
        on_event({"type": "agent_end"})
        raise RuntimeError(f"private provider failure for {question}")


class _AsterionMixedBatchPiClient(_AsterionFixturePiClient):
    calls = 0

    def prompt_and_wait(self, question: str, *, on_event, **kwargs: object) -> str:
        type(self).calls += 1
        if "question 1" in question:
            raise RuntimeError("fixture batch failure")
        for event in (
            {"type": "response", "id": "fixture-1", "success": True},
            {"type": "agent_start"},
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
            },
            {"type": "agent_end"},
        ):
            on_event(event)
        return "answer"


class _SpoofSemanticSelectors:
    def test_af250_h002_completed_native_runs_have_equal_stable_semantics(
        self,
    ) -> None:
        return None


def _resolve_selector(selector: str) -> bool:
    parts = selector.split(".")
    for index in range(len(parts), 0, -1):
        try:
            value: object = importlib.import_module(".".join(parts[:index]))
        except ModuleNotFoundError:
            continue
        try:
            for part in parts[index:]:
                value = getattr(value, part)
        except AttributeError:
            return False
        return callable(value)
    return False


class AsterionDciProductParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = load_product_matrix(ROOT)

    def _validated_rows(self) -> tuple[dict[str, object], ...]:
        return validate_product_matrix(ROOT, self.document)

    def _run_source_fixture(
        self, output: Path, client: type[_SourceFixturePiClient], *, resume: bool = False
    ) -> int:
        argv = [
            "dci-agent-lite",
            "--output-dir",
            str(output),
            "--cwd",
            str(output.parent),
            "--provider",
            "fixture-provider",
            "--model",
            "fixture-model",
            "--tools",
            "read,bash",
            "question",
        ]
        if resume:
            argv[1:1] = ["--resume", str(output)]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(source_runner, "PiRpcClient", client),
            mock.patch.object(
                source_runner,
                "collect_pi_source_provenance",
                return_value={"commit": "fixture", "dirty": False},
            ),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            return source_runner.main()

    def _run_asterion_fixture(
        self,
        root: Path,
        output: Path,
        client: type[_AsterionFixturePiClient],
        *,
        resume: bool = False,
    ) -> str:
        request = DciRunRequest(
            run_id="fixture-run",
            question="question",
            cwd=root,
            provider="fixture-provider",
            model="fixture-model",
            tools="read,bash",
            max_turns=100,
            resume=resume,
        )
        with (
            mock.patch("asterion.dci.run.PiRpcClient", client),
            mock.patch(
                "asterion.dci.artifacts.collect_pi_provenance",
                return_value={"commit": "fixture", "dirty": False},
            ),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            try:
                return run_pi_research(
                    resolve_dci_paths(root), request, output_dir=output
                ).status
            except DciRunError:
                return "failed"

    def _write_source_batch_evidence(
        self, root: Path, *, mode: str, rows: int
    ) -> tuple[Path, int, int]:
        output_root = root / f"source-{mode}"
        corpus = root / "corpus"
        corpus.mkdir(exist_ok=True)
        (corpus / "doc-0").write_text("fixture", encoding="utf-8")
        dataset = root / f"source-{mode}.jsonl"
        dataset.write_text("{}\n", encoding="utf-8")
        argv = [
            "run-batch",
            "--dataset",
            str(dataset),
            "--output-root",
            str(output_root),
            "--corpus-dir",
            str(corpus),
            "--max-concurrency",
            "1",
        ]
        if mode == "ir":
            argv.append("--enable-ir")
        with mock.patch.object(sys, "argv", argv):
            args = source_batch.parse_args()
        config = SourceJudgeConfig(
            base_url="https://judge.example.test/v1", model="fixture-judge"
        )
        source_calls = 0

        async def fake_subprocess(*command: str, **_: object):
            nonlocal source_calls
            source_calls += 1
            destination = Path(command[command.index("--output-dir") + 1])
            client = (
                _SourceFailingPiClient
                if destination.name == "q-1"
                else _SourceFixturePiClient
            )
            returncode = self._run_source_fixture(destination, client)

            class Process:
                async def communicate(self) -> tuple[bytes, bytes]:
                    return b"", b""

            process = Process()
            process.returncode = returncode
            return process

        judge_calls = 0

        async def fake_judge(**kwargs: object) -> dict[str, object]:
            nonlocal judge_calls
            judge_calls += 1
            judge_config = kwargs["config"]
            assert isinstance(judge_config, SourceJudgeConfig)
            return {
                **judge_config.public_dict(),
                "judge_request_fingerprint": source_judge_fingerprint(
                    config=judge_config,
                    question=str(kwargs["question"]),
                    gold_answer=str(kwargs["gold_answer"]),
                    predicted_answer=str(kwargs["predicted_answer"]),
                ),
                "is_correct": "question 1" not in str(kwargs["question"]),
                "attempts": 1,
                "usage": {},
                "cost_estimate_usd": {},
            }

        values = []
        for index in range(rows):
            value: dict[str, object] = {
                "query_id": f"q-{index}",
                "query": f"question {index}",
            }
            value["gold_docs" if mode == "ir" else "answer"] = (
                ["doc-0"] if mode == "ir" else "gold"
            )
            values.append(value)

        async def execute() -> list[dict[str, object]]:
            results = []
            for value in values:
                results.append(
                    await source_batch.run_single_query(
                        args=args,
                        row=value,
                        query_dir=output_root / str(value["query_id"]),
                        judge_config=None if mode == "ir" else config,
                    )
                )
            return results

        with mock.patch(
            "asyncio.create_subprocess_exec", side_effect=fake_subprocess
        ), mock.patch.object(
            source_batch, "judge_answer_async", side_effect=fake_judge
        ):
            results = asyncio.run(execute())
            if rows == 1:
                initial_calls = (source_calls, judge_calls)
                asyncio.run(execute())
                self.assertEqual((source_calls, judge_calls), initial_calls)
        output_root.mkdir(parents=True, exist_ok=True)
        source_batch.write_json(
            output_root / "summary.json", source_batch.aggregate_results(results)
        )
        source_batch.write_jsonl(output_root / "results.jsonl", results)
        return output_root, source_calls, judge_calls

    def _write_asterion_batch_evidence(
        self, root: Path, *, mode: str, rows: int
    ) -> tuple[Path, int, int]:
        dataset = root / f"asterion-{mode}.jsonl"
        values = []
        for index in range(rows):
            value: dict[str, object] = {
                "query_id": f"q-{index}",
                "query": f"question {index}",
            }
            value["gold_docs" if mode == "ir" else "answer"] = (
                ["doc-0"] if mode == "ir" else "gold"
            )
            values.append(value)
        dataset.write_text(
            "".join(json.dumps(value) + "\n" for value in values), encoding="utf-8"
        )
        corpus = root / "corpus"
        corpus.mkdir(exist_ok=True)
        (corpus / "doc-0").write_text("fixture", encoding="utf-8")
        output_root = root / f"asterion-{mode}"
        config = AsterionJudgeConfig(
            base_url="https://judge.example.test/v1", model="fixture-judge"
        )
        request = BenchmarkRequest(
            dataset=dataset,
            output_root=output_root,
            cwd=root,
            judge_config=config,
            runtime_options=DciRuntimeOptions(None, None),
            mode=mode,
            corpus=corpus if mode == "ir" else None,
            analysis=False,
            figures=False,
        )
        judge_calls = 0

        def fake_judge(**kwargs: object) -> dict[str, object]:
            nonlocal judge_calls
            judge_calls += 1
            judge_config = kwargs["config"]
            assert isinstance(judge_config, AsterionJudgeConfig)
            return {
                **judge_config.public_dict(),
                "judge_request_fingerprint": asterion_judge_fingerprint(
                    config=judge_config,
                    question=str(kwargs["question"]),
                    gold_answer=str(kwargs["gold_answer"]),
                    predicted_answer=str(kwargs["predicted_answer"]),
                ),
                "is_correct": True,
                "attempts": 1,
                "judged_at": "2026-07-15T00:00:00Z",
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

        _AsterionMixedBatchPiClient.calls = 0
        with mock.patch(
            "asterion.dci.run.PiRpcClient", _AsterionMixedBatchPiClient
        ), mock.patch(
            "asterion.dci.evaluation.judge_answer_sync", side_effect=fake_judge
        ):
            run_benchmark(request, paths=resolve_dci_paths(root))
            if rows == 1:
                initial_calls = (_AsterionMixedBatchPiClient.calls, judge_calls)
                run_benchmark(request, paths=resolve_dci_paths(root))
                self.assertEqual(
                    (_AsterionMixedBatchPiClient.calls, judge_calls), initial_calls
                )
        return output_root, _AsterionMixedBatchPiClient.calls, judge_calls

    def test_product_matrix_has_no_unsupported_or_unexecutable_row(self) -> None:
        rows = self._validated_rows()
        self.assertEqual({row["id"] for row in rows}, REQUIRED_PRODUCT_ROWS)
        self.assertTrue(all(row["unsupported"] is False for row in rows))
        self.assertTrue(all(row["local_evidence"] for row in rows))

    def test_matrix_binds_the_exact_af240_inventory(self) -> None:
        inventory = self.document["batch_inventory"]
        path = ROOT / inventory["path"]
        self.assertEqual(inventory["path"], "assets/dci/batch-parity.json")
        self.assertEqual(inventory["row_count"], 533)
        self.assertEqual(
            inventory["sha256"], hashlib.sha256(path.read_bytes()).hexdigest()
        )

    def test_matrix_binds_complete_body_free_product_acceptance(self) -> None:
        acceptance = self.document["product_acceptance"]
        path = ROOT / acceptance["path"]
        self.assertEqual(acceptance["path"], "assets/dci/product-acceptance.json")
        self.assertEqual(acceptance["case_count"], 7)
        self.assertEqual(
            acceptance["sha256"], hashlib.sha256(path.read_bytes()).hexdigest()
        )
        self.assertEqual(
            product_verifier.validate_acceptance_reference(ROOT, acceptance), 7
        )

        for field, value, error in (
            ("path", "assets/dci/missing.json", "canonical"),
            ("sha256", "0" * 64, "SHA-256"),
            ("case_count", 6, "case count"),
        ):
            with self.subTest(field=field):
                document = copy.deepcopy(self.document)
                document["product_acceptance"][field] = value
                with self.assertRaisesRegex(ValueError, error):
                    validate_product_matrix(ROOT, document)

    def test_inventory_requires_all_533_resolvable_executable_selectors(self) -> None:
        selectors = product_verifier.validate_batch_inventory(
            ROOT, self.document["batch_inventory"]
        )
        self.assertEqual(len(selectors), 533)
        self.assertEqual(len(set(selectors)), 533)
        rejected = selectors[17]
        with mock.patch.object(
            product_verifier,
            "_resolve_selector",
            side_effect=lambda root, selector: selector != rejected,
        ), mock.patch.object(
            product_verifier, "_resolve_dynamic_selectors", return_value=False
        ):
            with self.assertRaisesRegex(ValueError, "inventory selector"):
                product_verifier.validate_batch_inventory(
                    ROOT, self.document["batch_inventory"]
                )

    def test_exact_twelve_source_asterion_launcher_pairs_are_required(self) -> None:
        pairs = product_verifier.validate_launcher_pairs(ROOT)
        self.assertEqual(len(pairs), 12)
        primary_pairs = tuple(
            pair for pair in pairs if not pair[0].endswith("/run_L3.sh")
        )
        self.assertEqual(len(primary_pairs), 11)
        self.assertTrue(
            all("/run_L3.sh" not in path for pair in primary_pairs for path in pair)
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for source, target in pairs:
                for relative in (source, target):
                    destination = root / relative
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
            (root / pairs[0][1]).unlink()
            with self.assertRaisesRegex(ValueError, "launcher pairs"):
                product_verifier.validate_launcher_pairs(root)

    def test_batch_row_is_exactly_linked_to_all_delegated_inventory_selectors(
        self,
    ) -> None:
        inventory = tuple(
            row["current_verification_tests"][0]
            for row in json.loads(
                (ROOT / "assets/dci/batch-parity.json").read_text(encoding="utf-8")
            )["rows"]
        )
        mutations = []
        missing = copy.deepcopy(self.document)
        missing_evidence = missing["rows"][4]["local_evidence"][0]
        missing_evidence["selectors"].remove(inventory[10])
        missing_evidence["argv"].remove(inventory[10])
        mutations.append(missing)
        substituted = copy.deepcopy(self.document)
        substituted_evidence = substituted["rows"][4]["local_evidence"][0]
        replacement = next(iter(EXPECTED_BEHAVIOR_SELECTORS["configuration-and-pi-argv"]))
        index = substituted_evidence["selectors"].index(inventory[11])
        substituted_evidence["selectors"][index] = replacement
        substituted_evidence["argv"][len(product_verifier.UNITTEST_PREFIX) + index] = replacement
        mutations.append(substituted)
        duplicate = copy.deepcopy(self.document)
        duplicate_evidence = duplicate["rows"][4]["local_evidence"][0]
        duplicate_evidence["selectors"].append(inventory[12])
        duplicate_evidence["argv"].append(inventory[12])
        mutations.append(duplicate)
        for document in mutations:
            with self.subTest(kind=mutations.index(document)):
                with self.assertRaisesRegex(ValueError, "delegated inventory"):
                    validate_product_matrix(ROOT, document)

    def test_delegated_count_requires_the_linked_batch_command_to_pass(self) -> None:
        rows = self._validated_rows()

        def execute(argv: object, **_: object) -> subprocess.CompletedProcess[str]:
            selectors = tuple(argv) if isinstance(argv, tuple) else tuple(argv)
            status = 1 if len(selectors) > 500 else 0
            return subprocess.CompletedProcess(selectors, status)

        with mock.patch("subprocess.run", side_effect=execute):
            result = run_local_evidence(ROOT, rows)
        self.assertEqual(result["bounded_acceptance"], "7/7")
        self.assertEqual(result["delegated_inventory"], "0/533")
        self.assertEqual(result["launcher_pairs"], "0/12")
        self.assertEqual(result["batch_extra_selectors"], "0/6")

    def test_matrix_rejects_unknown_fields_and_duplicate_ids(self) -> None:
        unknown = copy.deepcopy(self.document)
        unknown["extra"] = True
        with self.assertRaisesRegex(ValueError, "unknown matrix fields"):
            validate_product_matrix(ROOT, unknown)
        duplicate = copy.deepcopy(self.document)
        duplicate["rows"].append(copy.deepcopy(duplicate["rows"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate product row"):
            validate_product_matrix(ROOT, duplicate)

    def test_matrix_rejects_unsafe_or_provider_backed_local_argv(self) -> None:
        mutations = (
            ["TOKEN=value", "uv", "run", "python", "-m", "unittest", "x"],
            ["/usr/bin/python3", "tools/verify_asterion_dci_product.py", "--validate-only"],
            ["uv", "run", "python", "-m", "unittest", "x; echo unsafe"],
        )
        for argv in mutations:
            with self.subTest(argv=argv):
                document = copy.deepcopy(self.document)
                document["rows"][0]["local_evidence"][0]["argv"] = argv
                with self.assertRaisesRegex(ValueError, "unsafe|allowlisted"):
                    validate_product_matrix(ROOT, document)
        document = copy.deepcopy(self.document)
        document["rows"][0]["local_evidence"][0]["tier"] = "provider-backed"
        with self.assertRaisesRegex(ValueError, "provider-backed"):
            validate_product_matrix(ROOT, document)
        document = copy.deepcopy(self.document)
        document["rows"][0]["local_evidence"][0]["tier"] = "remote"
        with self.assertRaisesRegex(ValueError, "invalid evidence tier"):
            validate_product_matrix(ROOT, document)
        document = copy.deepcopy(self.document)
        document["rows"][0]["local_evidence"][0]["response_body"] = "forbidden"
        with self.assertRaisesRegex(ValueError, "unknown local evidence fields"):
            validate_product_matrix(ROOT, document)

    def test_bash_syntax_evidence_rejects_option_injection_without_execution(self) -> None:
        bypass = ["bash", "-n", "+n", "-c", "printf BYPASS"]
        document = copy.deepcopy(self.document)
        document["rows"][0]["local_evidence"][0]["argv"] = bypass
        with self.assertRaisesRegex(ValueError, "unsafe bash syntax argv"):
            validate_product_matrix(ROOT, document)

        row = copy.deepcopy(self.document["rows"][0])
        row["local_evidence"][0]["argv"] = bypass
        with mock.patch("subprocess.run") as run:
            with self.assertRaisesRegex(ValueError, "unsafe bash syntax argv"):
                run_local_evidence(ROOT, (row,))
        run.assert_not_called()

    def test_bash_syntax_evidence_requires_normalized_existing_shell_files(self) -> None:
        invalid_suffixes = (
            ["bash", "-n"],
            ["bash", "-n", "-c", "true"],
            ["bash", "-n", "+n", "scripts/examples/dci_basic_example.sh"],
            ["bash", "-n", "../outside.sh"],
            ["bash", "-n", "/tmp/outside.sh"],
            ["bash", "-n", "tools/verify_asterion_dci_product.py"],
            ["bash", "-n", "scripts//examples/dci_basic_example.sh"],
        )
        for argv in invalid_suffixes:
            with self.subTest(argv=argv):
                document = copy.deepcopy(self.document)
                document["rows"][0]["local_evidence"][0]["argv"] = argv
                with self.assertRaisesRegex(ValueError, "unsafe bash syntax argv"):
                    validate_product_matrix(ROOT, document)
        valid = copy.deepcopy(self.document)
        valid["rows"][0]["local_evidence"][0]["argv"] = [
            "bash",
            "-n",
            "scripts/examples/dci_basic_example.sh",
            "scripts/examples/dci_runtime_context_example.sh",
        ]
        validate_product_matrix(ROOT, valid)

    def test_rows_require_exact_nonplaceholder_asterion_owners(self) -> None:
        self.assertEqual(
            {row["id"]: row["owner"] for row in self.document["rows"]},
            REQUIRED_PRODUCT_OWNERS,
        )
        for owner in ("", "unknown", "TODO-owner", "placeholder"):
            with self.subTest(owner=owner):
                document = copy.deepcopy(self.document)
                document["rows"][0]["owner"] = owner
                with self.assertRaisesRegex(ValueError, "owner"):
                    validate_product_matrix(ROOT, document)

    def test_rows_bind_exact_unique_provider_case_union(self) -> None:
        rows = self._validated_rows()
        cases = [case for row in rows for case in row["provider_evidence"]]
        self.assertEqual(set(cases), REQUIRED_PROVIDER_CASES)
        self.assertEqual(len(cases), len(set(cases)))
        examples = {row["id"]: row for row in rows}["source-and-asterion-examples"]
        self.assertEqual(
            set(examples["provider_evidence"]),
            {
                "source-basic",
                "source-runtime-context",
                "asterion-basic",
                "asterion-runtime-context",
            },
        )

    def test_provider_case_lists_reject_missing_duplicate_and_unknown_ids(self) -> None:
        mutations = []
        missing = copy.deepcopy(self.document)
        missing["rows"][5]["provider_evidence"] = []
        mutations.append(missing)
        duplicate = copy.deepcopy(self.document)
        duplicate["rows"][0]["provider_evidence"] = ["source-basic"]
        mutations.append(duplicate)
        unknown = copy.deepcopy(self.document)
        unknown["rows"][0]["provider_evidence"] = ["unregistered-case"]
        mutations.append(unknown)
        for document in mutations:
            with self.assertRaisesRegex(ValueError, "provider evidence"):
                validate_product_matrix(ROOT, document)

    def test_rows_execute_claimed_behavior_not_matrix_governance(self) -> None:
        rows = self._validated_rows()
        for row in rows:
            selectors = {
                selector
                for evidence in row["local_evidence"]
                for selector in evidence["selectors"]
            }
            self.assertEqual(selectors, EXPECTED_BEHAVIOR_SELECTORS[row["id"]])
            self.assertFalse(
                any(
                    selector.startswith("tests.test_asterion_dci_product_parity")
                    and selector not in product_verifier.PRODUCT_SEMANTIC_SELECTORS
                    for selector in selectors
                )
            )

    def test_behavior_rows_reject_matrix_governance_selectors(self) -> None:
        for method in (
            "test_af250_h001_exact_product_row_surface",
            "test_af250_h002_rows_define_stable_semantics",
        ):
            with self.subTest(method=method):
                selector = (
                    "tests.test_asterion_dci_product_parity."
                    f"AsterionDciProductParityTests.{method}"
                )
                document = copy.deepcopy(self.document)
                evidence = document["rows"][0]["local_evidence"][0]
                evidence["argv"] = [
                    "uv",
                    "run",
                    "python",
                    "-m",
                    "unittest",
                    selector,
                ]
                evidence["selectors"] = [selector]
                with self.assertRaisesRegex(ValueError, "matrix governance selector"):
                    validate_product_matrix(ROOT, document)

    def test_behavior_rows_require_exact_fully_qualified_semantic_selector(
        self,
    ) -> None:
        approved = (
            "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests."
            "test_af250_h002_completed_native_runs_have_equal_stable_semantics"
        )
        self.assertTrue(_resolve_selector(approved))
        spoof = (
            "tests.test_asterion_dci_product_parity._SpoofSemanticSelectors."
            "test_af250_h002_completed_native_runs_have_equal_stable_semantics"
        )
        self.assertTrue(_resolve_selector(spoof))
        document = copy.deepcopy(self.document)
        evidence = document["rows"][1]["local_evidence"][0]
        evidence["argv"] = ["uv", "run", "python", "-m", "unittest", spoof]
        evidence["selectors"] = [spoof]
        with self.assertRaisesRegex(ValueError, "matrix governance selector"):
            validate_product_matrix(ROOT, document)

    def test_matrix_rejects_missing_paths_empty_selectors_and_placeholders(self) -> None:
        missing = copy.deepcopy(self.document)
        missing["rows"][0]["source_entry_points"] = ["missing/source.py"]
        with self.assertRaisesRegex(ValueError, "entry point"):
            validate_product_matrix(ROOT, missing)
        empty = copy.deepcopy(self.document)
        empty["rows"][0]["local_evidence"][0]["selectors"] = []
        with self.assertRaisesRegex(ValueError, "selectors"):
            validate_product_matrix(ROOT, empty)
        placeholder = copy.deepcopy(self.document)
        placeholder["rows"][0]["stable_semantics"] = ["TODO later"]
        with self.assertRaisesRegex(ValueError, "placeholder"):
            validate_product_matrix(ROOT, placeholder)

    def test_default_executor_uses_literal_argv_and_skips_provider_evidence(self) -> None:
        rows = self._validated_rows()
        completed = subprocess.CompletedProcess([], 0, stdout="private body", stderr="secret")
        with mock.patch("subprocess.run", return_value=completed) as run:
            result = run_local_evidence(ROOT, rows)
        self.assertEqual(result["provider_backed_executed"], 0)
        self.assertNotIn("private body", json.dumps(result))
        self.assertNotIn("secret", json.dumps(result))
        self.assertEqual(result["delegated_inventory"], "533/533")
        self.assertEqual(result["launcher_pairs"], "12/12")
        self.assertEqual(result["batch_extra_selectors"], "6/6")
        for call in run.call_args_list:
            self.assertIs(call.kwargs["shell"], False)
            self.assertEqual(call.kwargs["cwd"], ROOT)

    def test_validate_only_cli_resolves_selectors_without_printing_environment(self) -> None:
        env = os.environ.copy()
        env["AF250_PRIVATE_SENTINEL"] = "must-not-be-printed"
        result = subprocess.run(
            ["python3", "tools/verify_asterion_dci_product.py", "--validate-only"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            {line.removesuffix(" VALID") for line in result.stdout.splitlines()},
            REQUIRED_PRODUCT_ROWS,
        )
        self.assertNotIn(env["AF250_PRIVATE_SENTINEL"], result.stdout + result.stderr)

    def test_default_cli_prints_the_exact_product_row_aggregate(self) -> None:
        summary = product_verifier.ProductAcceptanceSummary(
            product_rows=(8, 8),
            delegated_inventory=(533, 533),
            launcher_pairs=(12, 12),
            batch_extras=(6, 6),
            bounded_acceptance=(7, 7),
            provider_backed_executed=0,
            private_acceptance=None,
            row_statuses=(),
        )
        stdout = io.StringIO()
        with (
            mock.patch.object(product_verifier, "load_product_matrix", return_value={}),
            mock.patch.object(product_verifier, "validate_product_matrix", return_value=()),
            mock.patch.object(
                product_verifier,
                "verify_product_acceptance",
                return_value=summary,
            ),
            mock.patch.object(sys, "argv", ["verify_asterion_dci_product.py"]),
            contextlib.redirect_stdout(stdout),
        ):
            self.assertEqual(product_verifier.main(), 0)
        self.assertIn("product-rows 8/8\n", stdout.getvalue())

    def test_validate_only_cli_does_not_ignore_an_acceptance_root(self) -> None:
        private_root = "/tmp/af270-definitely-missing-private-evidence"
        environment = os.environ.copy()
        environment["DCI_EVAL_JUDGE_API_KEY_ENV"] = "DEEPSEEK_API_KEY"
        environment["DEEPSEEK_API_KEY"] = "PRIVATE-PLACEHOLDER-CREDENTIAL"
        result = subprocess.run(
            [
                "python3",
                "tools/verify_asterion_dci_product.py",
                "--validate-only",
                "--acceptance-root",
                private_root,
            ],
            cwd=ROOT,
            env=environment,
            text=True,
            capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn(" VALID", result.stdout)
        self.assertNotIn(private_root, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stderr, "private acceptance validation failed\n")

    # AF-250-H-001: source/Asterion runnable-surface completeness.
    def test_af250_h001_exact_product_row_surface(self) -> None:
        self.assertEqual({row["id"] for row in self._validated_rows()}, REQUIRED_PRODUCT_ROWS)

    def test_af250_h001_source_entry_points_exist(self) -> None:
        for row in self._validated_rows():
            self.assertTrue(all((ROOT / path).is_file() for path in row["source_entry_points"]))

    def test_af250_h001_asterion_entry_points_exist(self) -> None:
        for row in self._validated_rows():
            self.assertTrue(all((ROOT / path).is_file() for path in row["asterion_entry_points"]))

    def test_af250_h001_local_selectors_resolve(self) -> None:
        for row in self._validated_rows():
            for evidence in row["local_evidence"]:
                self.assertTrue(all(_resolve_selector(item) for item in evidence["selectors"]))

    # AF-250-H-002: stable cross-product semantic comparison.
    def test_af250_h002_rows_define_stable_semantics(self) -> None:
        for row in self._validated_rows():
            self.assertGreaterEqual(len(row["stable_semantics"]), 2)

    def test_af250_h002_completed_native_runs_have_equal_stable_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            source = root / "source"
            asterion = root / "asterion"
            self.assertEqual(self._run_source_fixture(source, _SourceFixturePiClient), 0)
            self.assertEqual(
                self._run_asterion_fixture(root, asterion, _AsterionFixturePiClient),
                "completed",
            )

            source_view = canonical_run_semantics(source)
            asterion_view = canonical_run_semantics(asterion)

        expected = {
            "status": "completed",
            "event_stream": "parseable-jsonl",
            "raw_event_types": ["message_update", "agent_end"],
            "final_present": True,
            "final_answer": "provider-prose",
            "state_present": True,
            "provider": "fixture-provider",
            "model": "fixture-model",
            "tools": "read,bash",
            "max_turns": 100,
            "pi_provenance": {"commit": "fixture", "dirty": False},
            "resume_count": 0,
            "protocol_attempt_count": 1,
            "protocol_terminal": "completed",
        }
        self.assertEqual(source_view, expected)
        self.assertEqual(asterion_view, expected)

    def test_af250_h002_run_semantics_retain_typed_max_turns(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            source = root / "source"
            asterion = root / "asterion"
            self.assertEqual(self._run_source_fixture(source, _SourceFixturePiClient), 0)
            self.assertEqual(
                self._run_asterion_fixture(root, asterion, _AsterionFixturePiClient),
                "completed",
            )
            self.assertEqual(
                canonical_run_semantics(source), canonical_run_semantics(asterion)
            )
            state_path = asterion / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["max_turns"] = 7
            state_path.write_text(json.dumps(state), encoding="utf-8")
            self.assertNotEqual(
                canonical_run_semantics(source), canonical_run_semantics(asterion)
            )
            state["max_turns"] = "7"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "max_turns"):
                canonical_run_semantics(asterion)

    def test_af250_h002_configuration_precedence_and_effective_pi_argv_match(self) -> None:
        environment = {
            "DCI_PROVIDER": "environment-provider",
            "DCI_MODEL": "environment-model",
            "DCI_TOOLS": "read",
        }
        with mock.patch.dict(os.environ, environment, clear=True):
            with mock.patch.object(
                sys,
                "argv",
                [
                    "dci-agent-lite",
                    "--provider",
                    "explicit-provider",
                    "--model",
                    "explicit-model",
                    "--tools",
                    "read,bash",
                    "question",
                ],
            ):
                source_options = source_runner.parse_args()
            asterion_options = resolve_dci_runtime_options(
                {
                    "provider": "explicit-provider",
                    "model": "explicit-model",
                    "tools": "read,bash",
                }
            )
        self.assertEqual(
            (source_options.provider, source_options.model, source_options.tools),
            (
                asterion_options.provider,
                asterion_options.model,
                asterion_options.tools,
            ),
        )
        common = {
            "package_dir": Path("fixture-pi/packages/coding-agent"),
            "mode": "rpc",
            "provider": source_options.provider,
            "model": source_options.model,
            "tools": source_options.tools,
            "no_session": True,
            "system_prompt_file": None,
            "append_system_prompt_file": None,
            "extra_args": ["--thinking", "high"],
        }
        with mock.patch.object(
            source_runner, "ensure_built_pi_cli", return_value=Path("fixture-cli.js")
        ), mock.patch.object(source_runner, "_node_bin", return_value="node"):
            source_argv = source_runner.build_pi_command(**common)
        with mock.patch(
            "asterion.dci.pi_rpc.ensure_built_pi_cli",
            return_value=Path("fixture-cli.js"),
        ):
            asterion_argv = build_asterion_pi_command(**common, node_bin="node")
        self.assertEqual(source_argv, asterion_argv)

    def test_af250_h002_failed_and_resumed_lifecycle_is_not_normalized_away(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "source"
            asterion = root / "asterion"
            self.assertEqual(self._run_source_fixture(source, _SourceFailingPiClient), 1)
            self.assertEqual(
                self._run_asterion_fixture(root, asterion, _AsterionFailingPiClient),
                "failed",
            )
            source_failed = canonical_run_semantics(source)
            asterion_failed = canonical_run_semantics(asterion)
            self.assertEqual(source_failed, asterion_failed)
            self.assertEqual(source_failed["status"], "failed")
            self.assertFalse(source_failed["final_present"])

            self.assertEqual(
                self._run_source_fixture(source, _SourceFixturePiClient, resume=True), 0
            )
            self.assertEqual(
                self._run_asterion_fixture(
                    root, asterion, _AsterionFixturePiClient, resume=True
                ),
                "completed",
            )
            self.assertEqual(
                canonical_run_semantics(source), canonical_run_semantics(asterion)
            )
            resumed = canonical_run_semantics(source)
            self.assertEqual(resumed["resume_count"], 1)
            self.assertEqual(resumed["protocol_attempt_count"], 2)

    def test_af250_h002_run_normalizer_rejects_missing_or_malformed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with self.assertRaisesRegex(ValueError, "state.json"):
                canonical_run_semantics(root)
            (root / "state.json").write_text("{}", encoding="utf-8")
            (root / "events.jsonl").write_text("not-json\n", encoding="utf-8")
            (root / "protocol").mkdir()
            (root / "protocol/attempt-0001.events.jsonl").write_text(
                "not-json\n", encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "events.jsonl"):
                canonical_run_semantics(root)

    def test_af250_h002_judge_request_and_cache_invalidation_semantics_match(self) -> None:
        source_config = SourceJudgeConfig(
            base_url="https://judge.example.test/v1",
            api="responses",
            model="fixture-judge",
        )
        asterion_config = AsterionJudgeConfig(
            base_url="https://judge.example.test/v1",
            api="responses",
            model="fixture-judge",
        )
        fields = {
            "question": "question",
            "gold_answer": "gold",
            "predicted_answer": "answer",
        }
        source_request = build_source_judge_request(source_config, **fields)
        asterion_request = build_asterion_judge_request(asterion_config, **fields)
        self.assertEqual(source_config.public_dict(), asterion_config.public_dict())
        self.assertEqual(
            source_judge_public_identity(source_config),
            asterion_judge_public_identity(asterion_config),
        )
        self.assertEqual(source_request["model"], asterion_request["model"])
        self.assertEqual(
            source_request["max_output_tokens"],
            asterion_request["max_output_tokens"],
        )
        for value in fields.values():
            self.assertIn(value, json.dumps(source_request))
            self.assertIn(value, json.dumps(asterion_request))
        def source_verdict(**kwargs: object) -> dict[str, object]:
            config = kwargs["config"]
            assert isinstance(config, SourceJudgeConfig)
            return {
                **config.public_dict(),
                "judge_request_fingerprint": source_judge_fingerprint(
                    config=config,
                    question=str(kwargs["question"]),
                    gold_answer=str(kwargs["gold_answer"]),
                    predicted_answer=str(kwargs["predicted_answer"]),
                ),
                "is_correct": True,
                "attempts": 1,
                "judged_at": "2026-07-15T00:00:00Z",
                "normalized_prediction": "answer",
                "reason": "source provider prose",
            }

        def asterion_verdict(**kwargs: object) -> dict[str, object]:
            config = kwargs["config"]
            assert isinstance(config, AsterionJudgeConfig)
            return {
                **config.public_dict(),
                "judge_request_fingerprint": asterion_judge_fingerprint(
                    config=config,
                    question=str(kwargs["question"]),
                    gold_answer=str(kwargs["gold_answer"]),
                    predicted_answer=str(kwargs["predicted_answer"]),
                ),
                "is_correct": True,
                "attempts": 1,
                "judged_at": "2026-07-15T00:00:00Z",
                "normalized_prediction": "answer",
                "reason": "Asterion provider prose",
                "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
                "cost_estimate_usd": {
                    "input_cost": 0.0,
                    "cached_input_cost": 0.0,
                    "output_cost": 0.0,
                    "total_cost": 0.0,
                },
            }

        changed_source_config = SourceJudgeConfig(
            base_url=source_config.base_url, model="changed-judge"
        )
        changed_asterion_config = AsterionJudgeConfig(
            base_url=asterion_config.base_url, model="changed-judge"
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            source_run = root / "source"
            asterion_run = root / "asterion"
            self.assertEqual(
                self._run_source_fixture(source_run, _SourceFixturePiClient), 0
            )
            self.assertEqual(
                self._run_asterion_fixture(
                    root, asterion_run, _AsterionFixturePiClient
                ),
                "completed",
            )
            with mock.patch.object(
                source_runner, "judge_answer_sync", side_effect=source_verdict
            ) as source_transport:
                source_first = source_runner.evaluate_run_output(
                    output_dir=source_run, judge_config=source_config, **fields
                )
                source_reused = source_runner.evaluate_run_output(
                    output_dir=source_run, judge_config=source_config, **fields
                )
                source_changed_answer = source_runner.evaluate_run_output(
                    output_dir=source_run,
                    judge_config=source_config,
                    **{**fields, "gold_answer": "changed gold"},
                )
                source_changed_config = source_runner.evaluate_run_output(
                    output_dir=source_run,
                    judge_config=changed_source_config,
                    **fields,
                )
            with mock.patch(
                "asterion.dci.evaluation.judge_answer_sync",
                side_effect=asterion_verdict,
            ) as asterion_transport:
                asterion_first = evaluate_run_directory(
                    asterion_run, gold_answer="gold", judge_config=asterion_config
                )
                asterion_reused = evaluate_run_directory(
                    asterion_run, gold_answer="gold", judge_config=asterion_config
                )
                asterion_changed_answer = evaluate_run_directory(
                    asterion_run,
                    gold_answer="changed gold",
                    judge_config=asterion_config,
                )
                asterion_changed_config = evaluate_run_directory(
                    asterion_run,
                    gold_answer="gold",
                    judge_config=changed_asterion_config,
                )

        self.assertEqual(source_transport.call_count, 3)
        self.assertEqual(asterion_transport.call_count, 3)
        self.assertEqual(
            source_first["judge_request_fingerprint"],
            source_reused["judge_request_fingerprint"],
        )
        self.assertEqual(
            asterion_first["judge_request_fingerprint"],
            asterion_reused["judge_request_fingerprint"],
        )
        for baseline, changed_answer, changed_config in (
            (source_first, source_changed_answer, source_changed_config),
            (asterion_first, asterion_changed_answer, asterion_changed_config),
        ):
            self.assertIs(canonical_judge_semantics(baseline)["is_correct"], True)
            self.assertNotEqual(
                baseline["judge_request_fingerprint"],
                changed_answer["judge_request_fingerprint"],
            )
            self.assertNotEqual(
                baseline["judge_request_fingerprint"],
                changed_config["judge_request_fingerprint"],
            )

    def test_af250_h002_batch_semantics_keep_counts_ndcg_exports_and_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            source_qa, source_runs, source_judges = self._write_source_batch_evidence(
                root, mode="qa", rows=2
            )
            asterion_qa, asterion_runs, asterion_judges = (
                self._write_asterion_batch_evidence(root, mode="qa", rows=2)
            )
            self.assertEqual((source_runs, source_judges), (2, 2))
            self.assertEqual((asterion_runs, asterion_judges), (2, 1))
            self.assertEqual(
                canonical_batch_semantics(source_qa),
                canonical_batch_semantics(asterion_qa),
            )

            source_ir, source_ir_runs, _ = self._write_source_batch_evidence(
                root, mode="ir", rows=1
            )
            asterion_ir, asterion_ir_runs, _ = self._write_asterion_batch_evidence(
                root, mode="ir", rows=1
            )
            self.assertEqual((source_ir_runs, asterion_ir_runs), (1, 1))
            source_ir_view = canonical_batch_semantics(source_ir)
            asterion_ir_view = canonical_batch_semantics(asterion_ir)
            self.assertEqual(
                source_ir_view,
                asterion_ir_view,
                (asterion_ir / "results.jsonl").read_text(encoding="utf-8"),
            )
            self.assertEqual(source_ir_view["ndcg_at_10"], 0.0)

    def test_af250_h002_bcplus_and_bright_export_transforms_match(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            bc_source = root / "bc-source"
            bc_source.mkdir()
            pq.write_table(
                pa.Table.from_pylist(
                    [
                        {
                            "docid": "1",
                            "text": "Title: Fixture\nbody",
                            "url": "https://example.test/doc",
                        }
                    ]
                ),
                bc_source / "part.parquet",
            )
            source_bc = root / "source-bc"
            asterion_bc = root / "asterion-bc"
            with (
                mock.patch.object(
                    sys,
                    "argv",
                    [
                        "export-bc",
                        "--source-dir",
                        str(bc_source),
                        "--output-dir",
                        str(source_bc),
                    ],
                ),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                source_bcplus_export.main()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                self.assertEqual(export_bcplus(bc_source, asterion_bc), 1)

            bright_source = root / "bright-source"
            bright_source.mkdir()
            pq.write_table(
                pa.Table.from_pylist([{"id": "nested/doc.txt", "content": "body"}]),
                bright_source / "part.parquet",
            )
            source_bright = root / "source-bright"
            asterion_bright = root / "asterion-bright"
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(
                io.StringIO()
            ):
                self.assertEqual(source_bright_export(bright_source, source_bright), 1)
                self.assertEqual(
                    asterion_bright_export(bright_source, asterion_bright), 1
                )

            def contents(directory: Path) -> dict[Path, str]:
                return {
                    path.relative_to(directory): path.read_text(encoding="utf-8")
                    for path in directory.rglob("*")
                    if path.is_file() and path.name != ".asterion-dci-export.lock"
                }

            self.assertEqual(contents(source_bc), contents(asterion_bc))
            self.assertEqual(contents(source_bright), contents(asterion_bright))

    def test_af250_h002_products_keep_distinct_entry_points(self) -> None:
        for row in self._validated_rows():
            self.assertTrue(set(row["source_entry_points"]).isdisjoint(row["asterion_entry_points"]))

    def test_af250_h002_batch_row_delegates_to_digest_bound_inventory(self) -> None:
        row = {item["id"]: item for item in self._validated_rows()}[
            "batch-ir-analysis-and-exports"
        ]
        self.assertIn("assets/dci/batch-parity.json", row["source_entry_points"])
        self.test_matrix_binds_the_exact_af240_inventory()

    def test_af250_h002_matrix_contains_no_placeholder_text(self) -> None:
        for row in self.document["rows"]:
            serialized = json.dumps(row["stable_semantics"], sort_keys=True).casefold()
            for token in ("placeholder", "todo", "tbd", "unknown", "n/a"):
                self.assertNotIn(token, serialized)

    # AF-250-H-003: installed wheel/application independence.
    def test_af250_h003_installed_rows_are_explicit(self) -> None:
        row_ids = {row["id"] for row in self._validated_rows()}
        self.assertIn("installed-wheel-boundary", row_ids)
        self.assertIn("installed-pi-application", row_ids)

    def test_af250_h003_wheel_row_names_distribution_boundaries(self) -> None:
        row = {item["id"]: item for item in self._validated_rows()}["installed-wheel-boundary"]
        self.assertIn("pyproject.toml", row["source_entry_points"])
        self.assertTrue(any("distribution" in path for path in row["asterion_entry_points"]))

    def test_af250_h003_application_row_names_bundled_assembly(self) -> None:
        row = {item["id"]: item for item in self._validated_rows()}["installed-pi-application"]
        self.assertTrue(
            any(path.endswith("dci-research-capability.json") for path in row["asterion_entry_points"])
        )

    def test_af250_h003_installed_evidence_is_model_free(self) -> None:
        for row in self._validated_rows():
            if not row["id"].startswith("installed-"):
                continue
            self.assertTrue(all(item["tier"] == "model-free" for item in row["local_evidence"]))

    def test_af250_h003_fresh_installed_product_runs_outside_repository(self) -> None:
        evidence = product_verifier.run_installed_product_proof(ROOT)
        self.assertEqual(evidence["dci_importable"], False)
        self.assertEqual(evidence["profiles"], 14)
        self.assertEqual(evidence["asterion_dci_help"], 0)
        self.assertEqual(evidence["asterion_list"], 0)
        self.assertEqual(evidence["paper_contract"], "packaged")
        self.assertEqual(evidence["paper_dataset_count"], 13)
        self.assertEqual(evidence["paper_scope_count"], 16)
        self.assertEqual(evidence["paper_ablation_count"], 20)
        self.assertEqual(set(evidence["paper_resource_digests"]), {
            "ablation_matrix_sha256",
            "benchmark_inventory_sha256",
            "experiment_scopes_sha256",
        })
        self.assertEqual(evidence["installed_application"], "completed")
        self.assertEqual(evidence["answer_artifact_uri"], "final.txt")
        self.assertEqual(evidence["native_artifact_uri"], "state.json")
        self.assertEqual(evidence["body_free"], True)
        self.assertEqual(
            evidence["runtime_options"],
            {
                "provider": "fixture-provider",
                "model": "fixture-model",
                "tools": "read,bash",
                "runtime_context_level": "level3",
                "thinking_level": "high",
            },
        )

    def test_installed_artifact_validation_rejects_missing_or_mismatched_files(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory)
            run = output_root / "installed-fixture"
            run.mkdir()
            state = {
                "status": "completed",
                "assistant_text": "PRIVATE-FIXTURE-ANSWER",
                "provider": "fixture-provider",
                "model": "fixture-model",
                "tools": "read,bash",
                "runtime_context_level": "level3",
                "thinking_level": "high",
            }
            payload = {
                "artifacts": [{"value": {
                    "answer_artifact_uri": "final.txt",
                    "state_artifact_uri": "state.json",
                }}]
            }
            (run / "state.json").write_text(json.dumps(state), encoding="utf-8")
            (run / "final.txt").write_text(
                "PRIVATE-FIXTURE-ANSWER\n", encoding="utf-8"
            )
            evidence = product_verifier.validate_installed_application_artifacts(
                output_root, payload, "body-free projection"
            )
            self.assertTrue(evidence["body_free"])
            (run / "final.txt").unlink()
            with self.assertRaisesRegex(RuntimeError, "artifact"):
                product_verifier.validate_installed_application_artifacts(
                    output_root, payload, "body-free projection"
                )
            (run / "final.txt").write_text(
                "PRIVATE-FIXTURE-ANSWER\n", encoding="utf-8"
            )
            for invalid_uri in (
                "other.json",
                "file:///state.json",
                "../state.json",
                "%2e%2e/state.json",
            ):
                mismatched = copy.deepcopy(payload)
                mismatched["artifacts"][0]["value"][
                    "state_artifact_uri"
                ] = invalid_uri
                with self.subTest(uri=invalid_uri), self.assertRaisesRegex(
                    RuntimeError, "artifact"
                ):
                    product_verifier.validate_installed_application_artifacts(
                        output_root, mismatched, "body-free projection"
                    )
            (run / "final.txt").write_text("\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "artifact"):
                product_verifier.validate_installed_application_artifacts(
                    output_root, payload, "body-free projection"
                )
            (run / "final.txt").write_text(
                "PRIVATE-FIXTURE-ANSWER\n", encoding="utf-8"
            )
            (run / "state.json").unlink()
            with self.assertRaisesRegex(RuntimeError, "state"):
                product_verifier.validate_installed_application_artifacts(
                    output_root, payload, "body-free projection"
                )

    def test_installed_artifact_validation_rejects_body_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_root = Path(temporary_directory)
            run = output_root / "installed-fixture"
            run.mkdir()
            (run / "state.json").write_text(
                json.dumps({
                    "status": "completed",
                    "assistant_text": "PRIVATE-FIXTURE-ANSWER",
                    "provider": "fixture-provider",
                    "model": "fixture-model",
                    "tools": "read,bash",
                    "runtime_context_level": "level3",
                    "thinking_level": "high",
                }),
                encoding="utf-8",
            )
            (run / "final.txt").write_text(
                "PRIVATE-FIXTURE-ANSWER\n", encoding="utf-8"
            )
            payload = {"artifacts": [{"value": {
                "answer_artifact_uri": "final.txt",
                "state_artifact_uri": "state.json",
            }}]}
            with self.assertRaisesRegex(RuntimeError, "body-free"):
                product_verifier.validate_installed_application_artifacts(
                    output_root, payload, "PRIVATE-FIXTURE-ANSWER"
                )

    # AF-250-H-004: bounded evidence and final matrix closure governance.
    def test_af250_h004_all_rows_are_supported(self) -> None:
        self.assertTrue(all(row["unsupported"] is False for row in self._validated_rows()))

    def test_af250_h004_provider_cases_are_body_free_ids(self) -> None:
        for row in self._validated_rows():
            case_ids = row["provider_evidence"]
            self.assertIsInstance(case_ids, list)
            self.assertTrue(all(isinstance(case_id, str) and case_id for case_id in case_ids))

    def test_af250_h004_local_executor_never_runs_provider_cases(self) -> None:
        rows = self._validated_rows()
        with mock.patch(
            "subprocess.run", return_value=subprocess.CompletedProcess([], 0)
        ):
            result = run_local_evidence(ROOT, rows)
        self.assertEqual(result["provider_backed_executed"], 0)

    def test_af250_h004_matrix_schema_and_inventory_are_finalized(self) -> None:
        self.assertEqual(self.document["schema"], "asterion.dci.product-parity/v1")
        self.test_matrix_binds_the_exact_af240_inventory()


from tests.test_asterion_dci_paper_product import (  # noqa: E402
    PaperBenchmarkProductParityTests as _PaperBenchmarkProductParityTests,
)


class PaperBenchmarkProductParityTests(_PaperBenchmarkProductParityTests):
    """Plan-addressable AF-320 source/product parity selector."""


if __name__ == "__main__":
    unittest.main()
