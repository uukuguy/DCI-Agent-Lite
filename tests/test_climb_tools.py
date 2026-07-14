from __future__ import annotations

import csv
import ast
import copy
import importlib
import json
import os
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
    "asterion.dci.datasets",
    "asterion.dci.evaluation",
    "asterion.dci.export",
    "asterion.dci.judge",
    "asterion.dci.metrics",
    "asterion.dci.run",
    "asterion.dci.resources.batch-profiles.json",
    "scripts.asterion",
}
AF240_FORBIDDEN = {"placeholder", "tbd", "todo", "unsupported", "unknown", "n/a"}
AF240_SOURCE_METRICS = {
    "agent_usage.cache_read_tokens",
    "agent_usage.cache_write_tokens",
    "agent_usage.cost_cache_read",
    "agent_usage.cost_cache_write",
    "agent_usage.cost_input",
    "agent_usage.cost_output",
    "agent_usage.cost_total",
    "agent_usage.input_tokens",
    "agent_usage.output_tokens",
    "agent_usage.total_tokens",
    "analysis.cost_efficiency.agent_tokens_per_correct",
    "analysis.cost_efficiency.cost_per_correct_usd",
    "analysis.incorrect_queries.overall_cost_total",
    "analysis.incorrect_queries.tool_call_count",
    "analysis.incorrect_queries.turn_count",
    "analysis.incorrect_queries.wall_time_seconds",
    "analysis.per_query.agent_cache_read_tokens",
    "analysis.per_query.agent_cost_total",
    "analysis.per_query.agent_input_tokens",
    "analysis.per_query.agent_output_tokens",
    "analysis.per_query.agent_total_tokens",
    "analysis.per_query.answer_char_count",
    "analysis.per_query.event_count",
    "analysis.per_query.gold_doc_count",
    "analysis.per_query.judge_cost_total",
    "analysis.per_query.judge_total_tokens",
    "analysis.per_query.launcher_wall_time_seconds",
    "analysis.per_query.non_tool_time_seconds",
    "analysis.per_query.overall_cost_total",
    "analysis.per_query.question_char_count",
    "analysis.per_query.question_word_count",
    "analysis.per_query.request_count",
    "analysis.per_query.tool_call_count",
    "analysis.per_query.tool_counts.*",
    "analysis.per_query.tool_durations.*",
    "analysis.per_query.tool_error_count",
    "analysis.per_query.tool_time_seconds",
    "analysis.per_query.tool_time_share",
    "analysis.per_query.turn_count",
    "analysis.per_query.wall_time_seconds",
    "analysis.rankings.highest_token_queries.value",
    "analysis.rankings.most_expensive_queries.value",
    "analysis.rankings.most_tool_heavy_queries.value",
    "analysis.rankings.slowest_queries.value",
    "analysis.tool_summary.accuracy_when_used",
    "analysis.tool_summary.avg_calls_per_query",
    "analysis.tool_summary.avg_calls_when_used",
    "analysis.tool_summary.avg_duration_per_call_seconds",
    "analysis.tool_summary.correct_when_used",
    "analysis.tool_summary.queries_used",
    "analysis.tool_summary.queries_used_rate",
    "analysis.tool_summary.total_calls",
    "analysis.tool_summary.total_duration_seconds",
    "analysis.tool_summary.total_error_count",
    "numeric_summary.count",
    "numeric_summary.max",
    "numeric_summary.mean",
    "numeric_summary.median",
    "numeric_summary.min",
    "numeric_summary.p10",
    "numeric_summary.p25",
    "numeric_summary.p75",
    "numeric_summary.p90",
    "judge_cost.cached_input_cost",
    "judge_cost.input_cost",
    "judge_cost.output_cost",
    "judge_cost.total_cost",
    "judge_usage.input_tokens",
    "judge_usage.input_tokens_details.cached_tokens",
    "judge_usage.output_tokens",
    "judge_usage.total_tokens",
    "query.event_count",
    "query.is_correct",
    "query.launcher_returncode",
    "query.launcher_wall_time_seconds",
    "query.ndcg_at_10",
    "query.non_tool_time_seconds",
    "query.request_count",
    "query.tool_time_seconds",
    "query.turn_count",
    "query.wall_time_seconds",
    "summary.accuracy.over_judged",
    "summary.accuracy.over_total",
    "summary.averages.agent_total_tokens",
    "summary.averages.judge_total_tokens",
    "summary.averages.overall_cost_total",
    "summary.averages.tool_call_count",
    "summary.averages.tool_time_seconds",
    "summary.averages.turn_count",
    "summary.averages.wall_time_seconds",
    "summary.counts.correct",
    "summary.counts.failed_runs",
    "summary.counts.incorrect_or_unjudged",
    "summary.counts.judged",
    "summary.counts.total",
    "summary.ndcg_at_10",
    "summary.totals.agent_cache_read_tokens",
    "summary.totals.agent_cache_write_tokens",
    "summary.totals.agent_cost_total",
    "summary.totals.agent_input_tokens",
    "summary.totals.agent_output_tokens",
    "summary.totals.agent_total_tokens",
    "summary.totals.event_count",
    "summary.totals.judge_cost_total",
    "summary.totals.judge_input_tokens",
    "summary.totals.judge_output_tokens",
    "summary.totals.judge_total_tokens",
    "summary.totals.launcher_wall_time_seconds",
    "summary.totals.non_tool_time_seconds",
    "summary.totals.overall_cost_total",
    "summary.totals.tool_call_count",
    "summary.totals.tool_error_count",
    "summary.totals.tool_time_seconds",
    "summary.totals.turn_count",
    "summary.totals.wall_time_seconds",
    "tool_metrics.by_tool.*.call_count",
    "tool_metrics.by_tool.*.duration_seconds",
    "tool_metrics.by_tool.*.error_count",
    "tool_metrics.call_count",
    "tool_metrics.duration_measured_call_count",
    "tool_metrics.duration_missing_call_count",
    "tool_metrics.duration_seconds",
    "tool_metrics.error_count",
}
AF240_SOURCE_METRICS |= {
    f"analysis.slices.*.{metric}.{statistic}"
    for metric in (
        "agent_total_tokens",
        "overall_cost_total",
        "question_word_count",
        "tool_call_count",
        "tool_error_count",
        "tool_time_seconds",
        "tool_time_share",
        "turn_count",
        "wall_time_seconds",
    )
    for statistic in (
        "count",
        "max",
        "mean",
        "median",
        "min",
        "p10",
        "p25",
        "p75",
        "p90",
    )
}
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
AF240_FUTURE_TEST_PREFIXES = {
    "AF-240 Task 1": "tests.test_asterion_dci_datasets.",
    "AF-240 Task 2": "tests.test_asterion_dci_evaluation.",
    "AF-240 Task 3": "tests.test_asterion_dci_batch.",
    "AF-240 Task 4": "tests.test_asterion_dci_analysis.",
    "AF-240 Task 5": "tests.test_asterion_dci_export.",
    "AF-240 Task 6": "tests.test_asterion_dci_batch_launchers.",
}


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


def _validate_af240_inventory(inventory: dict[str, object]) -> None:
    if inventory.get("schema") != "asterion.dci.batch-parity/v1":
        raise ValueError("unknown inventory schema")
    rows = inventory.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("inventory rows must be non-empty")
    row_ids: list[str] = []
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
        if target_task not in AF240_FUTURE_TEST_PREFIXES:
            raise ValueError(f"invalid target task in {row_id}")
        future_test = row.get("future_acceptance_test")
        if not (
            isinstance(future_test, str)
            and future_test.startswith("tests.")
            and ".test_" in future_test
        ):
            raise ValueError(f"invalid future acceptance test in {row_id}")
        if not future_test.startswith(AF240_FUTURE_TEST_PREFIXES[target_task]):
            raise ValueError(f"future acceptance test does not match target task in {row_id}")
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
    if mapped_metrics != AF240_SOURCE_METRICS:
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
        self.assertEqual(metric_names, AF240_SOURCE_METRICS)

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
            AF240_SOURCE_METRICS,
        )

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
            current_symbol="compute_detailed_analysis",
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
            if row["source_name"] != "numeric_summary.p10"
        ]
        mutations.append(metrics)
        target_task = copy.deepcopy(inventory)
        target_task["rows"][0]["target_task"] = "AF-240 Task 1"
        mutations.append(target_task)
        for index, mutation in enumerate(mutations):
            with self.subTest(mutation=index), self.assertRaises(ValueError):
                _validate_af240_inventory(mutation)


class ClimbToolTests(unittest.TestCase):
    def test_live_checkpoint_retains_scope_audit_package_marker(self) -> None:
        resume = (REPO_ROOT / "docs/status/RESUME-NEXT-SESSION.md").read_text()

        self.assertRegex(resume, r"(?m)^Active work package: AF-[0-9]+$")

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
        guide = (REPO_ROOT / "docs/operator/rust-executor.md").read_text()

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
        self.assertIn("npm --prefix packages/typescript/asterion-runtime test", train_script)

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
        self.assertIn("python -m unittest discover -v", train_script)
        self.assertIn("make test-typescript-host", train_script)
        self.assertIn("make test-rust-executor", train_script)
        self.assertIn("make check-rust-executor", train_script)

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
        self.assertIn("npm --prefix packages/typescript/asterion-runtime test", train_script)

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
        self.assertIn("python -m unittest discover -v", train_script)
        self.assertIn("npm --prefix packages/typescript/asterion-runtime ci", train_script)
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
        self.assertIn("python -m unittest discover -v", train_script)
        self.assertIn("npm --prefix packages/typescript/asterion-runtime ci", train_script)
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
        self.assertIn("python -m unittest discover -v", train_script)
        self.assertIn("npm --prefix packages/typescript/asterion-runtime ci", train_script)
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
        self.assertIn("packages/typescript/asterion-runtime", train_script)
        self.assertIn("packages/rust/controlled-executor", train_script)

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
        self.assertIn("python -m unittest discover -v", train_script)
        self.assertIn("packages/typescript/asterion-runtime ci", train_script)
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
        self.assertIn("python -m unittest discover -v", train_script)
        self.assertIn("packages/typescript/asterion-runtime ci", train_script)
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
        self.assertEqual(len(all_names), 16)
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

    def test_af240_hypotheses_are_pending_inventory_candidates_with_distinct_commands(self) -> None:
        hypotheses = yaml.safe_load(
            (REPO_ROOT / "docs/status/climb/hypotheses.yaml").read_text()
        )["hypotheses"]
        indexed = {item["id"]: item for item in hypotheses}
        commands = []
        for hypothesis_id, expected_names in AF240_READINESS_TESTS.items():
            item = indexed[hypothesis_id]
            self.assertEqual(item["status"], "pending")
            self.assertEqual(item["evidence_kind"], "inventory_readiness")
            self.assertIs(item["product_confirmation"], False)
            command = item["verification_command"]
            self.assertEqual(
                {name for name in expected_names if name in command}, set(expected_names)
            )
            self.assertNotIn("test_af240_inventory_maps_complete_source_surface", command)
            commands.append(command)
        self.assertEqual(len(commands), len(set(commands)))

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


if __name__ == "__main__":
    unittest.main()
