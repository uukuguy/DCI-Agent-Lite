from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from pathlib import PurePosixPath
from unittest.mock import patch

from tools.verify_asterion_dci_product import (
    ProductAcceptanceSummary,
    _required_acceptance_credential_values,
    load_product_matrix,
    validate_acceptance_artifacts,
    validate_acceptance_document,
    validate_acceptance_reference,
    verify_product_acceptance,
    run_installed_product_proof,
)


ROOT = Path(__file__).parents[1]
MANIFEST_PATH = ROOT / "assets/dci/product-acceptance.json"
SCHEMA = "asterion.dci.product-acceptance/v1"
REQUIRED_CASE_IDS = {
    "source-basic",
    "source-runtime-context",
    "asterion-basic",
    "asterion-runtime-context",
    "installed-pi-application",
    "one-row-pi-judge",
    "one-row-exact-reuse",
}
PRIVATE_PATH = re.compile(r"(?:^|[\"'])/(?:private|Users|home)/")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^\s\"']+"
)
FORBIDDEN_BODY_TEXT = re.compile(
    r"(?i)(?:provider[_ -]?(?:request|response)|conversation|final[_ -]?answer|stderr)"
)
ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FILE_MODE = re.compile(r"^[0-7]{3}$")


def validate_manifest(document: object) -> None:
    """Fail closed on body-bearing or incomplete provider acceptance evidence."""
    if not isinstance(document, dict) or set(document) != {"schema", "cases"}:
        raise ValueError("manifest shape is invalid")
    if document["schema"] != SCHEMA:
        raise ValueError("manifest schema is invalid")
    cases = document["cases"]
    if not isinstance(cases, list):
        raise ValueError("manifest cases are invalid")
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if set(ids) != REQUIRED_CASE_IDS or len(ids) != len(REQUIRED_CASE_IDS):
        raise ValueError("manifest cases are incomplete")
    encoded = json.dumps(document, sort_keys=True)
    if PRIVATE_PATH.search(encoded):
        raise ValueError("manifest contains an absolute private path")
    if SECRET_ASSIGNMENT.search(encoded):
        raise ValueError("manifest contains a plaintext credential")
    if FORBIDDEN_BODY_TEXT.search(encoded):
        raise ValueError("manifest contains a provider body reference")
    for case in cases:
        if not isinstance(case, dict) or set(case) != {
            "id",
            "command_template",
            "inherited_configuration",
            "exit_status",
            "structural_artifacts",
            "verdict",
            "counts",
            "timestamp",
        }:
            raise ValueError("case shape is invalid")
        command_template = case["command_template"]
        if not isinstance(command_template, str) or not command_template.strip():
            raise ValueError("case command template is invalid")
        inherited = case["inherited_configuration"]
        if (
            not isinstance(inherited, list)
            or not inherited
            or len(inherited) != len(set(inherited))
            or not all(
                isinstance(name, str) and ENVIRONMENT_NAME.fullmatch(name)
                for name in inherited
            )
        ):
            raise ValueError("case inherited configuration is invalid")
        if case["exit_status"] != 0:
            raise ValueError("case exit status is not successful")
        artifacts = case["structural_artifacts"]
        if not isinstance(artifacts, list) or not artifacts:
            raise ValueError("case has no structural artifact checks")
        if not all(
            isinstance(item, dict)
            and set(item) == {"name", "mode", "sha256"}
            and isinstance(item["name"], str)
            and item["name"]
            and not PurePosixPath(item["name"]).is_absolute()
            and ".." not in PurePosixPath(item["name"]).parts
            and isinstance(item["mode"], str)
            and FILE_MODE.fullmatch(item["mode"])
            and isinstance(item["sha256"], str)
            and SHA256.fullmatch(item["sha256"])
            for item in artifacts
        ):
            raise ValueError("structural artifact check is invalid")
        verdict = case["verdict"]
        if verdict is not None and type(verdict) is not bool:
            raise ValueError("case verdict type is invalid")
        if case["id"] == "one-row-pi-judge" and type(verdict) is not bool:
            raise ValueError("Judge verdict must be boolean")
        counts = case["counts"]
        if (
            not isinstance(counts, dict)
            or not counts
            or not all(
                isinstance(name, str)
                and name
                and type(value) is int
                and value >= 0
                for name, value in counts.items()
            )
        ):
            raise ValueError("case counts are invalid")
        if case["id"] == "one-row-exact-reuse" and (
            counts.get("protocol_attempts") != 1
            or counts.get("native_generations") != 1
        ):
            raise ValueError("reuse must retain exactly one attempt and generation")
        timestamp = case["timestamp"]
        if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
            raise ValueError("case timestamp is invalid")
        try:
            parsed_timestamp = datetime.fromisoformat(timestamp.removesuffix("Z") + "+00:00")
        except ValueError as error:
            raise ValueError("case timestamp is invalid") from error
        if parsed_timestamp.tzinfo is None:
            raise ValueError("case timestamp is invalid")


class AsterionDciProductAcceptanceTests(unittest.TestCase):
    def test_importable_product_acceptance_returns_typed_body_free_counts(self) -> None:
        rows = tuple(
            {"id": row_id}
            for row_id in (
                "configuration-and-pi-argv",
                "interactive-run-and-terminal",
                "native-artifacts-and-resume",
                "judge-and-exact-cache",
                "batch-ir-analysis-and-exports",
                "source-and-asterion-examples",
                "installed-wheel-boundary",
                "installed-pi-application",
            )
        )
        local = {
            "rows": [{"id": row["id"], "status": "PASS", "exit_status": 0} for row in rows],
            "provider_backed_executed": 0,
            "bounded_acceptance": "7/7",
            "delegated_inventory": "537/537",
            "launcher_pairs": "12/12",
            "batch_extra_selectors": "6/6",
        }
        with (
            patch(
                "tools.verify_asterion_dci_product.validate_product_matrix",
                return_value=rows,
            ),
            patch(
                "tools.verify_asterion_dci_product.run_local_evidence",
                return_value=local,
            ),
        ):
            summary = verify_product_acceptance(ROOT)

        self.assertIsInstance(summary, ProductAcceptanceSummary)
        self.assertEqual(summary.product_rows, (8, 8))
        self.assertEqual(summary.delegated_inventory, (537, 537))
        self.assertEqual(summary.launcher_pairs, (12, 12))
        self.assertEqual(summary.batch_extras, (6, 6))
        self.assertEqual(summary.bounded_acceptance, (7, 7))
        self.assertEqual(summary.provider_backed_executed, 0)

    def test_private_acceptance_requires_manifest_referenced_credentials(
        self,
    ) -> None:
        cases = (
            {
                "inherited_configuration": [
                    "PROVIDER_API_KEY",
                    "DCI_EVAL_JUDGE_API_KEY_ENV",
                ]
            },
        )
        with patch.dict(
            os.environ,
            {"UNRELATED_PASSWORD": "irrelevant"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "referenced credential"):
                _required_acceptance_credential_values(cases)

        with patch.dict(
            os.environ,
            {"PROVIDER_API_KEY": "provider-secret"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "DCI_EVAL_JUDGE_API_KEY_ENV"):
                _required_acceptance_credential_values(cases)

        with patch.dict(
            os.environ,
            {
                "DCI_EVAL_JUDGE_API_KEY_ENV": "CUSTOM_JUDGE_KEY",
                "CUSTOM_JUDGE_KEY": "judge-secret",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "PROVIDER_API_KEY"):
                _required_acceptance_credential_values(cases)

        with patch.dict(
            os.environ,
            {
                "PROVIDER_API_KEY": "provider-secret",
                "DCI_EVAL_JUDGE_API_KEY_ENV": "CUSTOM_JUDGE_KEY",
            },
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "CUSTOM_JUDGE_KEY"):
                _required_acceptance_credential_values(cases)

        with patch.dict(
            os.environ,
            {
                "PROVIDER_API_KEY": "provider-secret",
                "DCI_EVAL_JUDGE_API_KEY_ENV": "CUSTOM_JUDGE_KEY",
                "CUSTOM_JUDGE_KEY": "judge-secret",
            },
            clear=True,
        ):
            self.assertEqual(
                _required_acceptance_credential_values(cases),
                ("provider-secret", "judge-secret"),
            )

    def load_manifest(self) -> dict[str, object]:
        self.assertTrue(MANIFEST_PATH.is_file(), "acceptance manifest is required")
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def test_manifest_is_complete_and_body_free(self) -> None:
        manifest = self.load_manifest()
        validate_manifest(manifest)
        self.assertEqual(len(validate_acceptance_document(manifest)), 7)

    def test_af250_h005_manifest_is_canonical_and_digest_bound(self) -> None:
        reference = load_product_matrix(ROOT)["product_acceptance"]
        self.assertEqual(reference["path"], "assets/dci/product-acceptance.json")
        self.assertEqual(reference["case_count"], 7)
        self.assertEqual(
            reference["sha256"], hashlib.sha256(MANIFEST_PATH.read_bytes()).hexdigest()
        )
        self.assertEqual(validate_acceptance_reference(ROOT, reference), 7)

    def test_af250_h005_all_seven_provider_cases_are_successful(self) -> None:
        cases = validate_acceptance_document(self.load_manifest())
        self.assertEqual({case["id"] for case in cases}, REQUIRED_CASE_IDS)
        self.assertTrue(all(case["exit_status"] == 0 for case in cases))
        self.assertTrue(all(case["structural_artifacts"] for case in cases))

    def test_af250_h005_manifest_rejects_bodies_credentials_and_private_paths(self) -> None:
        for command in ("provider response", "API_KEY=plain", "/private/tmp/value"):
            with self.subTest(command=command):
                document = self.load_manifest()
                document["cases"][0]["command_template"] = command
                with self.assertRaises(ValueError):
                    validate_acceptance_document(document)

    def test_af250_h005_judge_and_exact_reuse_are_retained(self) -> None:
        cases = {
            case["id"]: case
            for case in validate_acceptance_document(self.load_manifest())
        }
        self.assertIs(cases["one-row-pi-judge"]["verdict"], True)
        counts = cases["one-row-exact-reuse"]["counts"]
        self.assertEqual(counts["protocol_attempts"], 1)
        self.assertEqual(counts["native_generations"], 1)

    def _private_fixture(
        self, root: Path, document: dict[str, object]
    ) -> tuple[dict[str, object], ...]:
        cases = document["cases"]
        self.assertIsInstance(cases, list)
        for case in cases:
            case_root = root / case["id"]
            case_root.mkdir(parents=True)
            names = {item["name"] for item in case["structural_artifacts"]}
            for name in names:
                path = case_root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                if name == "state.json":
                    content = json.dumps(
                        {"status": "completed", "assistant_text": "answer"}
                    )
                elif name == "events.jsonl":
                    content = json.dumps({"type": "agent_settled"}) + "\n"
                elif name == "final.txt":
                    content = "answer\n"
                elif name == "eval_result.json":
                    content = json.dumps(
                        {
                            "is_correct": True,
                            "judge_request_fingerprint": "0" * 64,
                        }
                    )
                elif name == "summary.json":
                    content = json.dumps({"counts": {"total": 1, "correct": 1}})
                elif name == "result.json":
                    content = json.dumps({"status": "completed", "is_correct": True})
                else:
                    content = json.dumps({"type": "run.completed"}) + "\n"
                path.write_text(content, encoding="utf-8")
            if "events" in case["counts"]:
                case["counts"]["events"] = 1

        judge_root = root / "one-row-pi-judge"
        reuse_root = root / "one-row-exact-reuse"
        private_tree = judge_root / "private-tree"
        private_tree.mkdir()
        for index in range(28):
            (private_tree / f"artifact-{index:02d}.json").write_text(
                "{}\n", encoding="utf-8"
            )
        for name in (
            "events.jsonl",
            "eval_result.json",
            "protocol/attempt-0001.events.jsonl",
        ):
            shutil.copy2(judge_root / name, reuse_root / name)

        for case in cases:
            case_root = root / case["id"]
            for artifact in case["structural_artifacts"]:
                path = case_root / artifact["name"]
                mode = int(artifact["mode"], 8)
                os.chmod(path, mode)
                artifact["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        return tuple(cases)

    def test_af250_h005_private_acceptance_recomputes_artifacts_and_semantics(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cases = self._private_fixture(root, self.load_manifest())
            self.assertEqual(validate_acceptance_artifacts(root, cases), 7)

            (root / "source-basic/final.txt").write_text("changed\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "artifact mismatch"):
                validate_acceptance_artifacts(root, cases)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cases = self._private_fixture(root, self.load_manifest())
            path = root / "source-basic/final.txt"
            path.write_text("credential-value\n", encoding="utf-8")
            source = next(case for case in cases if case["id"] == "source-basic")
            artifact = next(
                item
                for item in source["structural_artifacts"]
                if item["name"] == "final.txt"
            )
            artifact["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "contains a credential"):
                validate_acceptance_artifacts(
                    root, cases, credential_values=("credential-value",)
                )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cases = self._private_fixture(root, self.load_manifest())
            reused = root / "one-row-exact-reuse/events.jsonl"
            stat = reused.stat()
            os.utime(reused, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1))
            with self.assertRaisesRegex(ValueError, "exact-reuse evidence changed"):
                validate_acceptance_artifacts(root, cases)

    def test_rejects_privacy_schema_and_reuse_regressions(self) -> None:
        document = self.load_manifest()
        cases = document["cases"]
        self.assertIsInstance(cases, list)
        for mutation in (
            lambda value: value.pop("source-basic"),
            lambda value: value["source-basic"].__setitem__("exit_status", 1),
            lambda value: value["source-basic"].__setitem__("structural_artifacts", []),
            lambda value: value["one-row-pi-judge"].__setitem__("verdict", "true"),
            lambda value: value["source-basic"].__setitem__("command_template", "API_KEY=plain"),
            lambda value: value["source-basic"].__setitem__("command_template", "/private/tmp/value"),
            lambda value: value["source-basic"].__setitem__("command_template", "--cwd=/private/tmp/value"),
            lambda value: value["source-basic"].__setitem__("command_template", "provider response"),
            lambda value: value["source-basic"].__setitem__("inherited_configuration", ["KEY=value"]),
            lambda value: value["source-basic"]["structural_artifacts"][0].__setitem__("name", "../state.json"),
            lambda value: value["source-basic"]["structural_artifacts"][0].__setitem__("sha256", "not-a-digest"),
            lambda value: value["source-basic"]["counts"].__setitem__("events", True),
            lambda value: value["source-basic"].__setitem__("timestamp", "not-a-timestamp"),
            lambda value: value["one-row-exact-reuse"]["counts"].__setitem__("protocol_attempts", 2),
            lambda value: value["one-row-exact-reuse"]["counts"].__setitem__("unchanged_mtimes", 0),
            lambda value: value["one-row-exact-reuse"]["counts"].__setitem__("unchanged_hashes", 4),
            lambda value: value["one-row-exact-reuse"]["counts"].__setitem__("unchanged_mtimes", 4),
            lambda value: value["one-row-pi-judge"]["counts"].__setitem__("correct", 0),
            lambda value: value["source-basic"]["counts"].__setitem__("credential_matches", 1),
        ):
            with self.subTest(mutation=mutation):
                mutated = copy.deepcopy(document)
                by_id = {case["id"]: case for case in mutated["cases"]}
                mutation(by_id)
                if "source-basic" not in by_id:
                    mutated["cases"] = list(by_id.values())
                with self.assertRaises(ValueError):
                    validate_acceptance_document(mutated)

        credential = self.load_manifest()
        credential["cases"][0]["command_template"] = "credential-value"
        with self.assertRaisesRegex(ValueError, "configured credential"):
            validate_acceptance_document(
                credential, credential_values=("credential-value",)
            )


class PaperBenchmarkWheelTests(unittest.TestCase):
    def test_isolated_wheel_uses_packaged_paper_resources_not_cwd_lookalikes(self) -> None:
        evidence = run_installed_product_proof(ROOT)
        self.assertEqual(evidence["paper_contract"], "packaged")
        self.assertEqual(evidence["paper_verification"], "model-free")
        self.assertEqual(
            (
                evidence["paper_dataset_count"],
                evidence["paper_scope_count"],
                evidence["paper_ablation_count"],
            ),
            (13, 16, 20),
        )
