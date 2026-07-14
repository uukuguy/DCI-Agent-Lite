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
            case_id = row["provider_evidence"]
            self.assertTrue(case_id is None or (isinstance(case_id, str) and case_id))

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
