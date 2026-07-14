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
from pathlib import Path
from typing import cast


MATRIX_PATH = Path("assets/dci/product-parity.json")
SCHEMA = "asterion.dci.product-parity/v1"
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
MATRIX_FIELDS = {"schema", "batch_inventory", "rows"}
INVENTORY_FIELDS = {"path", "sha256", "row_count"}
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
    validate_batch_inventory(root, matrix["batch_inventory"])
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
    return tuple(rows)


def run_local_evidence(
    root: Path, rows: tuple[dict[str, object], ...]
) -> dict[str, object]:
    """Run only validated local/model-free argv and return body-free statuses."""
    results: list[dict[str, object]] = []
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
    inventory = load_product_matrix(root)["batch_inventory"]
    delegated = validate_batch_inventory(root, inventory)
    launchers = validate_launcher_pairs(root)
    return {
        "rows": results,
        "provider_backed_executed": 0,
        "delegated_inventory": f"{len(delegated)}/533",
        "launcher_pairs": f"{len(launchers)}/12",
    }


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
                "--input", "PRIVATE-FIXTURE-QUESTION",
            ],
            cwd=outside,
            environment=environment,
        )
        payload = json.loads(application.stdout)
        artifact = payload["artifacts"][0]["value"]
        states = tuple(output_root.rglob("state.json"))
        if len(states) != 1:
            raise RuntimeError("installed product proof native state is invalid")
        state = json.loads(states[0].read_text(encoding="utf-8"))
        serialized = application.stdout + application.stderr
        return {
            "dci_importable": False,
            "profiles": int(probe.stdout.strip()),
            "asterion_dci_help": help_result.returncode,
            "asterion_list": list_result.returncode,
            "installed_application": state["status"],
            "answer_artifact_uri": artifact["answer_artifact_uri"],
            "native_artifact_uri": artifact["state_artifact_uri"],
            "body_free": not any(
                secret in serialized
                for secret in ("PRIVATE-FIXTURE-QUESTION", "PRIVATE-FIXTURE-ANSWER")
            ),
            "runtime_options": {
                name: state[name]
                for name in (
                    "provider", "model", "tools", "runtime_context_level", "thinking_level"
                )
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    rows = validate_product_matrix(root, load_product_matrix(root))
    if args.validate_only:
        for row in rows:
            print(f"{row['id']} VALID")
        return 0
    result = run_local_evidence(root, rows)
    for row in cast(list[dict[str, object]], result["rows"]):
        print(f"{row['id']} {row['status']} exit={row['exit_status']}")
    print(f"delegated-inventory {result['delegated_inventory']}")
    print(f"launcher-pairs {result['launcher_pairs']}")
    print(f"provider-backed-executed {result['provider_backed_executed']}")
    return 0 if all(row["status"] == "PASS" for row in result["rows"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
