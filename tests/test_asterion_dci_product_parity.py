from __future__ import annotations

import copy
import hashlib
import importlib
import json
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

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
        "tests.test_check_judge.CheckJudgeTests.test_make_config_target_is_independently_executable",
        "tests.test_config.PiPathConfigTests.test_environment_can_override_all_pi_paths",
        "tests.test_asterion_dci_config.AsterionDciConfigTests.test_runtime_options_merge_shared_env_and_explicit_values",
        "tests.test_asterion_dci_run.AsterionDciRunTests.test_runtime_options_map_to_native_pi_request",
    },
    "interactive-run-and-terminal": {
        "tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_waits_for_agent_settled",
        "tests.test_asterion_dci_cli.AsterionDciCliTests.test_terminal_maps_operator_controls_without_artifacts",
        "tests.test_asterion_dci_pi_rpc.PiRpcCommandTests.test_terminal_uses_literal_argv_inherited_heap_and_exit_status",
    },
    "native-artifacts-and-resume": {
        "tests.test_pi_rpc_runner.PiRpcLifecycleTests.test_run_recorder_isolates_protocol_attempts_on_resume",
        "tests.test_asterion_dci_artifacts.AsterionDciArtifactTests.test_recorder_writes_original_durable_artifact_set",
        "tests.test_asterion_dci_run.AsterionDciRunTests.test_resume_reuses_failed_directory_and_creates_a_second_protocol_attempt",
    },
    "judge-and-exact-cache": {
        "tests.test_judge.JudgeTransportTests.test_judge_request_fingerprint_is_deterministic_and_endpoint_sensitive",
        "tests.test_judge.JudgeResultReuseTests.test_backend_identity_is_part_of_result_reuse",
        "tests.test_asterion_dci_evaluation.AsterionDciEvaluationTests.test_reuses_only_an_exact_judge_request_fingerprint",
    },
    "batch-ir-analysis-and-exports": {
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
                    for selector in selectors
                )
            )

    def test_behavior_rows_reject_matrix_governance_selectors(self) -> None:
        selector = (
            "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests."
            "test_af250_h001_exact_product_row_surface"
        )
        document = copy.deepcopy(self.document)
        evidence = document["rows"][0]["local_evidence"][0]
        evidence["argv"] = ["uv", "run", "python", "-m", "unittest", selector]
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
