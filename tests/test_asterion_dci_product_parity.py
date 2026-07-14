from __future__ import annotations

import copy
import contextlib
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

import pyarrow as pa
import pyarrow.parquet as pq
import dci.benchmark.pi_rpc_runner as source_runner
import dci.benchmark.export_bc_plus_docs as source_bcplus_export
from dci.benchmark.export_bright_docs import export_subset as source_bright_export
from dci.benchmark.judge import (
    JudgeConfig as SourceJudgeConfig,
    build_judge_request as build_source_judge_request,
    judge_request_fingerprint as source_judge_fingerprint,
)
from asterion.dci.config import resolve_dci_paths, resolve_dci_runtime_options
from asterion.dci.judge import (
    JudgeConfig as AsterionJudgeConfig,
    build_judge_request as build_asterion_judge_request,
    judge_request_fingerprint as asterion_judge_fingerprint,
)
from asterion.dci.pi_rpc import build_pi_command as build_asterion_pi_command
from asterion.dci.export import export_bcplus, export_subset as asterion_bright_export
from asterion.dci.run import DciRunError, DciRunRequest, run_pi_research
from tests.asterion_dci_parity_helpers import (
    canonical_batch_semantics,
    canonical_judge_semantics,
    canonical_run_semantics,
)

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
        "tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_run_recorder_isolates_protocol_attempts_on_resume",
        "tests.test_asterion_dci_artifacts.AsterionDciArtifactTests.test_recorder_writes_original_durable_artifact_set",
        "tests.test_asterion_dci_run.AsterionDciRunTests.test_resume_reuses_failed_directory_and_creates_a_second_protocol_attempt",
    },
    "judge-and-exact-cache": {
        "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_judge_semantics_keep_verdict_type_and_fingerprint",
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
    },
}


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
        return f"provider prose for {question}"


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
        return f"provider prose for {question}"


class _AsterionFailingPiClient(_AsterionFixturePiClient):
    def prompt_and_wait(self, question: str, *, on_event, **_: object) -> str:
        self.calls += 1
        on_event({"type": "agent_end"})
        raise RuntimeError(f"private provider failure for {question}")


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
                    and ".test_af250_h002_" not in selector
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
            "pi_provenance": {"commit": "fixture", "dirty": False},
            "resume_count": 0,
            "protocol_attempt_count": 1,
            "protocol_terminal": "completed",
        }
        self.assertEqual(source_view, expected)
        self.assertEqual(asterion_view, expected)

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

    def test_af250_h002_judge_semantics_keep_verdict_type_and_fingerprint(self) -> None:
        source = {
            "is_correct": True,
            "judge_request_fingerprint": "a" * 64,
            "judge_model": "fixture-judge",
            "judge_api": "responses",
            "reason": "source prose",
        }
        asterion = {
            **source,
            "reason": "different provider prose",
            "judged_at": "2026-07-15T00:00:00Z",
        }
        self.assertEqual(
            canonical_judge_semantics(source), canonical_judge_semantics(asterion)
        )
        changed = {**asterion, "judge_request_fingerprint": "b" * 64}
        self.assertNotEqual(
            canonical_judge_semantics(source), canonical_judge_semantics(changed)
        )
        with self.assertRaisesRegex(ValueError, "boolean"):
            canonical_judge_semantics({**source, "is_correct": 1})

    def test_af250_h002_judge_request_and_cache_invalidation_semantics_match(self) -> None:
        source_config = SourceJudgeConfig(
            base_url="https://judge.example.test/v1", model="fixture-judge"
        )
        asterion_config = AsterionJudgeConfig(
            base_url="https://judge.example.test/v1", model="fixture-judge"
        )
        fields = {
            "question": "question",
            "gold_answer": "gold",
            "predicted_answer": "answer",
        }
        source_request = build_source_judge_request(source_config, **fields)
        asterion_request = build_asterion_judge_request(asterion_config, **fields)
        self.assertEqual(source_config.public_dict(), asterion_config.public_dict())
        self.assertEqual(source_request["model"], asterion_request["model"])
        self.assertEqual(
            source_request["max_output_tokens"],
            asterion_request["max_output_tokens"],
        )
        for value in fields.values():
            self.assertIn(value, json.dumps(source_request))
            self.assertIn(value, json.dumps(asterion_request))
        source_fingerprint = source_judge_fingerprint(config=source_config, **fields)
        asterion_fingerprint = asterion_judge_fingerprint(
            config=asterion_config, **fields
        )
        self.assertRegex(source_fingerprint, r"^[0-9a-f]{64}$")
        self.assertRegex(asterion_fingerprint, r"^[0-9a-f]{64}$")
        for changed_fields in (
            {**fields, "predicted_answer": "changed answer"},
            fields,
        ):
            changed_source = (
                SourceJudgeConfig(
                    base_url="https://judge.example.test/v1", model="changed-judge"
                )
                if changed_fields is fields
                else source_config
            )
            changed_asterion = (
                AsterionJudgeConfig(
                    base_url="https://judge.example.test/v1", model="changed-judge"
                )
                if changed_fields is fields
                else asterion_config
            )
            source_changed = source_judge_fingerprint(
                config=changed_source, **changed_fields
            )
            asterion_changed = asterion_judge_fingerprint(
                config=changed_asterion, **changed_fields
            )
            self.assertNotEqual(source_fingerprint, source_changed)
            self.assertNotEqual(asterion_fingerprint, asterion_changed)

    def test_af250_h002_batch_semantics_keep_counts_ndcg_exports_and_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            views = []
            for product in ("source", "asterion"):
                batch = root / product
                batch.mkdir()
                (batch / "state.json").write_text(
                    json.dumps(
                        {
                            "status": "completed",
                            "counts": {"total": 2, "correct": 1, "failed": 1},
                        }
                    ),
                    encoding="utf-8",
                )
                (batch / "summary.json").write_text(
                    json.dumps({"ndcg_at_10": 0.75}), encoding="utf-8"
                )
                (batch / "results.jsonl").write_text(
                    json.dumps({"query_id": "q-0", "status": "completed", "reused": True})
                    + "\n"
                    + json.dumps({"query_id": "q-1", "status": "failed", "reused": False})
                    + "\n",
                    encoding="utf-8",
                )
                (batch / "exports.json").write_text(
                    json.dumps({"bcplus": 2, "bright": 3}), encoding="utf-8"
                )
                views.append(canonical_batch_semantics(batch))
            self.assertEqual(views[0], views[1])
            self.assertEqual(
                views[0],
                {
                    "status": "completed",
                    "counts": {"total": 2, "correct": 1, "failed": 1},
                    "failure_classification": ["failed"],
                    "ndcg_at_10": 0.75,
                    "exports": {"bcplus": 2, "bright": 3},
                    "reuse_decisions": [True, False],
                },
            )

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


if __name__ == "__main__":
    unittest.main()
