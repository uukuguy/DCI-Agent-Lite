from __future__ import annotations

import csv
import ast
import copy
import functools
import hashlib
import importlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


AF240_SOURCE_FILES = (
    "scripts/bcplus_eval/run_bcplus_eval.py",
    "scripts/bcplus_eval/extract_bcplus_qa.py",
    "src/dci/benchmark/export_bc_plus_docs.py",
    "src/dci/benchmark/export_bright_docs.py",
)
AF240_OWNERS = {
    "asterion.dci.analysis",
    "asterion.dci.artifacts",
    "asterion.dci.benchmark",
    "asterion.dci.cli",
    "asterion.dci.config",
    "asterion.dci.datasets",
    "asterion.dci.evaluation",
    "asterion.dci.effective_config",
    "asterion.dci.export",
    "asterion.dci.judge",
    "asterion.dci.metrics",
    "asterion.dci.run",
    "asterion.dci.resources.batch-profiles.json",
    "scripts.asterion",
}
AF240_FORBIDDEN = {"placeholder", "tbd", "todo", "unsupported", "unknown", "n/a"}
AF240_READINESS_TESTS = {
    "AF-240-H-001": (
        "test_af240_h001_dataset_mapping_readiness",
        "test_af240_h001_prompt_mapping_readiness",
        "test_af240_h001_retrieval_mapping_readiness",
        "test_af240_h001_ir_metric_mapping_readiness",
    ),
    "AF-240-H-002": (
        "test_af240_h002_nested_coordinator_mapping_readiness",
        "test_af240_h002_durable_query_mapping_readiness",
        "test_af240_h002_reuse_mapping_readiness",
        "test_af240_h002_cancellation_mapping_readiness",
    ),
    "AF-240-H-003": (
        "test_af240_h003_judge_mapping_readiness",
        "test_af240_h003_aggregate_metric_mapping_readiness",
        "test_af240_h003_analysis_mapping_readiness",
        "test_af240_h003_figure_mapping_readiness",
    ),
    "AF-240-H-004": (
        "test_af240_h004_extractor_mapping_readiness",
        "test_af240_h004_export_mapping_readiness",
        "test_af240_h004_launcher_mapping_readiness",
        "test_af240_h004_installed_resource_mapping_readiness",
    ),
}
AF240_FUTURE_TEST_TARGETS = {
    "AF-240 Task 1": ("tests/test_asterion_dci_datasets.py", "AsterionDciDatasetTests"),
    "AF-240 Task 2": ("tests/test_asterion_dci_evaluation.py", "AsterionDciEvaluationTests"),
    "AF-240 Task 3": ("tests/test_asterion_dci_batch.py", "AsterionDciBatchTests"),
    "AF-240 Task 4": ("tests/test_asterion_dci_analysis.py", "AsterionDciAnalysisTests"),
    "AF-240 Task 5": ("tests/test_asterion_dci_export.py", "AsterionDciExportTests"),
    "AF-240 Task 6": (
        "tests/test_asterion_dci_batch_launchers.py",
        "AsterionDciBatchLauncherTests",
    ),
}
AF250_MATRIX_TESTS = {
    "AF-250-H-001": (
        "test_af250_h001_exact_product_row_surface",
        "test_af250_h001_source_entry_points_exist",
        "test_af250_h001_asterion_entry_points_exist",
        "test_af250_h001_local_selectors_resolve",
    ),
    "AF-250-H-002": (
        "test_af250_h002_rows_define_stable_semantics",
        "test_af250_h002_products_keep_distinct_entry_points",
        "test_af250_h002_batch_row_delegates_to_digest_bound_inventory",
        "test_af250_h002_matrix_contains_no_placeholder_text",
    ),
    "AF-250-H-003": (
        "test_af250_h003_installed_rows_are_explicit",
        "test_af250_h003_wheel_row_names_distribution_boundaries",
        "test_af250_h003_application_row_names_bundled_assembly",
        "test_af250_h003_installed_evidence_is_model_free",
    ),
    "AF-250-H-004": (
        "test_af250_h004_all_rows_are_supported",
        "test_af250_h004_provider_cases_are_body_free_ids",
        "test_af250_h004_local_executor_never_runs_provider_cases",
        "test_af250_h004_matrix_schema_and_inventory_are_finalized",
    ),
    "AF-250-H-005": (
        "test_af250_h005_manifest_is_canonical_and_digest_bound",
        "test_af250_h005_all_seven_provider_cases_are_successful",
        "test_af250_h005_manifest_rejects_bodies_credentials_and_private_paths",
        "test_af250_h005_private_acceptance_recomputes_artifacts_and_semantics",
    ),
}


def _shell_if_branch_bodies(script: str, hypothesis_id: str) -> list[str]:
    return re.findall(
        rf'(?:if|elif) \[ "\$1" = "{re.escape(hypothesis_id)}" \]; then\n'
        r"(.*?)(?=\nelif \[ \"\$1\"|\nfi)",
        script,
        re.S,
    )


def _shell_case_branch(script: str, hypothesis_id: str) -> str:
    match = re.search(
        rf"^    {re.escape(hypothesis_id)}\)\n(.*?)^        ;;$",
        script,
        re.M | re.S,
    )
    if match is None:
        raise AssertionError(f"missing case branch for {hypothesis_id}")
    return match.group(1)


def _af240_source_functions(path: str) -> set[str]:
    tree = ast.parse((REPO_ROOT / path).read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _resolve_test_name(name: str) -> bool:
    parts = name.split(".")
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


def _resolve_current_owner(owner: str, symbol: str) -> bool:
    try:
        value: object = importlib.import_module(owner)
    except ModuleNotFoundError:
        return False
    try:
        for part in symbol.split("."):
            value = getattr(value, part)
    except AttributeError:
        return False
    return value is not None


def _af240_behavior_slug(row: dict[str, object]) -> str:
    value = f"{row['source_path']}__{row['source_kind']}__{row['source_name']}"
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", value.casefold())).strip("_")


def _af240_source_flags(path: str) -> set[str]:
    tree = ast.parse((REPO_ROOT / path).read_text(encoding="utf-8"))
    flags: set[str] = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
        ):
            continue
        flags.update(
            arg.value
            for arg in node.args
            if isinstance(arg, ast.Constant)
            and isinstance(arg.value, str)
            and arg.value.startswith("--")
        )
    return flags


@functools.cache
def _af240_metric_paths_from_source() -> frozenset[str]:
    """Extract emitted numeric/boolean JSONPaths from representative source schemas.

    The source functions build the fixtures; this extractor only supplies values that
    make every explicit list and dynamic tool container non-empty. AST keys are used
    as an independent guard that every emitted leaf name originates in source code.
    """
    source = importlib.import_module("scripts.bcplus_eval.run_bcplus_eval")
    ast_keys: set[str] = set()
    for source_path in (
        REPO_ROOT / "scripts/bcplus_eval/run_bcplus_eval.py",
        REPO_ROOT / "src/dci/benchmark/judge.py",
    ):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        ast_keys.update(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
    with tempfile.TemporaryDirectory() as temp_dir:
        query_dir = Path(temp_dir)
        state = {
            "status": "completed",
            "error": None,
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:00:02+00:00",
            "event_count": 3,
            "turn_count": 1,
            "conversation_features": {},
            "messages": [
                {
                    "event": "message_end",
                    "message": {
                        "role": "assistant",
                        "usage": {
                            "input": 11,
                            "output": 7,
                            "cacheRead": 3,
                            "cacheWrite": 2,
                            "totalTokens": 23,
                            "cost": {
                                "input": 0.01,
                                "output": 0.02,
                                "cacheRead": 0.001,
                                "cacheWrite": 0.002,
                                "total": 0.033,
                            },
                        },
                    },
                }
            ],
            "tool_calls": [
                {
                    "event": "tool_execution_start",
                    "toolCallId": "call-1",
                    "toolName": "fixture_tool",
                    "recorded_at": "2026-01-01T00:00:00+00:00",
                },
                {
                    "event": "tool_execution_end",
                    "toolCallId": "call-1",
                    "toolName": "fixture_tool",
                    "recorded_at": "2026-01-01T00:00:01+00:00",
                    "isError": False,
                },
            ],
        }
        (query_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
        (query_dir / "latest_model_context.json").write_text(
            json.dumps({"request_count": 1}), encoding="utf-8"
        )
        (query_dir / "final.txt").write_text("fixture answer", encoding="utf-8")
        for name in ("stderr.txt", "launcher_stdout.txt", "launcher_stderr.txt"):
            (query_dir / name).write_text("", encoding="utf-8")
        judge_result = {
            "is_correct": True,
            "reason": "fixture",
            "usage": {
                "input_tokens": 5,
                "output_tokens": 2,
                "total_tokens": 7,
                "input_tokens_details": {"cached_tokens": 1},
            },
            "cost_estimate_usd": {
                "input_cost": 0.01,
                "cached_input_cost": 0.001,
                "output_cost": 0.02,
                "total_cost": 0.031,
            },
        }
        row = {
            "query_id": "fixture-1",
            "query": "fixture question",
            "answer": "fixture answer",
            "gold_docs": ["doc-1"],
        }
        result = source.gather_query_metrics(
            row=row,
            query_dir=query_dir,
            launcher_returncode=0,
            launcher_started_at="2026-01-01T00:00:00+00:00",
            launcher_finished_at="2026-01-01T00:00:03+00:00",
            judge_result=judge_result,
            ndcg_at_10=1.0,
        )
    incorrect = copy.deepcopy(result)
    incorrect.update(query_id="fixture-2", is_correct=False)
    incorrect["judge_result"]["is_correct"] = False
    rows = [row, {**row, "query_id": "fixture-2"}]
    results = [result, incorrect]
    summary = source.aggregate_results(results)
    analysis = source.compute_detailed_analysis(
        results=results, rows=rows, summary=summary
    )

    dynamic_parents = {
        "tool_metrics.by_tool",
        "analysis.tool_summary",
        "analysis.per_query_metrics[*].tool_counts",
        "analysis.per_query_metrics[*].tool_durations",
    }
    paths: set[str] = set()

    def visit(value: object, path: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if path == "" and key in {"judge_result", "conversation_features"}:
                    continue
                rendered = "*" if path in dynamic_parents else str(key)
                visit(child, f"{path}.{rendered}" if path else rendered)
        elif isinstance(value, list):
            for child in value:
                visit(child, f"{path}[*]")
        elif isinstance(value, (bool, int, float)):
            paths.add(path)

    visit(result, "")
    visit(summary, "summary")
    visit(analysis, "analysis")
    for path in paths:
        leaf = path.rsplit(".", 1)[-1].replace("[*]", "")
        if leaf != "*" and leaf not in ast_keys:
            raise AssertionError(f"metric leaf is not emitted by source AST: {path}")
    return frozenset(paths)


def _validate_af240_inventory(inventory: dict[str, object]) -> None:
    if inventory.get("schema") != "asterion.dci.batch-parity/v1":
        raise ValueError("unknown inventory schema")
    rows = inventory.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("inventory rows must be non-empty")
    row_ids: list[str] = []
    future_methods: list[str] = []
    future_assertions: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("inventory row must be an object")
        row_id = row.get("id")
        if not isinstance(row_id, str) or not row_id:
            raise ValueError("inventory row id must be non-empty")
        row_ids.append(row_id)
        serialized = json.dumps(row, sort_keys=True).casefold()
        if any(token in serialized for token in AF240_FORBIDDEN):
            raise ValueError(f"placeholder value in {row_id}")
        status = row.get("implementation_status")
        if status not in {"implemented", "missing"}:
            raise ValueError(f"invalid implementation status in {row_id}")
        target_owner = row.get("target_asterion_owner")
        if target_owner not in AF240_OWNERS:
            raise ValueError(f"unknown target owner in {row_id}")
        target_task = row.get("target_task")
        if target_task not in AF240_FUTURE_TEST_TARGETS:
            raise ValueError(f"invalid target task in {row_id}")
        future = row.get("future_acceptance")
        if not isinstance(future, dict) or set(future) != {
            "task",
            "test_file",
            "test_class",
            "test_method",
            "assertion_id",
            "assertion_summary",
        }:
            raise ValueError(f"invalid future acceptance contract in {row_id}")
        expected_file, expected_class = AF240_FUTURE_TEST_TARGETS[target_task]
        if (
            future["task"] != target_task
            or future["test_file"] != expected_file
            or future["test_class"] != expected_class
        ):
            raise ValueError(f"future acceptance target does not match task in {row_id}")
        method = future["test_method"]
        assertion_id = future["assertion_id"]
        summary = future["assertion_summary"]
        behavior_slug = _af240_behavior_slug(row)
        if not isinstance(method, str) or not method.startswith("test_") or behavior_slug not in method:
            raise ValueError(f"future test method is not behavior-specific in {row_id}")
        if "inventory_acceptance_row" in method:
            raise ValueError(f"generic future test method in {row_id}")
        if not isinstance(assertion_id, str) or row_id not in assertion_id:
            raise ValueError(f"future assertion id is not behavior-specific in {row_id}")
        if not isinstance(summary, str) or row["source_name"] not in summary or row["source_path"] not in summary:
            raise ValueError(f"future assertion summary is not concrete in {row_id}")
        future_methods.append(method)
        future_assertions.append(assertion_id)
        current_owner = row.get("current_asterion_owner")
        current_symbol = row.get("current_symbol")
        current_tests = row.get("current_verification_tests")
        if status == "missing":
            if current_owner is not None or current_symbol is not None or current_tests != []:
                raise ValueError(f"missing behavior claims current evidence in {row_id}")
        else:
            if not isinstance(current_owner, str) or not isinstance(current_symbol, str):
                raise ValueError(f"implemented behavior lacks current owner in {row_id}")
            if not _resolve_current_owner(current_owner, current_symbol):
                raise ValueError(f"current owner does not resolve in {row_id}")
            if not isinstance(current_tests, list) or not current_tests:
                raise ValueError(f"implemented behavior lacks current tests in {row_id}")
            if not all(_resolve_test_name(test) for test in current_tests):
                raise ValueError(f"current verification test does not resolve in {row_id}")
    if row_ids != sorted(row_ids) or len(row_ids) != len(set(row_ids)):
        raise ValueError("inventory ids must be unique and stably sorted")
    if len(future_methods) != len(set(future_methods)):
        raise ValueError("future test methods must be unique per behavior")
    if len(future_assertions) != len(set(future_assertions)):
        raise ValueError("future assertion ids must be unique per behavior")

    indexed = {
        (row["source_path"], row["source_kind"], row["source_name"])
        for row in rows
    }
    for path in AF240_SOURCE_FILES:
        for function in _af240_source_functions(path):
            if (path, "function", function) not in indexed:
                raise ValueError(f"missing function mapping: {path}:{function}")
        for flag in _af240_source_flags(path):
            if (path, "cli_flag", flag) not in indexed:
                raise ValueError(f"missing flag mapping: {path}:{flag}")

    expected_launchers = {
        str(path.relative_to(REPO_ROOT))
        for directory in ("scripts/bcplus_eval", "scripts/qa", "scripts/bright")
        for path in (REPO_ROOT / directory).glob("run_*.sh")
    }
    mapped_launchers = {
        row["source_path"]
        for row in rows
        if row.get("source_kind") == "launcher"
    }
    if mapped_launchers != expected_launchers:
        raise ValueError("launcher inventory is incomplete")
    mapped_metrics = {
        row["source_name"] for row in rows if row.get("source_kind") == "metric"
    }
    if mapped_metrics != _af240_metric_paths_from_source():
        raise ValueError("source metric inventory is incomplete or fabricated")


class Af240InventoryTests(unittest.TestCase):
    def _inventory(self) -> dict[str, object]:
        return json.loads(
            (REPO_ROOT / "assets/dci/batch-parity.json").read_text(encoding="utf-8")
        )

    def test_af240_inventory_maps_complete_source_surface(self) -> None:
        inventory = self._inventory()
        _validate_af240_inventory(inventory)
        rows = inventory["rows"]
        self.assertEqual(
            {
                row["source_name"]
                for row in rows
                if row["source_kind"] == "durable_output"
                and row["source_path"] == "scripts/bcplus_eval/run_bcplus_eval.py"
            },
            {
                "analysis.json",
                "analysis.md",
                "analysis_figures/metric_distributions.png",
                "analysis_figures/runtime_breakdown.png",
                "analysis_figures/scatter_overview.png",
                "analysis_figures/tool_summary.png",
                "config.json",
                "conversation.json",
                "conversation_full.json",
                "eval_result.json",
                "events.jsonl",
                "final.txt",
                "input_question.txt",
                "item.json",
                "launcher_stderr.txt",
                "launcher_stdout.txt",
                "latest_model_context.json",
                "question.txt",
                "result.json",
                "results.jsonl",
                "state.json",
                "stderr.txt",
                "summary.json",
            },
        )
        self.assertEqual(
            {
                row["source_name"]
                for row in rows
                if row["source_kind"] == "target_output"
            },
            {"analysis.jsonl"},
        )
        extractor = inventory["extractor_contract"]
        self.assertEqual(
            extractor["column_aliases"],
            {
                "query_id": ["query_id", "id", "qid", "problem_id"],
                "query": ["query", "question", "problem", "input"],
                "answer": ["answer", "gold_answer", "solution", "output", "target"],
            },
        )
        self.assertEqual(
            extractor["semantics"],
            [
                "case-insensitive-column-aliases",
                "sorted-parquet-shards",
                "stable-shard-and-row-order",
                "canary-sha256-repeated-key-xor-base64",
                "no-decrypt-raw-values",
                "atomic-jsonl-replace",
            ],
        )
        self.assertEqual(inventory["launcher_counts"], {"bcplus": 2, "qa": 6, "bright": 4})
        launcher_rows = [row for row in rows if row["source_kind"] == "launcher"]
        for row in launcher_rows:
            self.assertEqual(
                set(row["source_profile"]),
                {
                    "dataset",
                    "output_root",
                    "corpus_dir",
                    "provider",
                    "model",
                    "tools",
                    "max_turns",
                    "max_concurrency",
                    "runtime_context_level",
                    "pi_thinking_level",
                    "node_max_old_space_size_mb",
                    "enable_ir",
                },
            )
        self.assertEqual(
            inventory["dynamic_launcher_controls"],
            ["runtime-context-level-positional", "optional-pi-thinking-level"],
        )
        dynamic_profile = next(
            row["source_profile"]
            for row in launcher_rows
            if row["source_name"] == "bcplus.dynamic-level-thinking"
        )
        self.assertEqual(dynamic_profile["runtime_context_level"], "${level}")
        self.assertEqual(dynamic_profile["pi_thinking_level"], "${thinking_level}")
        self.assertEqual(
            {
                row["source_name"]
                for row in rows
                if row["source_kind"] == "cache_rule"
            },
            {
                "completed-result-exact-judge-config",
                "completed-native-run-judge-only",
                "failed-or-incomplete-compatible-resume",
                "malformed-evidence-fail-closed",
                "dataset-order-aggregate-publication",
            },
        )
        metric_names = {
            row["source_name"] for row in rows if row["source_kind"] == "metric"
        }
        self.assertEqual(metric_names, _af240_metric_paths_from_source())

    def _rows(self) -> list[dict[str, object]]:
        inventory = self._inventory()
        _validate_af240_inventory(inventory)
        return inventory["rows"]

    def _assert_function_task(self, names: set[str], task: str) -> None:
        rows = self._rows()
        mapped = {
            row["source_name"]
            for row in rows
            if row["source_kind"] == "function"
            and row["source_path"] == "scripts/bcplus_eval/run_bcplus_eval.py"
            and row["target_task"] == task
        }
        self.assertTrue(names.issubset(mapped))

    def test_af240_h001_dataset_mapping_readiness(self) -> None:
        self._assert_function_task({"read_jsonl"}, "AF-240 Task 1")

    def test_af240_h001_prompt_mapping_readiness(self) -> None:
        self._assert_function_task(
            {"build_benchmark_prompt", "build_ir_prompt"}, "AF-240 Task 1"
        )

    def test_af240_h001_retrieval_mapping_readiness(self) -> None:
        self._assert_function_task(
            {"parse_retrieved_docs", "normalize_retrieved_path"}, "AF-240 Task 1"
        )

    def test_af240_h001_ir_metric_mapping_readiness(self) -> None:
        self._assert_function_task(
            {"compute_ndcg_at_k", "compute_ir_ndcg"}, "AF-240 Task 1"
        )

    def test_af240_h002_nested_coordinator_mapping_readiness(self) -> None:
        self._assert_function_task(
            {"persist_aggregate", "worker"}, "AF-240 Task 3"
        )

    def test_af240_h002_durable_query_mapping_readiness(self) -> None:
        rows = self._rows()
        names = {
            row["source_name"]
            for row in rows
            if row["source_kind"] == "durable_output"
            and row["source_path"] == "scripts/bcplus_eval/run_bcplus_eval.py"
        }
        self.assertTrue({"item.json", "result.json", "results.jsonl", "summary.json"}.issubset(names))

    def test_af240_h002_reuse_mapping_readiness(self) -> None:
        rows = self._rows()
        names = {
            row["source_name"] for row in rows if row["source_kind"] == "cache_rule"
        }
        self.assertEqual(
            names,
            {
                "completed-result-exact-judge-config",
                "completed-native-run-judge-only",
                "failed-or-incomplete-compatible-resume",
                "malformed-evidence-fail-closed",
                "dataset-order-aggregate-publication",
            },
        )

    def test_af240_h002_cancellation_mapping_readiness(self) -> None:
        rows = self._rows()
        row = next(row for row in rows if row["source_name"] == "cooperative-cancellation")
        self.assertEqual(row["source_kind"], "target_feature")
        self.assertEqual(row["target_task"], "AF-240 Task 3")

    def test_af240_h003_judge_mapping_readiness(self) -> None:
        self._assert_function_task(
            {"judge_answer_async", "judge_result_succeeded"}, "AF-240 Task 2"
        )

    def test_af240_h003_aggregate_metric_mapping_readiness(self) -> None:
        rows = self._rows()
        self.assertEqual(
            {row["source_name"] for row in rows if row["source_kind"] == "metric"},
            _af240_metric_paths_from_source(),
        )

    def test_af240_metric_paths_preserve_source_jsonpath_names(self) -> None:
        paths = _af240_metric_paths_from_source()
        self.assertIn("analysis.per_query_metrics[*].is_correct", paths)
        self.assertIn("judge_cost_estimate_usd.total_cost", paths)
        self.assertIn(
            "analysis.rankings.slowest_queries[*].wall_time_seconds", paths
        )
        self.assertNotIn("analysis.per_query.wall_time_seconds", paths)
        self.assertNotIn("judge_cost.total_cost", paths)
        self.assertNotIn("numeric_summary.p10", paths)

    def test_af240_h003_analysis_mapping_readiness(self) -> None:
        self._assert_function_task(
            {"compute_detailed_analysis", "rank_records", "write_analysis_artifacts"},
            "AF-240 Task 4",
        )

    def test_af240_h003_figure_mapping_readiness(self) -> None:
        rows = self._rows()
        outputs = {
            row["source_name"]
            for row in rows
            if row["source_kind"] == "durable_output"
            and str(row["source_name"]).endswith(".png")
        }
        self.assertEqual(
            outputs,
            {
                "analysis_figures/metric_distributions.png",
                "analysis_figures/runtime_breakdown.png",
                "analysis_figures/scatter_overview.png",
                "analysis_figures/tool_summary.png",
            },
        )

    def test_af240_h004_extractor_mapping_readiness(self) -> None:
        inventory = self._inventory()
        _validate_af240_inventory(inventory)
        self.assertIn("canary-sha256-repeated-key-xor-base64", inventory["extractor_contract"]["semantics"])

    def test_af240_h004_export_mapping_readiness(self) -> None:
        rows = self._rows()
        paths = {
            row["source_path"]
            for row in rows
            if row["source_kind"] == "function" and "export_" in row["source_path"]
        }
        self.assertEqual(
            paths,
            {
                "src/dci/benchmark/export_bc_plus_docs.py",
                "src/dci/benchmark/export_bright_docs.py",
            },
        )

    def test_af240_h004_launcher_mapping_readiness(self) -> None:
        rows = self._rows()
        launchers = [row for row in rows if row["source_kind"] == "launcher"]
        self.assertEqual(len(launchers), 12)
        self.assertEqual({row["launcher_family"] for row in launchers}, {"bcplus", "qa", "bright"})

    def test_af240_h004_installed_resource_mapping_readiness(self) -> None:
        rows = self._rows()
        row = next(row for row in rows if row["source_name"] == "installed-batch-profiles")
        self.assertEqual(row["source_kind"], "target_feature")
        self.assertEqual(row["target_task"], "AF-240 Task 6")

    def test_af240_future_acceptance_is_unique_and_behavior_specific(self) -> None:
        rows = self._rows()
        methods = [row["future_acceptance"]["test_method"] for row in rows]
        assertions = [row["future_acceptance"]["assertion_id"] for row in rows]
        self.assertEqual(len(methods), len(set(methods)))
        self.assertEqual(len(assertions), len(set(assertions)))
        for row in rows:
            future = row["future_acceptance"]
            self.assertIn(_af240_behavior_slug(row), future["test_method"])
            self.assertIn(row["id"], future["assertion_id"])
            self.assertNotIn("inventory_acceptance_row", future["test_method"])

    def test_af240_inventory_validator_rejects_missing_duplicate_placeholder_owner_and_tests(self) -> None:
        inventory = self._inventory()
        mutations = []
        missing = copy.deepcopy(inventory)
        missing["rows"] = [
            row
            for row in missing["rows"]
            if not (
                row["source_path"] == "scripts/bcplus_eval/run_bcplus_eval.py"
                and row["source_kind"] == "function"
                and row["source_name"] == "aggregate_results"
            )
        ]
        mutations.append(missing)
        nested = copy.deepcopy(inventory)
        nested["rows"] = [
            row for row in nested["rows"] if row["source_name"] != "worker"
        ]
        mutations.append(nested)
        duplicate = copy.deepcopy(inventory)
        duplicate["rows"].append(copy.deepcopy(duplicate["rows"][0]))
        mutations.append(duplicate)
        placeholder = copy.deepcopy(inventory)
        placeholder["rows"][0]["target_symbol"] = "TBD"
        mutations.append(placeholder)
        owner = copy.deepcopy(inventory)
        owner["rows"][0].update(
            implementation_status="implemented",
            current_asterion_owner="asterion.dci.analysis",
            current_symbol="absent_symbol",
            current_verification_tests=[
                "tests.test_climb_tools.Af240InventoryTests.test_af240_h003_analysis_mapping_readiness"
            ],
        )
        mutations.append(owner)
        tests = copy.deepcopy(inventory)
        tests["rows"][0].update(
            implementation_status="implemented",
            current_asterion_owner="asterion.dci.benchmark",
            current_symbol="run_benchmark",
            current_verification_tests=["tests.test_asterion_dci_benchmark.NoClass.test_absent"],
        )
        mutations.append(tests)
        metrics = copy.deepcopy(inventory)
        metrics["rows"] = [
            row
            for row in metrics["rows"]
            if row["source_name"]
            != "analysis.per_query_metrics[*].wall_time_seconds"
        ]
        mutations.append(metrics)
        target_task = copy.deepcopy(inventory)
        target_task["rows"][0]["target_task"] = "AF-240 Task 1"
        mutations.append(target_task)
        unrelated = copy.deepcopy(inventory)
        unrelated["rows"][0]["future_acceptance"]["test_method"] = (
            "test_same_task_but_unrelated_behavior"
        )
        mutations.append(unrelated)
        generic = copy.deepcopy(inventory)
        generic["rows"][0]["future_acceptance"]["test_method"] = (
            "test_inventory_acceptance_row"
        )
        mutations.append(generic)
        duplicate_assertion = copy.deepcopy(inventory)
        duplicate_assertion["rows"][1]["future_acceptance"]["assertion_id"] = (
            duplicate_assertion["rows"][0]["future_acceptance"]["assertion_id"]
        )
        mutations.append(duplicate_assertion)
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                _validate_af240_inventory(mutation)


class ClimbToolTests(unittest.TestCase):
    def test_resume_checkpoint_tracks_the_worklist_active_package(self) -> None:
        worklist = (REPO_ROOT / "docs/status/WORKLIST.md").read_text()
        resume = (REPO_ROOT / "docs/status/RESUME-NEXT-SESSION.md").read_text()
        active = re.findall(
            r"(?m)^## (AF-[0-9]+) — [^\n]+\n\n- Status: in_progress$",
            worklist,
        )
        lifecycle = re.search(
            r"(?m)^> Project lifecycle: (active|complete)$", worklist
        )

        self.assertIsNotNone(lifecycle)
        expected = active[0] if lifecycle.group(1) == "active" else "none"
        self.assertEqual(len(active), 1 if expected != "none" else 0)
        self.assertRegex(
            resume,
            rf"(?m)^Active work package: {re.escape(expected)}(?:\b.*)?$",
        )

    def test_regen_tree_serializes_tracked_hypothesis_state(self) -> None:
        result = subprocess.run(
            ["python3", "tools/climb/regen-tree.py"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        tree = json.loads(
            (REPO_ROOT / "docs/status/climb/research-tree.json").read_text()
        )
        hypotheses = yaml.safe_load(
            (REPO_ROOT / "docs/status/climb/hypotheses.yaml").read_text()
        )["hypotheses"]
        expected_active = {
            item["id"]
            for item in hypotheses
            if item["status"] in {"pending", "in-flight"}
        }
        expected_confirmed = {
            item["id"] for item in hypotheses if item["status"] == "confirmed"
        }
        self.assertEqual({item["id"] for item in tree["active"]}, expected_active)
        self.assertEqual(
            {item["id"] for item in tree["confirmed"]}, expected_confirmed
        )

    def test_h001_local_eval_reports_all_policy_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                evaluation["per_task"],
                {
                    "immutable_resolution": 1,
                    "repeat_validation": 1,
                    "dirty_checkout_safety": 1,
                    "override_compatibility": 1,
                },
            )

    def test_h002_local_eval_identifies_read_only_upgrade_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-002"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-002")
            self.assertEqual(evaluation["total"], 4)

    def test_h003_local_eval_identifies_rpc_protocol_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-003"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-003")
            self.assertEqual(evaluation["total"], 4)

    def test_h004_local_eval_identifies_run_provenance_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-004"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-004")
            self.assertEqual(evaluation["total"], 4)

    def test_h005_local_eval_identifies_pre_run_warning_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-005"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-005")
            self.assertEqual(evaluation["total"], 4)

    def test_h006_local_eval_identifies_judge_preflight_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-006"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-006")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "shared_transport": 1,
                    "missing_key_safety": 1,
                    "safe_output": 1,
                    "make_and_adapter": 1,
                },
            )

    def test_h007_local_eval_identifies_judge_key_provenance_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-007"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-007")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "dotenv_source": 1,
                    "process_source": 1,
                    "shadow_warning": 1,
                    "safe_output": 1,
                },
            )

    def test_h008_local_eval_identifies_no_request_config_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-008"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-008")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "config_only_safety": 1,
                    "dotenv_source": 1,
                    "shadow_warning": 1,
                    "make_and_adapter": 1,
                },
            )

    def test_h010_local_eval_identifies_judge_request_fingerprint_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-010"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-010")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "fingerprint_shape": 1,
                    "result_persistence": 1,
                    "reuse_contract": 1,
                    "adapter_integration": 1,
                },
            )

    def test_h011_local_eval_identifies_judge_error_redaction_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-011"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-011")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "invalid_response_redaction": 1,
                    "http_error_redaction": 1,
                    "retry_contract": 1,
                    "adapter_integration": 1,
                },
            )

    def test_h012_local_eval_identifies_judge_artifact_privacy_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-012"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-012")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "safe_result_projection": 1,
                    "invalid_error_redaction": 1,
                    "http_error_redaction": 1,
                    "adapter_integration": 1,
                },
            )

    def test_h013_local_eval_identifies_complete_judge_cache_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-013"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-013")
            self.assertEqual(
                evaluation["per_task"],
                {
                    "matching_identity_reuse": 1,
                    "legacy_rejection": 1,
                    "incomplete_rejection": 1,
                    "adapter_integration": 1,
                },
            )

    def test_h014_local_eval_identifies_judge_input_privacy_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "H-014"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation.get("hypothesis_id"), "H-014")
            self.assertEqual(evaluation["total"], 4)

    def test_record_cycle_confirms_four_of_four_and_advances(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / "climb"
            shutil.copytree(REPO_ROOT / "docs/status/climb", state_dir)
            hypothesis_path = state_dir / "hypotheses.yaml"
            isolated_hypotheses = yaml.safe_load(hypothesis_path.read_text())
            isolated_hypotheses["hypotheses"] = [
                hypothesis
                for hypothesis in isolated_hypotheses["hypotheses"]
                if hypothesis["id"] in {"H-001", "H-002", "H-003"}
            ]
            for hypothesis in isolated_hypotheses["hypotheses"]:
                hypothesis["results"] = []
                hypothesis["status"] = (
                    "in-flight" if hypothesis["id"] == "H-001" else "pending"
                )
            hypothesis_path.write_text(
                yaml.safe_dump(
                    isolated_hypotheses, sort_keys=False, allow_unicode=True
                )
            )
            session_path = state_dir / "session-state.json"
            legacy_session = json.loads(session_path.read_text())
            legacy_session.pop("work_package_id", None)
            session_path.write_text(json.dumps(legacy_session, indent=2) + "\n")
            journal = root / "JOURNAL.md"
            journal.write_text("# Test Journal\n\n## 2026-07-12\n")
            run_dir = root / "run-h001"
            run_dir.mkdir()
            (run_dir / "local-eval.json").write_text(
                json.dumps(
                    {
                        "total": 4,
                        "per_task": {
                            "immutable_resolution": 1,
                            "repeat_validation": 1,
                            "dirty_checkout_safety": 1,
                            "override_compatibility": 1,
                        },
                    }
                )
            )

            command = [
                "python3",
                "tools/climb/record-cycle.py",
                "--state-dir",
                str(state_dir),
                "--journal",
                str(journal),
                "--hypothesis-id",
                "H-001",
                "--run-id",
                "dci-climb-h001-test",
                "--run-dir",
                str(run_dir),
                "--cycle",
                "1",
            ]
            result = subprocess.run(
                command,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )
            replay = subprocess.run(
                command,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(replay.returncode, 0, replay.stderr)
            state = yaml.safe_load((state_dir / "hypotheses.yaml").read_text())
            h001 = next(h for h in state["hypotheses"] if h["id"] == "H-001")
            self.assertEqual(h001["status"], "confirmed")
            self.assertEqual(h001["results"][-1]["local"], 4)
            self.assertEqual(
                sum(
                    result["run"] == "dci-climb-h001-test"
                    for result in h001["results"]
                ),
                1,
            )
            runs_path = state_dir / "runs.csv"
            with runs_path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[-1]["verdict"], "confirmed 4/4")
            self.assertEqual(
                sum(row["run_id"] == "dci-climb-h001-test" for row in rows), 1
            )
            self.assertEqual(
                rows[-1]["manifest_path"],
                "runs/climb/dci-climb-h001-test/manifest.json",
            )
            self.assertNotIn(b"\r", runs_path.read_bytes())
            session = json.loads((state_dir / "session-state.json").read_text())
            self.assertEqual(session["next_hypothesis"], "H-002")
            self.assertIn("H-001 confirmed 4/4", journal.read_text())

    def test_record_cycle_recovers_hypothesis_specific_partial_write(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / "climb"
            shutil.copytree(REPO_ROOT / "docs/status/climb", state_dir)
            hypothesis_path = state_dir / "hypotheses.yaml"
            state = yaml.safe_load(hypothesis_path.read_text())
            state["hypotheses"] = [
                hypothesis
                for hypothesis in state["hypotheses"]
                if hypothesis["id"] == "H-006"
            ]
            h006 = state["hypotheses"][0]
            h006["status"] = "confirmed"
            h006["results"] = [
                {
                    "session": "2026-07-12-pi-revision",
                    "cycle": 6,
                    "run": "dci-climb-h006-test",
                    "local": 4,
                    "local_per_task": {
                        "shared_transport": 1,
                        "missing_key_safety": 1,
                        "safe_output": 1,
                        "make_and_adapter": 1,
                    },
                    "online": None,
                    "verdict": "confirmed 4/4",
                    "decision_reason": "deterministic local setup-policy acceptance",
                }
            ]
            hypothesis_path.write_text(
                yaml.safe_dump(state, sort_keys=False, allow_unicode=True)
            )
            journal = root / "JOURNAL.md"
            journal.write_text("# Test Journal\n\n## 2026-07-12\n")
            run_dir = root / "run-h006"
            run_dir.mkdir()
            (run_dir / "local-eval.json").write_text(
                json.dumps(
                    {
                        "total": 4,
                        "per_task": {
                            "shared_transport": 1,
                            "missing_key_safety": 1,
                            "safe_output": 1,
                            "make_and_adapter": 1,
                        },
                    }
                )
            )

            result = subprocess.run(
                [
                    "python3",
                    "tools/climb/record-cycle.py",
                    "--state-dir",
                    str(state_dir),
                    "--journal",
                    str(journal),
                    "--hypothesis-id",
                    "H-006",
                    "--run-id",
                    "dci-climb-h006-test",
                    "--run-dir",
                    str(run_dir),
                    "--cycle",
                    "6",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            recovered = yaml.safe_load(hypothesis_path.read_text())["hypotheses"][0]
            self.assertEqual(len(recovered["results"]), 1)
            with (state_dir / "runs.csv").open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            row = rows[-1]
            self.assertEqual(row["hypothesis_id"], "H-006")
            self.assertEqual(row["local_score"], "4")
            self.assertEqual(row["immutable_resolution"], "")
            self.assertEqual(row["repeat_validation"], "")
            self.assertEqual(row["dirty_checkout_safety"], "")
            self.assertEqual(row["override_compatibility"], "")

    def test_record_cycle_uses_active_af050_session_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / "climb"
            shutil.copytree(REPO_ROOT / "docs/status/climb", state_dir)
            hypothesis_path = state_dir / "hypotheses.yaml"
            state = yaml.safe_load(hypothesis_path.read_text())
            state["hypotheses"] = [
                hypothesis
                for hypothesis in state["hypotheses"]
                if hypothesis["id"] in {"AF-050-H-001", "AF-050-H-002"}
            ]
            state["hypotheses"].append(
                {
                    "id": "AF-100-H-001",
                    "work_package_id": "AF-100",
                    "description": "future package",
                    "parent_paradigm": "future",
                    "expected_lift": "+1",
                    "cost_h": 0.1,
                    "ranking": 99.0,
                    "status": "pending",
                    "created_at": "2026-07-13T00:00:00+08:00",
                    "results": [],
                }
            )
            for hypothesis in state["hypotheses"]:
                hypothesis["results"] = []
                hypothesis["status"] = (
                    "in-flight"
                    if hypothesis["id"] == "AF-050-H-001"
                    else "pending"
                )
            session_path = state_dir / "session-state.json"
            session = json.loads(session_path.read_text())
            session["session"] = "2026-07-12-af-050-rust-executor"
            session["work_package_id"] = "AF-050"
            session_path.write_text(json.dumps(session, indent=2) + "\n")
            hypothesis_path.write_text(
                yaml.safe_dump(state, sort_keys=False, allow_unicode=True)
            )
            journal = root / "JOURNAL.md"
            journal.write_text("# Test Journal\n\n## 2026-07-12\n")
            run_dir = root / "run-af050-h001"
            run_dir.mkdir()
            (run_dir / "local-eval.json").write_text(
                json.dumps(
                    {
                        "total": 4,
                        "per_task": {
                            "unknown_program_denial": 1,
                            "cwd_containment": 1,
                            "policy_limits": 1,
                            "authorized_values": 1,
                        },
                    }
                )
            )

            result = subprocess.run(
                [
                    "python3",
                    "tools/climb/record-cycle.py",
                    "--state-dir",
                    str(state_dir),
                    "--journal",
                    str(journal),
                    "--hypothesis-id",
                    "AF-050-H-001",
                    "--run-id",
                    "dci-climb-af050-h001-test",
                    "--run-dir",
                    str(run_dir),
                    "--cycle",
                    "20",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            recorded = yaml.safe_load(hypothesis_path.read_text())["hypotheses"][0]
            self.assertEqual(
                recorded["results"][-1]["session"],
                "2026-07-12-af-050-rust-executor",
            )
            self.assertEqual(
                recorded["results"][-1]["decision_reason"],
                "deterministic local executor acceptance",
            )
            session = json.loads((state_dir / "session-state.json").read_text())
            self.assertEqual(session["next_hypothesis"], "AF-050-H-002")

    def test_record_cycle_classifies_af070_as_package_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / "climb"
            shutil.copytree(REPO_ROOT / "docs/status/climb", state_dir)
            hypothesis_path = state_dir / "hypotheses.yaml"
            state = yaml.safe_load(hypothesis_path.read_text())
            state["hypotheses"] = [
                hypothesis
                for hypothesis in state["hypotheses"]
                if hypothesis["id"] == "AF-070-H-001"
            ]
            hypothesis = state["hypotheses"][0]
            hypothesis["results"] = []
            hypothesis["status"] = "in-flight"
            hypothesis_path.write_text(
                yaml.safe_dump(state, sort_keys=False, allow_unicode=True)
            )
            journal = root / "JOURNAL.md"
            journal.write_text("# Test Journal\n\n## 2026-07-12\n")
            run_dir = root / "run-af070-h001"
            run_dir.mkdir()
            (run_dir / "local-eval.json").write_text(
                json.dumps(
                    {
                        "total": 4,
                        "per_task": {
                            "portable_manifests": 1,
                            "workflow_kind": 1,
                            "stable_graph": 1,
                            "forbidden_fields": 1,
                        },
                    }
                )
            )

            result = subprocess.run(
                [
                    "python3",
                    "tools/climb/record-cycle.py",
                    "--state-dir",
                    str(state_dir),
                    "--journal",
                    str(journal),
                    "--hypothesis-id",
                    "AF-070-H-001",
                    "--run-id",
                    "dci-climb-af070-h001-test",
                    "--run-dir",
                    str(run_dir),
                    "--cycle",
                    "31",
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            recorded = yaml.safe_load(hypothesis_path.read_text())["hypotheses"][0]
            self.assertEqual(
                recorded["results"][-1]["decision_reason"],
                "deterministic local package acceptance",
            )
            self.assertIn("package acceptance recorded", journal.read_text())

    def test_cycle_adapter_shell_scripts_pass_syntax_validation(self) -> None:
        scripts = [
            "tools/climb/train.sh",
            "tools/climb/eval-local.sh",
            "tools/climb/push.sh",
            "tools/climb/apply-lb-score.sh",
            "tools/climb/cycle.sh",
        ]

        result = subprocess.run(
            ["bash", "-n", *scripts],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)

    def test_cycle_runs_scope_audit_before_training(self) -> None:
        cycle_script = (REPO_ROOT / "tools/climb/cycle.sh").read_text()
        guard = (
            'python3 "$ROOT/tools/project_scope_check.py" '
            '--climb-hypothesis "$HYPOTHESIS_ID"'
        )

        self.assertIn(guard, cycle_script)
        self.assertLess(cycle_script.index(guard), cycle_script.index('run_dir="$(bash'))

    def test_h003_train_runs_the_real_model_free_probe(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("scripts/check_pi_rpc.py", train_script)
        self.assertIn("uv run python", train_script)

    def test_h004_train_runs_runtime_acceptance(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("make runtime-example", train_script)

    def test_h006_train_runs_the_live_judge_preflight(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("tests.test_check_judge", train_script)
        self.assertIn("make check-judge", train_script)

    def test_h007_train_checks_dotenv_provenance(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-007", train_script)
        self.assertIn("env -u DEEPSEEK_API_KEY make check-judge", train_script)

    def test_h008_train_checks_config_without_request(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-008", train_script)
        self.assertIn(
            "env -u DEEPSEEK_API_KEY make check-judge-config", train_script
        )

    def test_h009_train_checks_strict_schema(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-009", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h010_train_checks_request_fingerprints(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-010", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h011_train_checks_malformed_response_redaction(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-011", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h012_train_checks_judge_artifact_privacy(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-012", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h013_train_checks_complete_judge_cache_results(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-013", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h014_train_checks_judge_input_privacy(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-014", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h016_train_checks_judge_origin_validation(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-016", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h017_train_checks_judge_redirect_containment(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-017", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h018_train_checks_official_responses_retention(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-018", train_script)
        self.assertIn("tests.test_judge", train_script)

    def test_h019_train_checks_rpc_settlement_postcondition(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("H-019", train_script)
        self.assertIn("tests.test_pi_rpc_runner", train_script)

    def test_af050_h001_train_runs_rust_authorization_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-050-H-001", train_script)
        self.assertIn("--test authorization", train_script)

    def test_af050_h001_eval_reports_four_authorization_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-050-H-001"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-050-H-001")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "unknown_program_denial",
                    "cwd_containment",
                    "policy_limits",
                    "authorized_values",
                },
            )

    def test_af050_h002_train_runs_rust_process_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-050-H-002", train_script)
        self.assertIn("--test process", train_script)

    def test_af050_h002_eval_reports_four_process_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-050-H-002"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-050-H-002")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "literal_arguments",
                    "cleared_environment",
                    "closed_stdin",
                    "canonical_cwd",
                },
            )

    def test_af050_h003_train_runs_bounded_process_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-050-H-003", train_script)
        self.assertIn("H-003 bounded process resources", train_script)

    def test_af050_h003_eval_reports_four_resource_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-050-H-003"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-050-H-003")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "bounded_streams",
                    "exact_limit",
                    "deadline_kill_reap",
                    "direct_boundary_regression",
                },
            )

    def test_af050_h004_train_runs_concurrent_service_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-050-H-004", train_script)
        self.assertIn("--test service", train_script)

    def test_af050_h004_eval_reports_four_service_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-050-H-004"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-050-H-004")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "responsive_out_of_order",
                    "duplicate_id_denial",
                    "cancel_exactly_once",
                    "safe_parse_error",
                },
            )

    def test_af050_operator_docs_and_root_verification_targets_exist(self) -> None:
        makefile = (REPO_ROOT / "Makefile").read_text()
        guide = (REPO_ROOT / "asterion/docs/operator/rust-executor.md").read_text()

        self.assertIn("test-rust-executor:", makefile)
        self.assertIn("check-rust-executor:", makefile)
        self.assertIn("not an operating-system sandbox", guide)
        self.assertIn("trusted operator configuration", guide)

    def test_af050_h005_train_runs_framework_closure_gate(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-050-H-005", train_script)
        self.assertIn("make test-rust-executor", train_script)
        self.assertIn("make check-rust-executor", train_script)

    def test_af050_h005_eval_reports_four_closure_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-050-H-005"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-050-H-005")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "operator_binary",
                    "operator_docs",
                    "root_test_target",
                    "root_check_target",
                },
            )

    def test_af060_h001_train_runs_package_manifest_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-060-H-001", train_script)
        self.assertIn("tests.test_package_composition", train_script)

    def test_af060_h001_eval_reports_four_manifest_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-060-H-001"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-060-H-001")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "valid_manifest",
                    "portable_kinds",
                    "closed_invalid_fixtures",
                    "sorted_unique_edges",
                },
            )

    def test_af060_h002_train_runs_package_composer_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-060-H-002", train_script)
        self.assertIn("PackageCompositionTests", train_script)

    def test_af060_h002_eval_reports_four_composition_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-060-H-002"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-060-H-002")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "stable_order",
                    "duplicate_and_ambiguity",
                    "missing_edges",
                    "cycle_rejection",
                },
            )

    def test_af060_h003_train_runs_dci_reference_graph_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-060-H-003", train_script)
        self.assertIn("DciReferencePackageTests", train_script)

    def test_af060_h003_eval_reports_four_reference_graph_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-060-H-003"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-060-H-003")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "portable_manifests",
                    "runtime_parity",
                    "research_audit_edges",
                    "capability_rejection",
                },
            )

    def test_af060_h004_train_runs_typescript_package_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-060-H-004", train_script)
        self.assertIn("npm --prefix asterion/packages/typescript/asterion-runtime test", train_script)

    def test_af060_h004_eval_reports_four_typescript_parity_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-060-H-004"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-060-H-004")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "valid_fixture",
                    "invalid_fixtures",
                    "canonical_ordering",
                    "public_type_contract",
                },
            )

    def test_af060_h005_train_runs_full_framework_closure_gate(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-060-H-005", train_script)
        self.assertIn("python -m unittest discover -s tests -v", train_script)
        self.assertIn("make test-typescript-host", train_script)
        self.assertIn("make test-rust-executor", train_script)
        self.assertIn("make check-rust-executor", train_script)

    def test_full_python_train_closures_cover_both_test_roots(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        closure_ids = (
            "AF-060-H-005",
            "AF-070-H-004",
            "AF-080-H-004",
            "AF-090-H-004",
            "AF-095-H-004",
            "AF-100-H-004",
            "AF-210-H-004",
        )
        branch_pattern = re.compile(
            r'elif \[ "\$1" = "(?P<id>AF-[0-9]+-H-[0-9]+)" \]; then\n'
            r"(?P<body>.*?)(?=\nelif \[ \"\$1\" = \"AF-|\Z)",
            re.DOTALL,
        )
        branches = {
            match.group("id"): match.group("body")
            for match in branch_pattern.finditer(train_script)
        }
        full_discovery_ids = {
            hypothesis_id
            for hypothesis_id, body in branches.items()
            if "uv run python -m unittest discover" in body
        }

        self.assertEqual(full_discovery_ids, set(closure_ids))
        expected_lines = {
            "uv run python -m unittest discover -s tests -v",
            "(cd asterion && uv run python -m unittest discover -s tests -v)",
            "uv run python -m compileall -q src asterion/src/asterion asterion/tests tests tools",
            "uv run ruff check src asterion/src/asterion asterion/tests tests tools",
        }
        for hypothesis_id in closure_ids:
            with self.subTest(hypothesis_id=hypothesis_id):
                lines = {line.strip() for line in branches[hypothesis_id].splitlines()}
                self.assertTrue(expected_lines <= lines, expected_lines - lines)

    def test_af060_h005_eval_reports_four_documentation_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-060-H-005"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-060-H-005")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "static_boundary",
                    "manifest_example",
                    "composer_example",
                    "extension_security",
                },
            )

    def test_af070_h001_train_runs_controlled_code_manifest_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-070-H-001", train_script)
        self.assertIn("ControlledCodePackageTests", train_script)

    def test_af070_h001_eval_reports_four_manifest_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-070-H-001"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-070-H-001")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "portable_manifests",
                    "workflow_kind",
                    "stable_graph",
                    "forbidden_fields",
                },
            )

    def test_af070_h002_train_runs_controlled_code_boundary_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-070-H-002", train_script)
        self.assertIn("test_controlled_code_graph_rejects_every_missing_boundary", train_script)

    def test_af070_h002_eval_reports_four_boundary_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-070-H-002"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-070-H-002")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "runtime_parity",
                    "permutation_stability",
                    "portable_outputs",
                    "missing_boundary_rejection",
                },
            )

    def test_af070_h003_train_runs_typescript_reference_manifest_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-070-H-003", train_script)
        self.assertIn("npm --prefix asterion/packages/typescript/asterion-runtime test", train_script)

    def test_af070_h003_eval_reports_four_typescript_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-070-H-003"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-070-H-003")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "all_reference_manifests",
                    "canonical_schema",
                    "public_validator",
                    "no_typescript_composer",
                },
            )

    def test_af070_h004_train_runs_full_framework_closure_gate(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-070-H-004", train_script)
        self.assertIn("python -m unittest discover -s tests -v", train_script)
        self.assertIn("npm --prefix asterion/packages/typescript/asterion-runtime ci", train_script)
        self.assertIn("make test-rust-executor", train_script)
        self.assertIn("make check-rust-executor", train_script)

    def test_af070_h004_eval_reports_four_closure_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-070-H-004"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-070-H-004")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "second_graph_docs",
                    "static_boundary",
                    "host_service_boundary",
                    "framework_closure",
                },
            )

    def test_af080_h001_train_runs_local_discovery_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-080-H-001", train_script)
        self.assertIn("PackageDiscoveryTests", train_script)

    def test_af080_h001_eval_reports_four_discovery_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-080-H-001"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-080-H-001")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "root_permutation",
                    "file_order",
                    "canonical_validation",
                    "non_recursive_filtering",
                },
            )

    def test_af080_h002_train_runs_catalog_boundary_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-080-H-002", train_script)
        self.assertIn("PackageCatalogBoundaryTests", train_script)

    def test_af080_h002_eval_reports_four_boundary_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-080-H-002"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-080-H-002")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "root_boundary",
                    "document_boundary",
                    "symlink_boundary",
                    "duplicate_identity",
                },
            )

    def test_af080_h003_train_runs_exact_selection_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-080-H-003", train_script)
        self.assertIn("PackageSelectionTests", train_script)

    def test_af080_h003_eval_reports_four_selection_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-080-H-003"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-080-H-003")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "exact_selection",
                    "fresh_manifests",
                    "graph_integration",
                    "selection_rejection",
                },
            )

    def test_af080_h004_train_runs_full_framework_closure_gate(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-080-H-004", train_script)
        self.assertIn("python -m unittest discover -s tests -v", train_script)
        self.assertIn("npm --prefix asterion/packages/typescript/asterion-runtime ci", train_script)
        self.assertIn("make test-rust-executor", train_script)
        self.assertIn("make check-rust-executor", train_script)

    def test_af080_h004_eval_reports_four_closure_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-080-H-004"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-080-H-004")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "catalog_docs",
                    "filesystem_boundary",
                    "selection_boundary",
                    "framework_closure",
                },
            )

    def test_af090_h001_train_runs_assembly_manifest_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        self.assertIn("AF-090-H-001", train_script)
        self.assertIn("AssemblyManifestTests", train_script)

    def test_af090_h001_eval_reports_four_manifest_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-090-H-001"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(
                set(evaluation["per_task"]),
                {"valid_manifest", "closed_contract", "canonical_refs", "canonical_edges"},
            )

    def test_af090_h002_train_runs_static_assembly_resolver_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        self.assertIn("AF-090-H-002", train_script)
        self.assertIn("AssemblyResolverTests", train_script)

    def test_af090_h002_eval_reports_four_resolver_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-090-H-002"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-090-H-002")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "runtime_binding",
                    "catalog_binding",
                    "capability_separation",
                    "safe_resolution",
                },
            )

    def test_af090_h003_train_runs_reference_assembly_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        self.assertIn("AF-090-H-003", train_script)
        self.assertIn("ReferenceAssemblyTests", train_script)

    def test_af090_h003_eval_reports_four_reference_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-090-H-003"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-090-H-003")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {"dci_plan", "runtime_parity", "controlled_plan", "service_separation"},
            )

    def test_af090_h004_train_runs_full_framework_closure_gate(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        self.assertIn("AF-090-H-004", train_script)
        self.assertIn("python -m unittest discover -s tests -v", train_script)
        self.assertIn("npm --prefix asterion/packages/typescript/asterion-runtime ci", train_script)
        self.assertIn("make test-rust-executor", train_script)
        self.assertIn("make check-rust-executor", train_script)

    def test_af090_h004_eval_reports_four_closure_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-090-H-004"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-090-H-004")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {"typescript_parity", "assembly_docs", "non_execution", "framework_closure"},
            )

    def test_af095_h001_train_runs_asterion_structure_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        self.assertIn("AF-095-H-001", train_script)
        self.assertIn("AsterionStructureTests", train_script)

    def test_af095_h001_eval_reports_four_ownership_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-095-H-001"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "authoritative_import",
                    "object_identity",
                    "dependency_direction",
                    "packaging_compatibility",
                },
            )

    def test_af095_h002_train_runs_extracted_contract_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        self.assertIn("AF-095-H-002", train_script)
        self.assertIn("test_package_and_assembly_objects_are_compatibility_aliases", train_script)

    def test_af095_h002_eval_reports_four_extraction_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-095-H-002"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {"package_extraction", "assembly_extraction", "wire_stability", "single_implementation"},
            )

    def test_af095_h003_train_runs_product_directory_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        self.assertIn("AF-095-H-003", train_script)
        self.assertIn("test_declarative_assets_have_product_level_owners", train_script)
        self.assertIn("asterion/packages/typescript/asterion-runtime", train_script)
        self.assertIn("asterion/packages/rust/controlled-executor", train_script)

    def test_af095_h003_eval_reports_four_directory_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-095-H-003"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {"capability_roots", "application_root", "cross_language_paths", "identity_stability"},
            )

    def test_af095_h004_train_runs_full_framework_closure_gate(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        self.assertIn("AF-095-H-004", train_script)
        self.assertIn("python -m unittest discover -s tests -v", train_script)
        self.assertIn("asterion/packages/typescript/asterion-runtime ci", train_script)
        self.assertIn("make test-rust-executor", train_script)
        self.assertIn("make check-rust-executor", train_script)

    def test_af095_h004_eval_reports_four_closure_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-095-H-004"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {"dci_cli_compatibility", "example_compatibility", "architecture_boundary", "framework_closure"},
            )

    def test_af100_h001_train_runs_capability_ownership_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        self.assertIn("AF-100-H-001", train_script)
        self.assertIn("test_capability_ownership_is_not_inferred_from_names", train_script)

    def test_af100_h001_eval_reports_four_ownership_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-100-H-001"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-100-H-001")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "runtime_ownership",
                    "host_ownership",
                    "immutable_plan",
                    "no_name_inference",
                },
            )

    def test_af100_h002_train_runs_application_runner_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        self.assertIn("AF-100-H-002", train_script)
        self.assertIn("tests.test_application_runner", train_script)

    def test_af100_h002_eval_reports_four_runner_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-100-H-002"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-100-H-002")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "portable_request",
                    "runtime_invocation",
                    "immutable_events",
                    "artifact_projection",
                },
            )

    def test_af100_h003_train_runs_runner_safety_suite(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        self.assertIn("AF-100-H-003", train_script)
        self.assertIn("test_runtime_and_service_mismatches_fail_before_invocation", train_script)

    def test_af100_h003_eval_reports_four_safety_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-100-H-003"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-100-H-003")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "runtime_parity",
                    "cancellation",
                    "preflight_safety",
                    "error_redaction",
                },
            )

    def test_af100_h004_train_runs_full_framework_closure_gate(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        self.assertIn("AF-100-H-004", train_script)
        self.assertIn("python -m unittest discover -s tests -v", train_script)
        self.assertIn("asterion/packages/typescript/asterion-runtime ci", train_script)
        self.assertIn("make test-rust-executor", train_script)
        self.assertIn("project_scope_check.py --climb-hypothesis AF-100-H-004", train_script)

    def test_af100_h004_eval_reports_four_closure_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-100-H-004"
            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-100-H-004")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "runner_docs",
                    "boundary_integrity",
                    "language_ownership",
                    "framework_closure",
                },
            )

    def test_af210_train_registers_every_application_parity_hypothesis(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        for hypothesis_id, suite in (
            ("AF-210-H-001", "tests.test_asterion_dci_application_executor"),
            ("AF-210-H-002", "tests.test_dci_research_capability"),
            ("AF-210-H-003", "tests.test_builtin_dci_application"),
            ("AF-210-H-004", "tests.test_distribution_boundaries"),
        ):
            with self.subTest(hypothesis_id=hypothesis_id):
                self.assertIn(hypothesis_id, train_script)
                self.assertIn(suite, train_script)

    def test_af210_local_eval_reports_application_parity_dimensions(self) -> None:
        expected_dimensions = {
            "AF-210-H-001": {
                "native_executor",
                "configuration_namespace",
                "default_isolation",
                "dotenv_precedence",
            },
            "AF-210-H-002": {
                "pi_native_dispatch",
                "claude_fixture_scope",
                "native_failure_redaction",
                "body_free_projection",
            },
            "AF-210-H-003": {
                "installed_native_dispatch",
                "installed_failure_redaction",
                "generic_cli_neutrality",
                "wheel_installation",
            },
            "AF-210-H-004": {
                "full_python_suite",
                "python_quality_and_shell",
                "typescript_runtime",
                "rust_scope_and_diff",
            },
        }
        for hypothesis_id, dimensions in expected_dimensions.items():
            with self.subTest(hypothesis_id=hypothesis_id), tempfile.TemporaryDirectory() as temp_dir:
                run_dir = Path(temp_dir)
                env = os.environ.copy()
                env["DCI_CLIMB_HYPOTHESIS_ID"] = hypothesis_id
                result = subprocess.run(
                    ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                evaluation = json.loads((run_dir / "local-eval.json").read_text())
                self.assertEqual(evaluation["hypothesis_id"], hypothesis_id)
                self.assertEqual(evaluation["total"], 4)
                self.assertEqual(set(evaluation["per_task"]), dimensions)

    def test_af220_train_registers_every_shared_product_parity_hypothesis(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        for hypothesis_id, suite in (
            ("AF-220-H-001", "tests.test_asterion_dci_judge"),
            ("AF-220-H-002", "tests.test_asterion_dci_pi_rpc"),
            ("AF-220-H-003", "tests.test_asterion_dci_benchmark"),
            ("AF-220-H-004", "tests.test_asterion_dci_application_executor"),
        ):
            with self.subTest(hypothesis_id=hypothesis_id):
                self.assertIn(hypothesis_id, train_script)
                self.assertIn(suite, train_script)

    def test_af220_local_eval_reports_shared_product_parity_dimensions(self) -> None:
        expected_dimensions = {
            "AF-220-H-001": {
                "shared_path_precedence",
                "runtime_option_precedence",
                "shared_judge_precedence",
                "invalid_shared_values",
            },
            "AF-220-H-002": {
                "typed_request_mapping",
                "pi_context_controls",
                "node_heap_preservation",
                "literal_control_safety",
            },
            "AF-220-H-003": {
                "cli_shared_defaults",
                "cli_explicit_override",
                "batch_runtime_propagation",
                "bounded_sorted_limit",
            },
            "AF-220-H-004": {
                "application_shared_options",
                "installed_provider_boundary",
                "example_shared_configuration",
                "example_preflight_safety",
            },
        }
        for hypothesis_id, dimensions in expected_dimensions.items():
            with self.subTest(hypothesis_id=hypothesis_id), tempfile.TemporaryDirectory() as temp_dir:
                run_dir = Path(temp_dir)
                env = os.environ.copy()
                env["DCI_CLIMB_HYPOTHESIS_ID"] = hypothesis_id
                result = subprocess.run(
                    ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                evaluation = json.loads((run_dir / "local-eval.json").read_text())
                self.assertEqual(evaluation["hypothesis_id"], hypothesis_id)
                self.assertEqual(evaluation["total"], 4)
                self.assertEqual(set(evaluation["per_task"]), dimensions)

    def test_af230_train_registers_every_native_operator_hypothesis(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        for hypothesis_id, suite in (
            ("AF-230-H-001", "tests.test_asterion_dci_application_executor"),
            ("AF-230-H-002", "tests.test_asterion_dci_artifacts"),
            ("AF-230-H-003", "tests.test_asterion_dci_run"),
            ("AF-230-H-004", "tests.test_asterion_dci_pi_rpc"),
        ):
            with self.subTest(hypothesis_id=hypothesis_id):
                self.assertIn(hypothesis_id, train_script)
                self.assertIn(suite, train_script)

    def test_af230_local_eval_reports_native_operator_dimensions(self) -> None:
        expected_dimensions = {
            "AF-230-H-001": {
                "private_atomic_recorder",
                "unified_production_path",
                "resume_writer_safety",
                "application_projection",
            },
            "AF-230-H-002": {
                "full_processed_separation",
                "safe_tool_externalization",
                "latest_provider_context",
                "protocol_digest",
            },
            "AF-230-H-003": {
                "credential_safe_provenance",
                "attempt_isolation",
                "terminal_status_validation",
                "lock_lifetime",
            },
            "AF-230-H-004": {
                "run_input_resources",
                "conversation_controls",
                "terminal_literal_boundary",
                "node_selection",
            },
        }
        for hypothesis_id, dimensions in expected_dimensions.items():
            with self.subTest(hypothesis_id=hypothesis_id), tempfile.TemporaryDirectory() as temp_dir:
                run_dir = Path(temp_dir)
                env = os.environ.copy()
                env["DCI_CLIMB_HYPOTHESIS_ID"] = hypothesis_id
                result = subprocess.run(
                    ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                evaluation = json.loads((run_dir / "local-eval.json").read_text())
                self.assertEqual(evaluation["hypothesis_id"], hypothesis_id)
                self.assertEqual(evaluation["total"], 4)
                self.assertEqual(set(evaluation["per_task"]), dimensions)

    def test_af240_train_registers_every_batch_parity_hypothesis(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        all_names = {name for names in AF240_READINESS_TESTS.values() for name in names}
        self.assertEqual(len(all_names), 4 * len(AF240_READINESS_TESTS))
        for hypothesis_id, expected_names in AF240_READINESS_TESTS.items():
            with self.subTest(hypothesis_id=hypothesis_id):
                marker = f'elif [ "$1" = "{hypothesis_id}" ]; then'
                start = train_script.rindex(marker)
                end = train_script.find("\nelif ", start + len(marker))
                branch = train_script[start : end if end >= 0 else None]
                self.assertEqual(
                    {name for name in all_names if name in branch}, set(expected_names)
                )
        self.assertIn('"evidence_kind":', train_script)
        self.assertIn("inventory_readiness", train_script)
        self.assertIn('"product_confirmation":', train_script)

    def test_af240_hypotheses_are_confirmed_inventory_candidates_with_distinct_commands(self) -> None:
        hypotheses = yaml.safe_load(
            (REPO_ROOT / "docs/status/climb/hypotheses.yaml").read_text()
        )["hypotheses"]
        indexed = {item["id"]: item for item in hypotheses}
        commands = []
        for hypothesis_id, expected_names in AF240_READINESS_TESTS.items():
            item = indexed[hypothesis_id]
            self.assertEqual(item["status"], "confirmed")
            self.assertEqual(item["evidence_kind"], "inventory_readiness")
            self.assertIs(item["product_confirmation"], False)
            self.assertEqual(item["results"][-1]["local"], 4)
            self.assertEqual(item["results"][-1]["verdict"], "confirmed 4/4")
            command = item["verification_command"]
            self.assertEqual(
                {name for name in expected_names if name in command}, set(expected_names)
            )
            self.assertNotIn("test_af240_inventory_maps_complete_source_surface", command)
            commands.append(command)
        self.assertEqual(len(commands), len(set(commands)))

    def test_af230_and_af240_result_sessions_match_the_run_ledger(self) -> None:
        hypotheses = yaml.safe_load(
            (REPO_ROOT / "docs/status/climb/hypotheses.yaml").read_text()
        )["hypotheses"]
        with (REPO_ROOT / "docs/status/climb/runs.csv").open(newline="") as handle:
            runs = {row["run_id"]: row for row in csv.DictReader(handle)}

        for item in hypotheses:
            if item.get("work_package_id") not in {"AF-230", "AF-240"}:
                continue
            for result in item["results"]:
                with self.subTest(hypothesis=item["id"], run=result["run"]):
                    ledger = runs[result["run"]]
                    self.assertEqual(ledger["hypothesis_id"], item["id"])
                    self.assertEqual(ledger["session"], result["session"])

    def test_af240_session_name_stays_within_batch_package_scope(self) -> None:
        hypotheses = yaml.safe_load(
            (REPO_ROOT / "docs/status/climb/hypotheses.yaml").read_text()
        )["hypotheses"]
        target = (REPO_ROOT / "docs/status/climb/session-target.md").read_text()
        for item in hypotheses:
            if item.get("work_package_id") == "AF-240":
                self.assertEqual(
                    item["results"][-1]["session"],
                    "2026-07-15-af-240-batch-evaluation-export-parity",
                )
        self.assertNotIn("full source-parity", target.lower())

    def test_af240_local_eval_reports_batch_parity_dimensions(self) -> None:
        eval_script = (REPO_ROOT / "tools/climb/eval-local.sh").read_text()
        all_names = {name for names in AF240_READINESS_TESTS.values() for name in names}
        for hypothesis_id, expected_names in AF240_READINESS_TESTS.items():
            marker = f"    {hypothesis_id})"
            start = eval_script.index(marker)
            end = eval_script.find("\n    AF-240-H-", start + len(marker))
            if end < 0:
                end = eval_script.find("\n    *)", start + len(marker))
            branch = eval_script[start:end]
            self.assertEqual(
                {name for name in all_names if name in branch}, set(expected_names)
            )
        expected_dimensions = {
            "AF-240-H-001": {
                "dataset_contract",
                "prompt_contract",
                "retrieval_parsing",
                "ir_metric",
            },
            "AF-240-H-002": {
                "bounded_concurrency",
                "durable_query_state",
                "exact_reuse",
                "compatible_resume",
            },
            "AF-240-H-003": {
                "judge_retry_cache",
                "aggregate_metrics",
                "detailed_analysis",
                "reproducible_figures",
            },
            "AF-240-H-004": {
                "bcplus_qa_export",
                "corpus_exports",
                "launcher_profiles",
                "installed_resources",
            },
        }
        for hypothesis_id, dimensions in expected_dimensions.items():
            with self.subTest(hypothesis_id=hypothesis_id), tempfile.TemporaryDirectory() as temp_dir:
                run_dir = Path(temp_dir)
                env = os.environ.copy()
                env["DCI_CLIMB_HYPOTHESIS_ID"] = hypothesis_id
                result = subprocess.run(
                    ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                )

                self.assertEqual(result.returncode, 0, result.stderr)
                evaluation = json.loads((run_dir / "local-eval.json").read_text())
                self.assertEqual(evaluation["hypothesis_id"], hypothesis_id)
                self.assertEqual(evaluation["total"], 4)
                self.assertEqual(set(evaluation["per_task"]), dimensions)
                self.assertEqual(evaluation["evidence_kind"], "inventory_readiness")
                self.assertEqual(evaluation["candidate_status"], "pending")
                self.assertIs(evaluation["product_confirmation"], False)

    def test_af250_governance_uses_the_exact_package_and_session(self) -> None:
        hypotheses = yaml.safe_load(
            (REPO_ROOT / "docs/status/climb/hypotheses.yaml").read_text()
        )["hypotheses"]
        indexed = {item["id"]: item for item in hypotheses}
        commands: list[str] = []
        for cycle, (hypothesis_id, selectors) in enumerate(
            AF250_MATRIX_TESTS.items(), start=80
        ):
            item = indexed[hypothesis_id]
            self.assertEqual(item["work_package_id"], "AF-250")
            self.assertEqual(item["status"], "confirmed")
            self.assertEqual(
                len(item.get("results", [])), 2 if hypothesis_id == "AF-250-H-005" else 1
            )
            result = item["results"][0]
            self.assertEqual(result["session"], "2026-07-15-af-250-product-acceptance-matrix")
            self.assertEqual(result["cycle"], cycle)
            self.assertEqual(result["local"], 4)
            self.assertEqual(result["verdict"], "confirmed 4/4")
            command = item["verification_command"]
            self.assertEqual({name for name in selectors if name in command}, set(selectors))
            commands.append(command)
        self.assertEqual(len(commands), len(set(commands)))
        recovery = indexed["AF-250-H-005"]["results"][-1]
        self.assertEqual(recovery["cycle"], 85)
        self.assertEqual(recovery["local"], 4)
        self.assertEqual(recovery["verdict"], "confirmed 4/4")

        worklist = (REPO_ROOT / "docs/status/WORKLIST.md").read_text()
        af250 = worklist.split("## AF-250 — Product acceptance matrix", 1)[1]
        af250 = af250.split("\n## ", 1)[0]
        self.assertIn("- Status: completed", af250)

        self.assertNotIn("Commit the cohesive AF-250", worklist)

    def test_af250_train_registers_distinct_executable_selectors(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        all_names = {name for names in AF250_MATRIX_TESTS.values() for name in names}
        self.assertEqual(len(all_names), 4 * len(AF250_MATRIX_TESTS))
        for hypothesis_id, selectors in AF250_MATRIX_TESTS.items():
            marker = f'elif [ "$1" = "{hypothesis_id}" ]; then'
            start = train_script.rindex(marker)
            end = train_script.find("\nelif ", start + len(marker))
            branch = train_script[start : end if end >= 0 else None]
            self.assertEqual({name for name in all_names if name in branch}, set(selectors))

    def test_af250_local_eval_dimensions_have_distinct_executable_selectors(self) -> None:
        eval_script = (REPO_ROOT / "tools/climb/eval-local.sh").read_text()
        all_names = {name for names in AF250_MATRIX_TESTS.values() for name in names}
        seen_dimensions: set[str] = set()
        for hypothesis_id, selectors in AF250_MATRIX_TESTS.items():
            marker = f"    {hypothesis_id})"
            start = eval_script.index(marker)
            end = eval_script.find("\n    AF-", start + len(marker))
            if end < 0:
                end = eval_script.find("\n    *)", start + len(marker))
            branch = eval_script[start:end]
            self.assertEqual({name for name in all_names if name in branch}, set(selectors))
            dimensions = set(re.findall(r'^\s*(?:first|second|third|fourth)_dimension="([^"]+)"', branch, re.M))
            self.assertEqual(len(dimensions), 4)
            self.assertTrue(seen_dimensions.isdisjoint(dimensions))
            seen_dimensions.update(dimensions)

    def test_af250_local_eval_executes_each_governed_dimension(self) -> None:
        expected_dimensions = {
            "AF-250-H-001": {"product_rows", "source_entries", "asterion_entries", "local_selectors"},
            "AF-250-H-002": {"stable_semantics", "independent_entries", "batch_inventory", "no_placeholders"},
            "AF-250-H-003": {"installed_rows", "wheel_boundary", "application_assembly", "model_free_install"},
            "AF-250-H-004": {"supported_rows", "provider_case_ids", "provider_skip", "schema_inventory"},
            "AF-250-H-005": {"manifest_binding", "successful_cases", "body_free_evidence", "private_native_evidence"},
        }
        for hypothesis_id, dimensions in expected_dimensions.items():
            with self.subTest(hypothesis_id=hypothesis_id), tempfile.TemporaryDirectory() as temp_dir:
                run_dir = Path(temp_dir)
                env = os.environ.copy()
                env["DCI_CLIMB_HYPOTHESIS_ID"] = hypothesis_id
                result = subprocess.run(
                    ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                evaluation = json.loads((run_dir / "local-eval.json").read_text())
                self.assertEqual(evaluation["hypothesis_id"], hypothesis_id)
                self.assertEqual(evaluation["total"], 4)
                self.assertEqual(set(evaluation["per_task"]), dimensions)
                self.assertEqual(
                    evaluation["evidence_kind"], "product_matrix_readiness"
                )
                self.assertEqual(evaluation["candidate_status"], "pending")
                self.assertIs(evaluation["product_confirmation"], False)

    def test_af310_train_registers_context_contract_hypothesis(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-310-H-001", train_script)
        self.assertIn("tests.test_asterion_dci_context_profiles", train_script)

    def test_af310_h001_eval_reports_four_contract_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-310-H-001"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-310-H-001")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "closed_profiles",
                    "stable_identity",
                    "invalid_values",
                    "boundary_validation",
                },
            )

    def test_af310_train_registers_live_context_hypothesis(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-310-H-002", train_script)
        self.assertIn("dci-context-extension", train_script)

    def test_af310_h002_eval_reports_four_live_context_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-310-H-002"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-310-H-002")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "canonical_profiles",
                    "exact_truncation",
                    "live_retention",
                    "summary_failure_semantics",
                },
            )

    def test_af310_train_registers_packaged_transport_hypothesis(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-310-H-003", train_script)
        self.assertIn("test_asterion_dci_context_extension", train_script)
        self.assertIn("test_asterion_dci_pi_rpc", train_script)

    def test_af310_h003_eval_reports_four_packaged_transport_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-310-H-003"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-310-H-003")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "resource_integrity",
                    "literal_transport",
                    "immutable_resume",
                    "isolated_wheel",
                },
            )

    def test_af310_train_registers_product_surface_hypothesis(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-310-H-004", train_script)
        self.assertIn("test_asterion_dci_application_executor", train_script)
        self.assertIn("test_asterion_dci_batch", train_script)

    def test_af310_h004_eval_reports_four_product_surface_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-310-H-004"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-310-H-004")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "closed_cli",
                    "batch_identity",
                    "application_mapping",
                    "body_free_projection",
                },
            )

    def test_af310_train_registers_bounded_context_acceptance_hypothesis(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-310-H-005", train_script)
        self.assertIn("test_asterion_dci_verification", train_script)
        self.assertIn("test_asterion_dci_pi_rpc", train_script)

    def test_af310_h005_eval_reports_four_bounded_acceptance_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-310-H-005"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-310-H-005")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "model_free_boundary",
                    "level3_semantics",
                    "level4_semantics",
                    "body_free_evidence",
                },
            )

    def test_af320_train_registers_paper_inventory_hypothesis(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()

        self.assertIn("AF-320-H-001", train_script)
        self.assertIn("tests.test_asterion_dci_paper_benchmarks", train_script)

    def test_af320_h001_eval_reports_four_inventory_dimensions(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-320-H-001"

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-320-H-001")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                set(evaluation["per_task"]),
                {
                    "closed_inventory",
                    "scope_identity",
                    "bounded_ndcg",
                    "adapter_gate",
                },
            )

    def test_af320_resolution_hypotheses_have_four_dimension_adapters(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        expected = {
            "AF-320-H-002": {
                "coverage_contract",
                "localization_aggregation",
                "retained_unavailable",
                "batch_analysis",
            },
            "AF-320-H-003": {
                "conservative_alignment",
                "byte_exact_identity",
                "reuse_invalidation",
                "body_free_projection",
            },
        }
        for hypothesis_id, dimensions in expected.items():
            with self.subTest(hypothesis_id=hypothesis_id), tempfile.TemporaryDirectory() as temp_dir:
                self.assertIn(hypothesis_id, train_script)
                run_dir = Path(temp_dir)
                env = os.environ.copy()
                env["DCI_CLIMB_HYPOTHESIS_ID"] = hypothesis_id
                result = subprocess.run(
                    ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                    cwd=REPO_ROOT,
                    env=env,
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                evaluation = json.loads((run_dir / "local-eval.json").read_text())
                self.assertEqual(evaluation["hypothesis_id"], hypothesis_id)
                self.assertEqual(evaluation["total"], 4)
                self.assertEqual(set(evaluation["per_task"]), dimensions)

    def test_af340_train_has_exact_closed_membership_and_paradigms(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        expected = {
            "AF-340-H-001": "dci-reproduction-evidence",
            "AF-340-H-002": "dci-reproduction-statistics",
            "AF-340-H-003": "dci-reproduction-local-coordinator",
            "AF-340-H-004": "dci-reproduction-bounded-evidence",
        }
        allowlist = re.search(
            r'^case "\$1" in\n    ([^\n]+)\) ;;$', train_script, re.M
        )

        self.assertIsNotNone(allowlist)
        af340_members = [
            item
            for item in allowlist.group(1).split("|")
            if item.startswith("AF-340-")
        ]
        self.assertEqual(af340_members, list(expected))

        for hypothesis_id, paradigm in expected.items():
            with self.subTest(hypothesis_id=hypothesis_id):
                branches = _shell_if_branch_bodies(train_script, hypothesis_id)
                self.assertEqual(len(branches), 2)
                self.assertEqual(
                    branches[0].strip(), f'paradigm="{paradigm}"'
                )

    def test_af340_session_target_distinguishes_governed_from_active_hypotheses(self) -> None:
        target = (REPO_ROOT / "docs/status/climb/session-target.md").read_text()

        self.assertNotIn("Four active governed hypotheses", target)
        self.assertIn("Four governed hypotheses", target)
        self.assertIn("H-001 through H-004 are confirmed", target)
        self.assertIn("no AF-340 hypothesis remains active", target)
        self.assertNotIn("only AF-340-H-004 remains active", target)

    def test_af340_eval_branches_have_exact_dimensions_and_selectors(self) -> None:
        eval_script = (REPO_ROOT / "tools/climb/eval-local.sh").read_text()
        expected = {
            "AF-340-H-001": (
                (
                    "immutable_rows",
                    "strict_manifest",
                    "status_preservation",
                    "body_free_schema",
                ),
                (
                    "tests.test_asterion_dci_reproduction.ReproductionManifestTests.test_manifest_is_frozen_stably_ordered_and_body_free",
                    "tests.test_asterion_dci_reproduction.ReproductionManifestTests.test_manifest_rejects_duplicate_or_missing_query_ids",
                    "tests.test_asterion_dci_reproduction.ReproductionManifestTests.test_manifest_rejects_exclusion_without_versioned_reason",
                    "tests.test_asterion_dci_reproduction.ReproductionManifestTests.test_manifest_rejects_unknown_body_or_credential_fields_at_any_depth",
                ),
            ),
            "AF-340-H-002": (
                (
                    "paired_accuracy",
                    "paired_ndcg",
                    "deterministic_estimator",
                    "target_comparison_cli",
                ),
                (
                    "tests.test_asterion_dci_reproduction.ReproductionStatisticsTests.test_accuracy_minus_point_zero_four_passes_and_is_deterministic",
                    "tests.test_asterion_dci_reproduction.ReproductionStatisticsTests.test_ndcg_threshold_fixtures_use_lower_confidence_bound",
                    "tests.test_asterion_dci_reproduction.ReproductionStatisticsTests.test_estimator_sample_digest_binds_values_status_and_evidence",
                    "tests.test_asterion_dci_reproduction.ReproductionStatisticsTests.test_target_report_binds_exact_profile_target_and_runtime",
                ),
            ),
            "AF-340-H-003": (
                (
                    "literal_local_matrix",
                    "zero_operations",
                    "private_output_boundary",
                    "documented_commands",
                ),
                (
                    "tests.test_af340_reproduction_verifier.Af340ReproductionVerifierTests.test_local_exact_matrix_has_zero_provider_operations",
                    "tests.test_af340_reproduction_verifier.Af340ReproductionVerifierTests.test_local_exact_matrix_has_zero_provider_operations",
                    "tests.test_af340_reproduction_verifier.Af340ReproductionVerifierTests.test_failure_report_preserves_counts_without_command_or_output_bodies",
                    "tests.test_asterion_documentation",
                ),
            ),
            "AF-340-H-004": (
                (
                    "bounded_original_pi",
                    "bounded_asterion_pi",
                    "bounded_claude_minimax",
                    "retained_body_free_evidence",
                ),
                (
                    "bounded_original_pi",
                    "bounded_asterion_pi",
                    "bounded_claude_minimax",
                    "retained_body_free_evidence",
                ),
            ),
        }

        for hypothesis_id, (dimensions, selectors) in expected.items():
            with self.subTest(hypothesis_id=hypothesis_id):
                branch = _shell_case_branch(eval_script, hypothesis_id)
                assignments = dict(re.findall(r'^        (\w+)="([^"]+)"$', branch, re.M))
                self.assertEqual(
                    tuple(assignments[f"{name}_dimension"] for name in (
                        "first", "second", "third", "fourth"
                    )),
                    dimensions,
                )
                self.assertEqual(
                    tuple(assignments[name] for name in (
                        "immutable_test", "repeat_test", "dirty_test", "override_test"
                    )),
                    selectors,
                )
                expected_keys = {
                    "first_dimension",
                    "second_dimension",
                    "third_dimension",
                    "fourth_dimension",
                    "immutable_test",
                    "repeat_test",
                    "dirty_test",
                    "override_test",
                }
                if hypothesis_id == "AF-340-H-004":
                    expected_keys.add("dimension_runner")
                    self.assertEqual(
                        assignments["dimension_runner"],
                        "run_af340_evidence_dimension",
                    )
                self.assertEqual(set(assignments), expected_keys)

    def test_af340_train_branches_use_exact_tracked_commands(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        expected_modules = {
            "AF-340-H-001": {
                "tests.test_asterion_dci_reproduction",
            },
            "AF-340-H-002": {
                "tests.test_asterion_dci_reproduction",
                "tests.test_asterion_dci_paper_resolution_analysis",
                "tests.test_asterion_dci_paper_product",
            },
            "AF-340-H-003": {
                "tests.test_af340_reproduction_verifier",
                "tests.test_original_readme_acceptance",
                "tests.test_asterion_documentation",
            },
            "AF-340-H-004": set(),
        }

        for hypothesis_id, modules in expected_modules.items():
            with self.subTest(hypothesis_id=hypothesis_id):
                branch = _shell_if_branch_bodies(train_script, hypothesis_id)[1]
                self.assertEqual(
                    set(re.findall(r"tests\.test_[a-zA-Z0-9_]+", branch)),
                    modules,
                )
                verifier_calls = re.findall(
                    r"uv run python tools/verify_af340_reproduction\.py [^\n\\]+",
                    branch,
                )
                if hypothesis_id == "AF-340-H-004":
                    self.assertEqual(
                        verifier_calls,
                        ["uv run python tools/verify_af340_reproduction.py inspect "],
                    )
                else:
                    self.assertEqual(verifier_calls, [])

    def test_af340_h004_eval_only_inspects_retained_evidence(self) -> None:
        train_script = (REPO_ROOT / "tools/climb/train.sh").read_text()
        eval_script = (REPO_ROOT / "tools/climb/eval-local.sh").read_text()
        h004_eval = _shell_case_branch(eval_script, "AF-340-H-004")
        runner = re.search(
            r"run_af340_evidence_dimension\(\) \{\n(.*?)\n\}",
            eval_script,
            re.S,
        )

        self.assertIsNotNone(runner)
        self.assertIn("inspect", runner.group(1))
        self.assertNotIn("inspect-full", runner.group(1))
        self.assertEqual(runner.group(1).count('--report "$AF340_'), 2)
        self.assertIn("AF340_PI_REPORT", runner.group(1))
        self.assertIn("AF340_CLAUDE_MINIMAX_REPORT", runner.group(1))
        self.assertNotIn("AF340_CLAUDE_SUBSCRIPTION_REPORT", runner.group(1))
        self.assertNotIn('elif [ "$1" = "AF-340-H-005" ]', train_script)
        self.assertNotIn("AF-340-H-005)", eval_script)
        self.assertNotIn("AF340_FULL_REPORT", runner.group(1))
        self.assertNotIn('--dimension "$dimension"', runner.group(1))
        self.assertNotIn("verify_af340_reproduction.py bounded", runner.group(1))
        self.assertNotIn('="bounded"', h004_eval)
        self.assertEqual(
            train_script.count("verify_af340_reproduction.py bounded")
            + eval_script.count("verify_af340_reproduction.py bounded"),
            0,
        )

    def test_af340_h001_eval_is_provider_free_and_scores_four(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            run_dir = Path(temp_dir)
            env = os.environ.copy()
            env["DCI_CLIMB_HYPOTHESIS_ID"] = "AF-340-H-001"
            env.pop("OPENAI_API_KEY", None)
            env.pop("ANTHROPIC_API_KEY", None)
            env.pop("DEEPSEEK_API_KEY", None)
            env.pop("MINIMAX_API_KEY", None)

            result = subprocess.run(
                ["bash", "tools/climb/eval-local.sh", str(run_dir)],
                cwd=REPO_ROOT,
                env=env,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            evaluation = json.loads((run_dir / "local-eval.json").read_text())
            self.assertEqual(evaluation["hypothesis_id"], "AF-340-H-001")
            self.assertEqual(evaluation["total"], 4)
            self.assertEqual(
                evaluation["per_task"],
                {
                    "immutable_rows": 1,
                    "strict_manifest": 1,
                    "status_preservation": 1,
                    "body_free_schema": 1,
                },
            )

    def test_af340_h001_shell_syntax_and_scope_preflight_pass(self) -> None:
        syntax = subprocess.run(
            ["bash", "-n", "tools/climb/train.sh", "tools/climb/eval-local.sh"],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )
        scope = subprocess.run(
            [
                "python3",
                "tools/project_scope_check.py",
                "--climb-hypothesis",
                "AF-340-H-001",
            ],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
        )

        self.assertEqual(syntax.returncode, 0, syntax.stderr)
        self.assertEqual(scope.returncode, 0, scope.stderr)

    def test_af310_h005_provider_binding_is_digest_bound_and_body_free(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            state_dir = root / "climb"
            state_dir.mkdir()
            shutil.copy(
                REPO_ROOT / "docs/status/climb/hypotheses.yaml",
                state_dir / "hypotheses.yaml",
            )
            hypotheses = state_dir / "hypotheses.yaml"
            hypotheses.write_text(
                re.sub(
                    r"    provider_evidence:\n      path: provider-evidence/af-310-h-005.json\n"
                    r"      sha256: [0-9a-f]{64}\n      report_sha256: [0-9a-f]{64}\n?",
                    "",
                    hypotheses.read_text(),
                )
            )
            manifest = json.loads(
                (
                    REPO_ROOT
                    / "asterion/src/asterion/dci/resources/pi/context-extension-manifest.json"
                ).read_text()
            )
            revision = (REPO_ROOT / "pi-revision.txt").read_text().strip()
            case = {
                "profile": "level3",
                "compactions": 1,
                "preserved_turns": 12,
                "summary_attempts": 0,
                "summary_successes": 0,
                "summary_suppressed": False,
                "artifact_digests": {
                    "context-policy.json": "",
                    "events.jsonl": "",
                    "state.json": "",
                },
            }
            report = {
                "schema": "asterion.dci.context-acceptance/v1",
                "mode": "bounded-provider-backed",
                "provider": "fixture-provider",
                "model": "fixture-model",
                "pi_revision": revision,
                "extension_version": manifest["extension_version"],
                "contract_version": manifest["contract_version"],
                "extension_sha256": manifest["sha256"],
                "corpus_fixture_sha256": "d" * 64,
                "provider_operations": 2,
                "user_turns_per_case": 13,
                "api_request_multiplicity": "externally ambiguous",
                "full_dataset_ran": False,
                "cases": [
                    case,
                    {
                        **case,
                        "artifact_digests": dict(case["artifact_digests"]),
                        "profile": "level4",
                        "preserved_turns": None,
                        "summary_attempts": 1,
                        "summary_successes": 1,
                    },
                ],
            }
            for profile_case in report["cases"]:
                artifact_dir = root / profile_case["profile"]
                artifact_dir.mkdir()
                for name in ("context-policy.json", "events.jsonl", "state.json"):
                    artifact = artifact_dir / name
                    artifact.write_bytes(f"{profile_case['profile']}:{name}".encode())
                    artifact.chmod(0o600)
                    profile_case["artifact_digests"][name] = hashlib.sha256(
                        artifact.read_bytes()
                    ).hexdigest()
            report_path = root / "context-acceptance.json"
            report_path.write_text(json.dumps(report))
            report_path.chmod(0o600)
            clean_pi = root / "clean-pi"
            subprocess.run(
                ["git", "clone", "-q", "--no-local", str(REPO_ROOT / "pi"), str(clean_pi)],
                check=True,
            )

            command = [
                "uv", "run", "--project", "asterion", "python",
                "tools/climb/bind-provider-evidence.py",
                "--report", str(report_path),
                "--state-dir", str(state_dir),
                "--pi-dir", str(clean_pi),
            ]
            insecure = list(command)
            report_path.chmod(0o644)
            rejected = subprocess.run(
                insecure, cwd=REPO_ROOT, text=True, capture_output=True
            )
            self.assertNotEqual(rejected.returncode, 0)
            report_path.chmod(0o600)

            report_link = root / "report-link.json"
            report_link.symlink_to(report_path)
            linked = list(command)
            linked[linked.index("--report") + 1] = str(report_link)
            rejected = subprocess.run(
                linked, cwd=REPO_ROOT, text=True, capture_output=True
            )
            self.assertNotEqual(rejected.returncode, 0)

            artifact = root / "level3/events.jsonl"
            original_artifact = artifact.read_bytes()
            artifact.write_bytes(b"tampered")
            artifact.chmod(0o600)
            rejected = subprocess.run(
                command, cwd=REPO_ROOT, text=True, capture_output=True
            )
            self.assertNotEqual(rejected.returncode, 0)
            artifact.write_bytes(original_artifact)
            artifact.chmod(0o600)

            artifact_backup = root / "events-backup.jsonl"
            artifact.rename(artifact_backup)
            artifact.symlink_to(artifact_backup)
            rejected = subprocess.run(
                command, cwd=REPO_ROOT, text=True, capture_output=True
            )
            self.assertNotEqual(rejected.returncode, 0)
            artifact.unlink()
            artifact_backup.rename(artifact)

            dirty_command = [
                *command[:-1], str(REPO_ROOT / "pi")
            ]
            dirty = subprocess.run(
                dirty_command, cwd=REPO_ROOT, text=True, capture_output=True
            )
            self.assertNotEqual(dirty.returncode, 0)
            self.assertFalse((state_dir / "provider-evidence").exists())

            result = subprocess.run(
                command,
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            updated = (state_dir / "hypotheses.yaml").read_text()
            self.assertIn("provider_evidence:", updated)
            evidence_path = state_dir / "provider-evidence/af-310-h-005.json"
            evidence = json.loads(evidence_path.read_text())
            self.assertEqual(evidence["provider_operations"], 2)
            self.assertEqual(evidence["cases"][0]["preserved_turns"], 12)
            serialized = evidence_path.read_text() + updated
            self.assertNotIn("fixture-provider", serialized)
            self.assertNotIn(str(root), serialized)

            before = (evidence_path.read_bytes(), hypotheses.read_bytes())
            repeated = subprocess.run(
                result.args, cwd=REPO_ROOT, text=True, capture_output=True
            )
            self.assertEqual(repeated.returncode, 0, repeated.stderr)
            self.assertEqual(before, (evidence_path.read_bytes(), hypotheses.read_bytes()))

            report["provider"] = "different-provider"
            report_path.write_text(json.dumps(report))
            report_path.chmod(0o600)
            conflicting = subprocess.run(
                result.args, cwd=REPO_ROOT, text=True, capture_output=True
            )
            self.assertNotEqual(conflicting.returncode, 0)
            self.assertEqual(before, (evidence_path.read_bytes(), hypotheses.read_bytes()))


if __name__ == "__main__":
    unittest.main()
