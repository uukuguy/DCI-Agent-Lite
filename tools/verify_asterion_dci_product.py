#!/usr/bin/env python3
"""Validate and execute the model-free Asterion DCI product matrix."""

from __future__ import annotations

import argparse
import ast
import functools
import hashlib
import importlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from pathlib import PurePosixPath
from typing import cast
from urllib.parse import unquote, urlsplit


MATRIX_PATH = Path("assets/dci/product-parity.json")
ACCEPTANCE_PATH = Path("assets/dci/product-acceptance.json")
SCHEMA = "asterion.dci.product-parity/v1"
ACCEPTANCE_SCHEMA = "asterion.dci.product-acceptance/v1"
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
UNITTEST_PREFIX = ("uv", "run", "python", "-m", "unittest")
VALIDATE_ONLY_ARGV = (
    "python3",
    "tools/verify_asterion_dci_product.py",
    "--validate-only",
)
REQUIRED_PROVIDER_CASES = {
    "source-basic",
    "source-runtime-context",
    "asterion-basic",
    "asterion-runtime-context",
    "installed-pi-application",
    "one-row-pi-judge",
    "one-row-exact-reuse",
}
EXPECTED_ACCEPTANCE_ARTIFACTS = {
    "source-basic": {"state.json", "events.jsonl", "final.txt"},
    "source-runtime-context": {
        "state.json",
        "events.jsonl",
        "final.txt",
        "eval_result.json",
    },
    "asterion-basic": {"state.json", "events.jsonl", "final.txt"},
    "asterion-runtime-context": {
        "state.json",
        "events.jsonl",
        "final.txt",
        "eval_result.json",
    },
    "installed-pi-application": {"state.json", "events.jsonl", "final.txt"},
    "one-row-pi-judge": {
        "summary.json",
        "result.json",
        "eval_result.json",
        "events.jsonl",
        "protocol/attempt-0001.events.jsonl",
    },
    "one-row-exact-reuse": {
        "events.jsonl",
        "eval_result.json",
        "protocol/attempt-0001.events.jsonl",
    },
}
EXPECTED_ACCEPTANCE_COUNTS = {
    "source-basic": {"events", "protocol_attempts", "native_generations", "credential_matches"},
    "source-runtime-context": {"events", "protocol_attempts", "native_generations", "credential_matches"},
    "asterion-basic": {"events", "protocol_attempts", "native_generations", "credential_matches"},
    "asterion-runtime-context": {"events", "protocol_attempts", "native_generations", "credential_matches"},
    "installed-pi-application": {
        "events",
        "protocol_attempts",
        "native_generations",
        "body_free_projections",
        "credential_matches",
    },
    "one-row-pi-judge": {
        "total",
        "correct",
        "private_files",
        "protocol_attempts",
        "native_generations",
        "credential_matches",
    },
    "one-row-exact-reuse": {
        "total",
        "correct",
        "unchanged_hashes",
        "unchanged_mtimes",
        "protocol_attempts",
        "native_generations",
        "credential_matches",
    },
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
ALLOWED_TIERS = {"local", "model-free", "provider-backed"}
FORBIDDEN_TEXT = {"placeholder", "todo", "tbd", "unknown", "n/a"}
MATRIX_FIELDS = {"schema", "batch_inventory", "product_acceptance", "rows"}
INVENTORY_FIELDS = {"path", "sha256", "row_count"}
ACCEPTANCE_REFERENCE_FIELDS = {"path", "sha256", "case_count"}
ROW_FIELDS = {
    "id",
    "owner",
    "source_entry_points",
    "asterion_entry_points",
    "stable_semantics",
    "unsupported",
    "local_evidence",
    "provider_evidence",
}
EVIDENCE_FIELDS = {"id", "tier", "argv", "selectors"}
SHELL_METACHARACTERS = re.compile(r"[\n\r;&|`$<>]")
ENVIRONMENT_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
CASE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
ENVIRONMENT_NAME = re.compile(r"^[A-Z][A-Z0-9_]*$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
FILE_MODE = re.compile(r"^[0-7]{3}$")
PRIVATE_PATH = re.compile(r"/(?:private|Users|home)/")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?:api[_-]?key|token|secret|password)\s*[:=]\s*[^\s\"']+"
)
FORBIDDEN_BODY_TEXT = re.compile(
    r"(?i)(?:provider[_ -]?(?:request|response)|conversation|final[_ -]?answer|stderr)"
)
MATRIX_ONLY_TEST_PREFIXES = (
    "test_af250_h",
    "test_product_matrix_",
    "test_matrix_",
    "test_rows_",
    "test_provider_",
    "test_behavior_",
    "test_bash_",
    "test_default_executor_",
    "test_validate_only_",
)
_PRODUCT_SEMANTIC_SELECTOR_PREFIX = (
    "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests."
)
PRODUCT_SEMANTIC_SELECTORS = frozenset(
    {
        _PRODUCT_SEMANTIC_SELECTOR_PREFIX + name
        for name in (
            "test_af250_h002_batch_semantics_keep_counts_ndcg_exports_and_reuse",
            "test_af250_h002_bcplus_and_bright_export_transforms_match",
            "test_af250_h002_completed_native_runs_have_equal_stable_semantics",
            "test_af250_h002_configuration_precedence_and_effective_pi_argv_match",
            "test_af250_h002_failed_and_resumed_lifecycle_is_not_normalized_away",
            "test_af250_h002_judge_request_and_cache_invalidation_semantics_match",
            "test_af250_h002_run_normalizer_rejects_missing_or_malformed_evidence",
            "test_af250_h002_run_semantics_retain_typed_max_turns",
            "test_af250_h003_fresh_installed_product_runs_outside_repository",
        )
    }
)
LAUNCHER_RELATIVES = (
    "bcplus_eval/run_L3.sh",
    "bcplus_eval/run_bcplus_eval_openai.sh",
    "bright/run_bio.sh",
    "bright/run_earth_science.sh",
    "bright/run_economics.sh",
    "bright/run_robotics.sh",
    "qa/run_2wikimultihopqa_dev_sample50.sh",
    "qa/run_bamboogle_test_sample50.sh",
    "qa/run_hotpotqa_dev_sample50.sh",
    "qa/run_musique_dev_sample50.sh",
    "qa/run_nq_test_sample50.sh",
    "qa/run_triviaqa_test_sample50.sh",
)
_VERIFIED_DYNAMIC_SELECTORS: set[str] = set()
BATCH_EXTRA_SELECTORS = (
    "tests.test_climb_tools.Af240InventoryTests.test_af240_inventory_maps_complete_source_surface",
    "tests.test_asterion_dci_batch.AsterionDciBatchTests.test_exact_result_is_reused_without_native_or_judge_work",
    "tests.test_asterion_dci_metrics.AsterionDciMetricTests.test_normalization_matches_source_property_matrix",
    "tests.test_asterion_dci_export.AsterionDciExportTests.test_cli_failures_are_body_free_and_module_has_no_baseline_import",
    "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_batch_semantics_keep_counts_ndcg_exports_and_reuse",
    "tests.test_asterion_dci_product_parity.AsterionDciProductParityTests.test_af250_h002_bcplus_and_bright_export_transforms_match",
)
EXPECTED_FAKE_ANSWER = "PRIVATE-FIXTURE-ANSWER"
EXPECTED_FAKE_QUESTION = "PRIVATE-FIXTURE-QUESTION"


@dataclass(frozen=True)
class ProductAcceptanceSummary:
    """Body-free aggregate returned to operator-facing verification commands."""

    product_rows: tuple[int, int]
    delegated_inventory: tuple[int, int]
    launcher_pairs: tuple[int, int]
    batch_extras: tuple[int, int]
    bounded_acceptance: tuple[int, int]
    provider_backed_executed: int
    private_acceptance: tuple[int, int] | None
    row_statuses: tuple[tuple[str, str, int], ...] = ()


def load_product_matrix(root: Path) -> dict[str, object]:
    """Load the checked-in matrix without executing any evidence."""
    path = root / MATRIX_PATH
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise ValueError("product matrix must be an object")
    return cast(dict[str, object], document)


def _require_exact_fields(value: dict[str, object], expected: set[str], label: str) -> None:
    fields = set(value)
    if fields != expected:
        raise ValueError(f"unknown {label} fields: {sorted(fields - expected)}")


def _credential_values_from_environment() -> tuple[str, ...]:
    return tuple(
        value
        for name, value in os.environ.items()
        if value
        and not name.upper().endswith("_ENV")
        and any(
            token in name.upper()
            for token in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")
        )
    )


def _required_acceptance_credential_values(
    cases: tuple[dict[str, object], ...],
) -> tuple[str, ...]:
    """Resolve only credentials named by the acceptance cases, including indirection."""
    references: list[str] = []
    for case in cases:
        for name in cast(list[str], case["inherited_configuration"]):
            if (
                any(
                    token in name.upper()
                    for token in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")
                )
                and name not in references
            ):
                references.append(name)

    values: list[str] = []
    for name in references:
        if name.upper().endswith("_ENV"):
            target = os.environ.get(name)
            if not target:
                raise ValueError(
                    f"manifest-referenced credential indirection is not exported: {name}"
                )
            value = os.environ.get(target, "")
            if not value:
                raise ValueError(
                    f"manifest-referenced credential is not exported: {target}"
                )
        else:
            value = os.environ.get(name, "")
            if not value:
                raise ValueError(
                    f"manifest-referenced credential is not exported: {name}"
                )
        if value not in values:
            values.append(value)
    if not references:
        raise ValueError(
            "private acceptance manifest contains no credential references"
        )
    return tuple(values)


def validate_acceptance_document(
    document: object, *, credential_values: tuple[str, ...] = ()
) -> tuple[dict[str, object], ...]:
    """Validate the body-free record of bounded provider-backed acceptance."""
    if not isinstance(document, dict) or set(document) != {"schema", "cases"}:
        raise ValueError("acceptance manifest shape is invalid")
    if document["schema"] != ACCEPTANCE_SCHEMA:
        raise ValueError("acceptance manifest schema is invalid")
    cases = document["cases"]
    if not isinstance(cases, list):
        raise ValueError("acceptance manifest cases are invalid")
    ids = [case.get("id") for case in cases if isinstance(case, dict)]
    if set(ids) != REQUIRED_PROVIDER_CASES or len(ids) != len(REQUIRED_PROVIDER_CASES):
        raise ValueError("acceptance manifest cases are incomplete")
    encoded = json.dumps(document, sort_keys=True)
    if PRIVATE_PATH.search(encoded):
        raise ValueError("acceptance manifest contains an absolute private path")
    if SECRET_ASSIGNMENT.search(encoded):
        raise ValueError("acceptance manifest contains a plaintext credential")
    if FORBIDDEN_BODY_TEXT.search(encoded):
        raise ValueError("acceptance manifest contains a provider body reference")
    if any(value and value in encoded for value in credential_values):
        raise ValueError("acceptance manifest contains a configured credential value")

    validated: list[dict[str, object]] = []
    expected_fields = {
        "id",
        "command_template",
        "inherited_configuration",
        "exit_status",
        "structural_artifacts",
        "verdict",
        "counts",
        "timestamp",
    }
    for raw_case in cases:
        if not isinstance(raw_case, dict):
            raise ValueError("acceptance case must be an object")
        case = cast(dict[str, object], raw_case)
        _require_exact_fields(case, expected_fields, "acceptance case")
        command = case["command_template"]
        if not isinstance(command, str) or not command.strip():
            raise ValueError("acceptance command template is invalid")
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
            raise ValueError("acceptance inherited configuration is invalid")
        if case["exit_status"] != 0:
            raise ValueError("acceptance exit status is not successful")
        artifacts = case["structural_artifacts"]
        if not isinstance(artifacts, list) or not artifacts:
            raise ValueError("acceptance case has no structural artifacts")
        if not all(
            isinstance(item, dict)
            and set(item) == {"name", "mode", "sha256"}
            and isinstance(item["name"], str)
            and bool(item["name"])
            and not PurePosixPath(item["name"]).is_absolute()
            and ".." not in PurePosixPath(item["name"]).parts
            and isinstance(item["mode"], str)
            and bool(FILE_MODE.fullmatch(item["mode"]))
            and isinstance(item["sha256"], str)
            and bool(SHA256.fullmatch(item["sha256"]))
            for item in artifacts
        ):
            raise ValueError("acceptance structural artifact is invalid")
        artifact_names = {cast(str, item["name"]) for item in artifacts}
        if artifact_names != EXPECTED_ACCEPTANCE_ARTIFACTS[cast(str, case["id"])]:
            raise ValueError("acceptance structural artifact set is incomplete")
        verdict = case["verdict"]
        if verdict is not None and type(verdict) is not bool:
            raise ValueError("acceptance verdict type is invalid")
        if case["id"] == "one-row-pi-judge" and type(verdict) is not bool:
            raise ValueError("Judge verdict must be boolean")
        counts = case["counts"]
        if (
            not isinstance(counts, dict)
            or not counts
            or not all(
                isinstance(name, str)
                and bool(name)
                and type(value) is int
                and value >= 0
                for name, value in counts.items()
            )
        ):
            raise ValueError("acceptance counts are invalid")
        if set(counts) != EXPECTED_ACCEPTANCE_COUNTS[cast(str, case["id"])]:
            raise ValueError("acceptance count set is incomplete")
        if case["id"] not in {"one-row-pi-judge", "one-row-exact-reuse"} and (
            counts.get("protocol_attempts") != 1
            or counts.get("native_generations") != 1
        ):
            raise ValueError("acceptance run count is invalid")
        if case["id"] == "one-row-exact-reuse" and (
            counts.get("protocol_attempts") != 1
            or counts.get("native_generations") != 1
            or counts.get("unchanged_hashes") != 3
            or counts.get("unchanged_mtimes") != 3
        ):
            raise ValueError("exact reuse evidence is incomplete")
        if case["id"] == "one-row-pi-judge" and (
            counts.get("total") != 1
            or counts.get("correct") != 1
            or counts.get("private_files", 0) < 28
            or counts.get("protocol_attempts") != 1
            or counts.get("native_generations") != 1
        ):
            raise ValueError("Pi-plus-Judge evidence is incomplete")
        if counts.get("credential_matches", 0) != 0:
            raise ValueError("acceptance credential scan is not clean")
        timestamp = case["timestamp"]
        if not isinstance(timestamp, str) or not timestamp.endswith("Z"):
            raise ValueError("acceptance timestamp is invalid")
        try:
            parsed = datetime.fromisoformat(timestamp.removesuffix("Z") + "+00:00")
        except ValueError as error:
            raise ValueError("acceptance timestamp is invalid") from error
        if parsed.tzinfo is None:
            raise ValueError("acceptance timestamp is invalid")
        validated.append(case)
    return tuple(validated)


def _read_json_object(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"private {label} artifact is invalid") from error
    if not isinstance(value, dict):
        raise ValueError(f"private {label} artifact is invalid")
    return cast(dict[str, object], value)


def validate_acceptance_artifacts(
    acceptance_root: Path,
    cases: tuple[dict[str, object], ...],
    *,
    credential_values: tuple[str, ...] = (),
) -> int:
    """Recompute public structural claims against a caller-owned private root."""
    root = acceptance_root.resolve(strict=True)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("private acceptance root is invalid")
    indexed = {cast(str, case["id"]): case for case in cases}
    for case_id, case in indexed.items():
        case_root = root / case_id
        if not case_root.is_dir() or case_root.is_symlink():
            raise ValueError(f"private acceptance case is missing: {case_id}")
        artifact_names: set[str] = set()
        for artifact in cast(list[dict[str, object]], case["structural_artifacts"]):
            name = cast(str, artifact["name"])
            if name in artifact_names:
                raise ValueError("private acceptance artifact is duplicated")
            artifact_names.add(name)
            path = case_root / PurePosixPath(name)
            if path.is_symlink() or not path.is_file():
                raise ValueError(f"private acceptance artifact is missing: {case_id}")
            if not path.resolve().is_relative_to(case_root.resolve()):
                raise ValueError("private acceptance artifact escapes its case")
            mode = f"{path.stat().st_mode & 0o777:03o}"
            content = path.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if mode != artifact["mode"] or digest != artifact["sha256"]:
                raise ValueError(f"private acceptance artifact mismatch: {case_id}")
            if any(
                value and value.encode("utf-8") in content
                for value in credential_values
            ):
                raise ValueError("private acceptance artifact contains a credential")

        for private_path in case_root.rglob("*"):
            if private_path.is_symlink():
                raise ValueError("private acceptance evidence contains a symlink")
            if private_path.is_file():
                content = private_path.read_bytes()
                if any(
                    value and value.encode("utf-8") in content
                    for value in credential_values
                ):
                    raise ValueError("private acceptance evidence contains a credential")

        if "state.json" in artifact_names:
            state = _read_json_object(case_root / "state.json", "state")
            if state.get("status") != "completed" or not state.get("assistant_text"):
                raise ValueError(f"private acceptance state is incomplete: {case_id}")
            final = (case_root / "final.txt").read_text(encoding="utf-8").strip()
            if not final or final != str(state["assistant_text"]).strip():
                raise ValueError(f"private acceptance final is invalid: {case_id}")
            lines = (case_root / "events.jsonl").read_text(encoding="utf-8").splitlines()
            try:
                events = [json.loads(line) for line in lines if line]
            except json.JSONDecodeError as error:
                raise ValueError(f"private acceptance events are invalid: {case_id}") from error
            if not events or events[-1].get("type") != "agent_settled":
                raise ValueError(f"private acceptance events are incomplete: {case_id}")
            if cast(dict[str, object], case["counts"]).get("events") != len(events):
                raise ValueError(f"private acceptance event count mismatch: {case_id}")

        if "eval_result.json" in artifact_names:
            evaluation = _read_json_object(case_root / "eval_result.json", "evaluation")
            fingerprint = evaluation.get("judge_request_fingerprint")
            if evaluation.get("is_correct") is not True or not (
                isinstance(fingerprint, str) and SHA256.fullmatch(fingerprint)
            ):
                raise ValueError(f"private Judge evidence is invalid: {case_id}")

    judge_root = root / "one-row-pi-judge"
    private_tree = judge_root / "private-tree"
    expected_private_files = cast(
        dict[str, int], indexed["one-row-pi-judge"]["counts"]
    )["private_files"]
    if (
        not private_tree.is_dir()
        or sum(path.is_file() for path in private_tree.rglob("*"))
        != expected_private_files
    ):
        raise ValueError("private Pi-plus-Judge file inventory is incomplete")
    summary = _read_json_object(judge_root / "summary.json", "summary")
    summary_counts = summary.get("counts")
    result = _read_json_object(judge_root / "result.json", "result")
    if (
        not isinstance(summary_counts, dict)
        or summary_counts.get("total") != 1
        or summary_counts.get("correct") != 1
        or result.get("status") != "completed"
        or result.get("is_correct") is not True
    ):
        raise ValueError("private Pi-plus-Judge evidence is incomplete")

    reuse_root = root / "one-row-exact-reuse"
    for name in (
        "events.jsonl",
        "eval_result.json",
        "protocol/attempt-0001.events.jsonl",
    ):
        before = judge_root / name
        after = reuse_root / name
        if (
            hashlib.sha256(before.read_bytes()).hexdigest()
            != hashlib.sha256(after.read_bytes()).hexdigest()
            or before.stat().st_mtime_ns != after.stat().st_mtime_ns
        ):
            raise ValueError("private exact-reuse evidence changed")
    return len(cases)


def validate_acceptance_reference(root: Path, value: object) -> int:
    """Resolve the canonical acceptance manifest through its matrix digest binding."""
    if not isinstance(value, dict):
        raise ValueError("product acceptance reference must be an object")
    reference = cast(dict[str, object], value)
    _require_exact_fields(reference, ACCEPTANCE_REFERENCE_FIELDS, "product acceptance")
    if reference["path"] != ACCEPTANCE_PATH.as_posix():
        raise ValueError("product acceptance path is not canonical")
    path = root / ACCEPTANCE_PATH
    if not path.is_file():
        raise ValueError("product acceptance path does not exist")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if reference["sha256"] != digest:
        raise ValueError("product acceptance SHA-256 mismatch")
    document = json.loads(path.read_text(encoding="utf-8"))
    cases = validate_acceptance_document(
        document, credential_values=_credential_values_from_environment()
    )
    if reference["case_count"] != len(REQUIRED_PROVIDER_CASES) or len(cases) != len(
        REQUIRED_PROVIDER_CASES
    ):
        raise ValueError("product acceptance case count mismatch")
    return len(cases)


def _safe_repo_file(root: Path, value: object, label: str) -> str:
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise ValueError(f"{label} entry point must be a relative path")
    path = Path(value)
    if ".." in path.parts or not (root / path).is_file():
        raise ValueError(f"{label} entry point does not exist: {value}")
    return value


@functools.lru_cache(maxsize=None)
def _resolve_selector(root: Path, selector: str) -> bool:
    if selector in _VERIFIED_DYNAMIC_SELECTORS:
        return True
    parts = selector.split(".")
    if len(parts) == 4 and parts[0] == "tests":
        path = root / "tests" / f"{parts[1]}.py"
        if not path.is_file():
            return False
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == parts[2]:
                if any(
                    isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and child.name == parts[3]
                    for child in node.body
                ):
                    return True
    root_text = str(root)
    added_root = root_text not in sys.path
    if added_root:
        sys.path.insert(0, root_text)
    try:
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
    finally:
        if added_root:
            sys.path.remove(root_text)


@functools.lru_cache(maxsize=None)
def _resolve_dynamic_selectors(root: Path, selectors: tuple[str, ...]) -> bool:
    program = """
import importlib
import json
import sys
for selector in json.load(sys.stdin):
    module_name, class_name, method_name = selector.rsplit('.', 2)
    value = getattr(getattr(importlib.import_module(module_name), class_name), method_name)
    if not callable(value):
        raise SystemExit(1)
"""
    completed = subprocess.run(
        ["uv", "run", "python", "-c", program],
        cwd=root,
        input=json.dumps(selectors),
        text=True,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def _validate_argv(root: Path, value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(arg, str) and arg for arg in value):
        raise ValueError("unsafe argv: expected non-empty string array")
    argv = tuple(value)
    if Path(argv[0]).is_absolute():
        raise ValueError("unsafe absolute executable")
    if any(ENVIRONMENT_ASSIGNMENT.match(arg) for arg in argv):
        raise ValueError("unsafe environment assignment in argv")
    if any(SHELL_METACHARACTERS.search(arg) for arg in argv):
        raise ValueError("unsafe shell metacharacter in argv")
    if argv[: len(UNITTEST_PREFIX)] == UNITTEST_PREFIX and len(argv) > len(
        UNITTEST_PREFIX
    ):
        return argv
    if argv == VALIDATE_ONLY_ARGV:
        return argv
    if argv[:2] == ("bash", "-n"):
        paths = argv[2:]
        if not paths:
            raise ValueError("unsafe bash syntax argv")
        for raw_path in paths:
            path = Path(raw_path)
            if (
                raw_path.startswith(("-", "+"))
                or path.is_absolute()
                or ".." in path.parts
                or path.suffix != ".sh"
                or path.as_posix() != raw_path
                or not (root / path).is_file()
            ):
                raise ValueError("unsafe bash syntax argv")
        return argv
    if argv and argv[0] == "bash":
        raise ValueError("unsafe bash syntax argv")
    raise ValueError("argv shape is not allowlisted")


def validate_batch_inventory(root: Path, value: object) -> tuple[str, ...]:
    """Validate and resolve every digest-bound AF-240 delegated test selector."""

    if not isinstance(value, dict):
        raise ValueError("batch inventory reference must be an object")
    inventory = cast(dict[str, object], value)
    _require_exact_fields(inventory, INVENTORY_FIELDS, "batch inventory")
    if inventory["path"] != "assets/dci/batch-parity.json":
        raise ValueError("batch inventory path is not canonical")
    path = root / cast(str, inventory["path"])
    if not path.is_file():
        raise ValueError("batch inventory path does not exist")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if inventory["sha256"] != digest:
        raise ValueError("batch inventory SHA-256 mismatch")
    parsed = json.loads(path.read_text(encoding="utf-8"))
    rows = parsed.get("rows") if isinstance(parsed, dict) else None
    if inventory["row_count"] != 533 or not isinstance(rows, list) or len(rows) != 533:
        raise ValueError("batch inventory row count mismatch")
    selectors: list[str] = []
    for row in rows:
        values = row.get("current_verification_tests") if isinstance(row, dict) else None
        if (
            row.get("implementation_status") != "implemented"
            if isinstance(row, dict)
            else True
        ) or not isinstance(values, list) or len(values) != 1:
            raise ValueError("batch inventory selector is missing")
        selector = values[0]
        if not isinstance(selector, str) or not selector.startswith("tests."):
            raise ValueError("batch inventory selector is not executable")
        selectors.append(selector)
    if len(set(selectors)) != 533:
        raise ValueError("batch inventory selectors are not unique")
    unresolved = tuple(
        selector for selector in selectors if not _resolve_selector(root, selector)
    )
    if unresolved and not _resolve_dynamic_selectors(root, unresolved):
        raise ValueError("batch inventory selector is not executable")
    _VERIFIED_DYNAMIC_SELECTORS.update(unresolved)
    return tuple(selectors)


def validate_launcher_pairs(root: Path) -> tuple[tuple[str, str], ...]:
    """Require the exact twelve independent source/Asterion launcher pairs."""

    expected = {
        f"scripts/{relative}" for relative in LAUNCHER_RELATIVES
    }
    expected_targets = {
        f"scripts/asterion/{relative}" for relative in LAUNCHER_RELATIVES
    }
    actual = {
        path.relative_to(root).as_posix()
        for family in ("bcplus_eval", "qa", "bright")
        for path in (root / "scripts" / family).glob("run_*.sh")
    }
    actual_targets = {
        path.relative_to(root).as_posix()
        for family in ("bcplus_eval", "qa", "bright")
        for path in (root / "scripts" / "asterion" / family).glob("run_*.sh")
    }
    if actual != expected or actual_targets != expected_targets:
        raise ValueError("source/Asterion launcher pairs are not exact")
    return tuple(
        (f"scripts/{relative}", f"scripts/asterion/{relative}")
        for relative in LAUNCHER_RELATIVES
    )


def _nonempty_strings(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ValueError(f"{label} must be a non-empty string array")
    return cast(list[str], value)


def _validate_batch_evidence_link(
    rows: tuple[dict[str, object], ...] | list[dict[str, object]],
    inventory_selectors: tuple[str, ...],
) -> dict[str, object]:
    matches = [row for row in rows if row.get("id") == "batch-ir-analysis-and-exports"]
    if len(matches) != 1:
        raise ValueError("delegated inventory batch row is invalid")
    evidence_list = matches[0].get("local_evidence")
    if not isinstance(evidence_list, list) or len(evidence_list) != 1:
        raise ValueError("delegated inventory evidence is invalid")
    evidence = evidence_list[0]
    if not isinstance(evidence, dict):
        raise ValueError("delegated inventory evidence is invalid")
    selectors = evidence.get("selectors")
    argv = evidence.get("argv")
    expected = (*inventory_selectors, *BATCH_EXTRA_SELECTORS)
    if (
        not isinstance(selectors, list)
        or tuple(selectors) != expected
        or len(set(selectors)) != len(selectors)
        or not isinstance(argv, list)
        or tuple(argv) != (*UNITTEST_PREFIX, *expected)
    ):
        raise ValueError("delegated inventory evidence is not exact")
    launcher_selectors = tuple(
        selector
        for selector in inventory_selectors
        if selector.startswith(
            "tests.test_asterion_dci_batch_launchers.AsterionDciBatchLauncherTests."
        )
        and "_launcher_" in selector
    )
    if len(launcher_selectors) != 12 or len(set(launcher_selectors)) != 12:
        raise ValueError("delegated inventory launcher selectors are not exact")
    return evidence


def validate_product_matrix(
    root: Path, document: object
) -> tuple[dict[str, object], ...]:
    """Fail closed on malformed, unsafe, or unresolvable matrix evidence."""
    if not isinstance(document, dict):
        raise ValueError("product matrix must be an object")
    matrix = cast(dict[str, object], document)
    _require_exact_fields(matrix, MATRIX_FIELDS, "matrix")
    if matrix["schema"] != SCHEMA:
        raise ValueError("unsupported product matrix schema")
    inventory_selectors = validate_batch_inventory(root, matrix["batch_inventory"])
    validate_acceptance_reference(root, matrix["product_acceptance"])
    validate_launcher_pairs(root)
    raw_rows = matrix["rows"]
    if not isinstance(raw_rows, list):
        raise ValueError("product matrix rows must be an array")

    preliminary_ids = [row.get("id") for row in raw_rows if isinstance(row, dict)]
    if len(preliminary_ids) != len(set(preliminary_ids)):
        raise ValueError("duplicate product row id")

    rows: list[dict[str, object]] = []
    row_ids: list[str] = []
    evidence_ids: set[str] = set()
    provider_case_ids: list[str] = []
    for raw_row in raw_rows:
        if not isinstance(raw_row, dict):
            raise ValueError("product row must be an object")
        row = cast(dict[str, object], raw_row)
        _require_exact_fields(row, ROW_FIELDS, "product row")
        row_id = row["id"]
        if not isinstance(row_id, str) or row_id not in REQUIRED_PRODUCT_ROWS:
            raise ValueError("invalid product row id")
        row_ids.append(row_id)
        owner = row["owner"]
        if owner != REQUIRED_PRODUCT_OWNERS[row_id]:
            raise ValueError(f"invalid product owner: {owner!r}")
        if row["unsupported"] is not False:
            raise ValueError(f"unsupported product row: {row_id}")
        for field in ("source_entry_points", "asterion_entry_points"):
            paths = _nonempty_strings(row[field], field)
            row[field] = [_safe_repo_file(root, path, field) for path in paths]
        semantics = _nonempty_strings(row["stable_semantics"], "stable semantics")
        if any(token in item.casefold() for item in semantics for token in FORBIDDEN_TEXT):
            raise ValueError(f"placeholder text in product row: {row_id}")

        evidence_list = row["local_evidence"]
        if not isinstance(evidence_list, list) or not evidence_list:
            raise ValueError(f"local evidence must be non-empty: {row_id}")
        for raw_evidence in evidence_list:
            if not isinstance(raw_evidence, dict):
                raise ValueError("local evidence must be an object")
            evidence = cast(dict[str, object], raw_evidence)
            _require_exact_fields(evidence, EVIDENCE_FIELDS, "local evidence")
            evidence_id = evidence["id"]
            if not isinstance(evidence_id, str) or not CASE_ID.fullmatch(evidence_id):
                raise ValueError("local evidence id is invalid")
            if evidence_id in evidence_ids:
                raise ValueError(f"duplicate evidence id: {evidence_id}")
            evidence_ids.add(evidence_id)
            tier = evidence["tier"]
            if tier not in ALLOWED_TIERS:
                raise ValueError(f"invalid evidence tier: {tier}")
            if tier == "provider-backed":
                raise ValueError("provider-backed command is forbidden in local_evidence")
            argv = _validate_argv(root, evidence["argv"])
            selectors = _nonempty_strings(evidence["selectors"], "selectors")
            if argv[: len(UNITTEST_PREFIX)] == UNITTEST_PREFIX and tuple(
                selectors
            ) != argv[len(UNITTEST_PREFIX) :]:
                raise ValueError("selectors do not match unittest argv")
            if any(
                selector.startswith("tests.test_asterion_dci_product_parity")
                and selector.rsplit(".", 1)[-1].startswith(MATRIX_ONLY_TEST_PREFIXES)
                and selector not in PRODUCT_SEMANTIC_SELECTORS
                for selector in selectors
            ):
                raise ValueError("matrix governance selector cannot prove product behavior")
            if not all(
                selector.startswith("tests.")
                and (
                    selector in _VERIFIED_DYNAMIC_SELECTORS
                    or _resolve_selector(root, selector)
                )
                for selector in selectors
            ):
                raise ValueError("selectors must resolve to executable tests")
        provider_cases = row["provider_evidence"]
        if not isinstance(provider_cases, list) or not all(
            isinstance(case_id, str) and CASE_ID.fullmatch(case_id)
            for case_id in provider_cases
        ):
            raise ValueError("provider evidence must be a body-free case id list")
        provider_case_ids.extend(provider_cases)
        rows.append(row)

    if len(row_ids) != len(set(row_ids)):
        raise ValueError("duplicate product row id")
    if set(row_ids) != REQUIRED_PRODUCT_ROWS or len(row_ids) != len(REQUIRED_PRODUCT_ROWS):
        raise ValueError("product matrix must contain exactly the required rows")
    if (
        len(provider_case_ids) != len(set(provider_case_ids))
        or set(provider_case_ids) != REQUIRED_PROVIDER_CASES
    ):
        raise ValueError("provider evidence must contain each required case exactly once")
    _validate_batch_evidence_link(rows, inventory_selectors)
    return tuple(rows)


def run_local_evidence(
    root: Path, rows: tuple[dict[str, object], ...]
) -> dict[str, object]:
    """Run only validated local/model-free argv and return body-free statuses."""
    for row in rows:
        for evidence in cast(list[dict[str, object]], row["local_evidence"]):
            _validate_argv(root, evidence.get("argv"))
    matrix = load_product_matrix(root)
    inventory = matrix["batch_inventory"]
    delegated = validate_batch_inventory(root, inventory)
    accepted = validate_acceptance_reference(root, matrix["product_acceptance"])
    _validate_batch_evidence_link(rows, delegated)
    results: list[dict[str, object]] = []
    batch_passed = False
    for row in rows:
        statuses: list[int] = []
        for evidence in cast(list[dict[str, object]], row["local_evidence"]):
            tier = evidence.get("tier")
            if tier == "provider-backed":
                continue
            if tier not in {"local", "model-free"}:
                raise ValueError(f"invalid evidence tier: {tier}")
            argv = _validate_argv(root, evidence.get("argv"))
            completed = subprocess.run(
                argv,
                cwd=root,
                shell=False,
                text=True,
                capture_output=True,
                check=False,
            )
            statuses.append(completed.returncode)
        results.append(
            {
                "id": row["id"],
                "status": "PASS" if statuses and all(code == 0 for code in statuses) else "FAIL",
                "exit_status": max(statuses, default=1),
            }
        )
        if row["id"] == "batch-ir-analysis-and-exports":
            batch_passed = bool(statuses) and all(code == 0 for code in statuses)
    launchers = validate_launcher_pairs(root)
    return {
        "rows": results,
        "provider_backed_executed": 0,
        "bounded_acceptance": f"{accepted}/{len(REQUIRED_PROVIDER_CASES)}",
        "delegated_inventory": f"{len(delegated) if batch_passed else 0}/533",
        "launcher_pairs": f"{len(launchers) if batch_passed else 0}/12",
        "batch_extra_selectors": f"{len(BATCH_EXTRA_SELECTORS) if batch_passed else 0}/6",
    }


def verify_product_acceptance(
    root: Path, *, acceptance_root: Path | None = None
) -> ProductAcceptanceSummary:
    """Run the complete model-free product proof and return typed aggregate counts."""

    canonical_root = Path(root).resolve()
    matrix = load_product_matrix(canonical_root)
    rows = validate_product_matrix(canonical_root, matrix)
    private_acceptance = None
    if acceptance_root is not None:
        private_acceptance = validate_private_acceptance(
            canonical_root, acceptance_root
        )
    result = run_local_evidence(canonical_root, rows)
    row_statuses = tuple(
        (
            cast(str, row["id"]),
            cast(str, row["status"]),
            cast(int, row["exit_status"]),
        )
        for row in cast(list[dict[str, object]], result["rows"])
    )
    return ProductAcceptanceSummary(
        product_rows=(
            sum(status == "PASS" for _, status, _ in row_statuses),
            len(rows),
        ),
        delegated_inventory=_fraction(cast(str, result["delegated_inventory"])),
        launcher_pairs=_fraction(cast(str, result["launcher_pairs"])),
        batch_extras=_fraction(cast(str, result["batch_extra_selectors"])),
        bounded_acceptance=_fraction(cast(str, result["bounded_acceptance"])),
        provider_backed_executed=cast(int, result["provider_backed_executed"]),
        private_acceptance=private_acceptance,
        row_statuses=row_statuses,
    )


def validate_private_acceptance(
    root: Path, acceptance_root: Path
) -> tuple[int, int]:
    """Validate retained provider evidence without running local product rows."""

    canonical_root = Path(root).resolve()
    manifest = json.loads(
        (canonical_root / ACCEPTANCE_PATH).read_text(encoding="utf-8")
    )
    unchecked_cases = validate_acceptance_document(manifest)
    credential_values = _required_acceptance_credential_values(unchecked_cases)
    cases = validate_acceptance_document(
        manifest, credential_values=credential_values
    )
    verified = validate_acceptance_artifacts(
        acceptance_root,
        cases,
        credential_values=credential_values,
    )
    return verified, len(REQUIRED_PROVIDER_CASES)


def _fraction(value: str) -> tuple[int, int]:
    try:
        actual, expected = value.split("/", 1)
        parsed = (int(actual), int(expected))
    except (TypeError, ValueError):
        raise ValueError("product acceptance count is invalid") from None
    if min(parsed) < 0:
        raise ValueError("product acceptance count is invalid")
    return parsed


_FAKE_NODE = r'''#!/usr/bin/env python3
import json
import sys

if sys.argv[1:] == ["--version"]:
    print("v20.0.0")
    raise SystemExit(0)
for line in sys.stdin:
    request = json.loads(line)
    request_id = request.get("id")
    if request.get("type") == "get_state":
        print(json.dumps({
            "type": "response", "id": request_id, "success": True,
            "data": {"isStreaming": False, "isCompacting": False,
                     "messageCount": 0, "pendingMessageCount": 0},
        }), flush=True)
    elif request.get("type") == "prompt":
        print(json.dumps({"type": "response", "id": request_id, "success": True}), flush=True)
        print(json.dumps({"type": "agent_start"}), flush=True)
        print(json.dumps({"type": "message_update", "assistantMessageEvent": {
            "type": "text_delta", "delta": "PRIVATE-FIXTURE-ANSWER"}}), flush=True)
        print(json.dumps({"type": "agent_settled"}), flush=True)
'''


def _checked_run(
    argv: list[str], *, cwd: Path, environment: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        argv,
        cwd=cwd,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("installed product proof command failed")
    return completed


def _resolve_installed_artifact(
    output_root: Path, run_directory: Path, uri: object, expected_name: str
) -> Path:
    if not isinstance(uri, str) or not uri:
        raise RuntimeError("installed product proof artifact URI is invalid")
    parsed = urlsplit(uri)
    decoded = unquote(parsed.path)
    path = PurePosixPath(decoded)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or decoded != expected_name
        or path.is_absolute()
        or ".." in path.parts
        or "\\" in decoded
    ):
        raise RuntimeError("installed product proof artifact URI is invalid")
    candidate = run_directory / expected_name
    try:
        resolved = candidate.resolve(strict=True)
        root = output_root.resolve(strict=True)
    except OSError as error:
        raise RuntimeError("installed product proof artifact is missing") from error
    if candidate.is_symlink() or not resolved.is_file() or not resolved.is_relative_to(root):
        raise RuntimeError("installed product proof artifact path is invalid")
    return resolved


def validate_installed_application_artifacts(
    output_root: Path, payload: object, serialized_output: str
) -> dict[str, object]:
    """Resolve installed projection references and return body-free proof only."""

    if not isinstance(payload, dict):
        raise RuntimeError("installed product proof projection is invalid")
    artifacts = payload.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 1:
        raise RuntimeError("installed product proof projection is invalid")
    projected = artifacts[0]
    value = projected.get("value") if isinstance(projected, dict) else None
    if not isinstance(value, dict):
        raise RuntimeError("installed product proof projection is invalid")
    states = tuple(output_root.rglob("state.json"))
    if len(states) != 1:
        raise RuntimeError("installed product proof native state is invalid")
    run_directory = states[0].parent
    state_path = _resolve_installed_artifact(
        output_root, run_directory, value.get("state_artifact_uri"), "state.json"
    )
    if state_path != states[0].resolve():
        raise RuntimeError("installed product proof native artifact is mismatched")
    final_path = _resolve_installed_artifact(
        output_root, run_directory, value.get("answer_artifact_uri"), "final.txt"
    )
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        final_text = final_path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError, ValueError) as error:
        raise RuntimeError("installed product proof artifact is invalid") from error
    expected_options = {
        "provider": "fixture-provider",
        "model": "fixture-model",
        "tools": "read,bash",
        "runtime_context_level": "level3",
        "thinking_level": "high",
    }
    if (
        not isinstance(state, dict)
        or state.get("status") != "completed"
        or state.get("assistant_text") != EXPECTED_FAKE_ANSWER
        or final_text != EXPECTED_FAKE_ANSWER
        or any(state.get(name) != expected for name, expected in expected_options.items())
    ):
        raise RuntimeError("installed product proof artifact state is invalid")
    if any(
        secret in serialized_output
        for secret in (EXPECTED_FAKE_QUESTION, EXPECTED_FAKE_ANSWER)
    ):
        raise RuntimeError("installed product proof output is not body-free")
    return {
        "installed_application": "completed",
        "answer_artifact_uri": "final.txt",
        "native_artifact_uri": "state.json",
        "body_free": True,
        "runtime_options": expected_options,
    }


def run_installed_product_proof(root: Path) -> dict[str, object]:
    """Build, isolate, and execute the installed Pi-default DCI product model-free."""

    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_root = Path(temporary_directory).resolve()
        dist = temporary_root / "dist"
        outside = temporary_root / "outside"
        venv = temporary_root / "venv"
        fake_bin = temporary_root / "fake-bin"
        pi_package = temporary_root / "fake-pi" / "packages" / "coding-agent"
        pi_agent = temporary_root / "fake-pi" / ".pi" / "agent"
        output_root = temporary_root / "native-runs"
        for directory in (outside, fake_bin, pi_package / "dist", pi_agent):
            directory.mkdir(parents=True, exist_ok=True)
        (pi_package / "dist" / "cli.js").write_text("fixture\n", encoding="utf-8")
        fake_node = fake_bin / "node"
        fake_node.write_text(_FAKE_NODE, encoding="utf-8")
        fake_node.chmod(0o755)

        build_environment = os.environ.copy()
        build_environment.pop("PYTHONPATH", None)
        _checked_run(
            ["uv", "build", "--package", "asterion", "--wheel", "--out-dir", str(dist)],
            cwd=root,
            environment=build_environment,
        )
        wheels = tuple(dist.glob("*.whl"))
        if len(wheels) != 1:
            raise RuntimeError("installed product proof wheel count is invalid")
        _checked_run(
            ["uv", "venv", "--python", sys.executable, str(venv)],
            cwd=outside,
            environment=build_environment,
        )
        python = venv / "bin" / "python"
        _checked_run(
            ["uv", "pip", "install", "--python", str(python), str(wheels[0])],
            cwd=outside,
            environment=build_environment,
        )

        environment = build_environment | {
            "PATH": os.pathsep.join((str(fake_bin), str(venv / "bin"), build_environment.get("PATH", ""))),
            "DCI_PI_DIR": str(temporary_root / "fake-pi"),
            "DCI_PROVIDER": "fixture-provider",
            "DCI_MODEL": "fixture-model",
            "DCI_TOOLS": "read,bash",
            "DCI_RUNTIME_CONTEXT_LEVEL": "level3",
            "DCI_PI_THINKING_LEVEL": "high",
            "ASTERION_RUNTIME_CWD": str(outside),
            "ASTERION_DCI_OUTPUT_ROOT": str(output_root),
        }
        probe = _checked_run(
            [
                str(python), "-I", "-c",
                "from importlib.util import find_spec; "
                "from asterion.dci.cli import _load_batch_profiles; "
                "assert find_spec('dci') is None; print(len(_load_batch_profiles()))",
            ],
            cwd=outside,
            environment=environment,
        )
        help_result = _checked_run(
            [str(venv / "bin" / "asterion-dci"), "--help"],
            cwd=outside,
            environment=environment,
        )
        list_result = _checked_run(
            [str(venv / "bin" / "asterion"), "list"],
            cwd=outside,
            environment=environment,
        )
        application = _checked_run(
            [
                str(venv / "bin" / "asterion"), "run",
                "--provider", "dci-agent-lite",
                "--runtime", "pi.reference",
                "--application", "dci.research-capability@1.0.0",
                "--run-id", "installed-fixture",
                "--input", EXPECTED_FAKE_QUESTION,
            ],
            cwd=outside,
            environment=environment,
        )
        payload = json.loads(application.stdout)
        serialized = application.stdout + application.stderr
        artifact_evidence = validate_installed_application_artifacts(
            output_root, payload, serialized
        )
        return {
            "dci_importable": False,
            "profiles": int(probe.stdout.strip()),
            "asterion_dci_help": help_result.returncode,
            "asterion_list": list_result.returncode,
            **artifact_evidence,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--acceptance-root", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    rows = validate_product_matrix(root, load_product_matrix(root))
    if args.validate_only:
        if args.acceptance_root is not None:
            actual, expected = validate_private_acceptance(root, args.acceptance_root)
            print(f"private-acceptance {actual}/{expected}")
            return 0 if actual == expected else 1
        for row in rows:
            print(f"{row['id']} VALID")
        return 0
    summary = verify_product_acceptance(root, acceptance_root=args.acceptance_root)
    if summary.private_acceptance is not None:
        print(f"private-acceptance {summary.private_acceptance[0]}/{summary.private_acceptance[1]}")
    for row_id, status, exit_status in summary.row_statuses:
        print(f"{row_id} {status} exit={exit_status}")
    print(f"delegated-inventory {summary.delegated_inventory[0]}/{summary.delegated_inventory[1]}")
    print(f"launcher-pairs {summary.launcher_pairs[0]}/{summary.launcher_pairs[1]}")
    print(f"batch-extra-selectors {summary.batch_extras[0]}/{summary.batch_extras[1]}")
    print(f"provider-backed-executed {summary.provider_backed_executed}")
    print(f"bounded-acceptance {summary.bounded_acceptance[0]}/{summary.bounded_acceptance[1]}")
    return 0 if summary.product_rows[0] == summary.product_rows[1] else 1


if __name__ == "__main__":
    raise SystemExit(main())
