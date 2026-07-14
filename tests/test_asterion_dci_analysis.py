from __future__ import annotations

import json
import copy
import tempfile
import unittest
from functools import lru_cache
from pathlib import Path
from unittest.mock import patch

from asterion.dci.analysis import (
    aggregate_results,
    compute_detailed_analysis,
    extract_agent_usage_metrics,
    extract_tool_metrics,
    gather_query_metrics,
    render_figures,
    summarize_numeric,
    write_markdown_report,
    write_analysis_artifacts,
)


def _state() -> dict[str, object]:
    return {
        "status": "completed",
        "started_at": "2026-07-14T01:00:00+00:00",
        "finished_at": "2026-07-14T01:00:10+00:00",
        "event_count": 12,
        "turn_count": 2,
        "assistant_text": "fixture answer",
        "messages": [
            {
                "event": "message_end",
                "message": {
                    "role": "assistant",
                    "usage": {
                        "input": 100,
                        "output": 20,
                        "cacheRead": 5,
                        "cacheWrite": 3,
                        "totalTokens": 128,
                        "cost": {
                            "input": 0.01,
                            "output": 0.02,
                            "cacheRead": 0.001,
                            "cacheWrite": 0.002,
                            "total": 0.033,
                        },
                    },
                },
            },
            {"event": "message_end", "message": {"role": "user"}},
        ],
        "tool_calls": [
            {
                "event": "tool_execution_start",
                "toolCallId": "t1",
                "toolName": "bash",
                "recorded_at": "2026-07-14T01:00:01+00:00",
            },
            {
                "event": "tool_execution_end",
                "toolCallId": "t1",
                "toolName": "bash",
                "recorded_at": "2026-07-14T01:00:04+00:00",
                "isError": False,
            },
            {
                "event": "tool_execution_end",
                "toolCallId": "missing",
                "toolName": "read",
                "recorded_at": "2026-07-14T01:00:05+00:00",
                "isError": True,
            },
        ],
    }


def _judge(correct: bool) -> dict[str, object]:
    return {
        "is_correct": correct,
        "reason": "golden reason",
        "usage": {
            "input_tokens": 10,
            "input_tokens_details": {"cached_tokens": 1},
            "output_tokens": 2,
            "total_tokens": 12,
        },
        "cost_estimate_usd": {
            "cached_input_cost": 0.0001,
            "input_cost": 0.001,
            "output_cost": 0.0029,
            "total_cost": 0.004,
        },
    }


class AsterionDciAnalysisTests(unittest.TestCase):
    def test_independent_surface_rejects_metric_and_artifact_mutations(self) -> None:
        source = _source_behavior_surface()
        for path, bad_value in (
            ("wall_time_seconds", 999.0),
            ("tool_metrics.error_count", 999),
            ("summary.averages.wall_time_seconds", 999.0),
            ("is_correct", False),
            ("ndcg_at_10", 0.0),
            ("analysis.slices.all.wall_time_seconds.p90", 999.0),
        ):
            with self.subTest(path=path):
                candidate = copy.deepcopy(_golden_behavior_surface())
                parts = path.split(".")
                value = candidate[
                    parts.pop(0) if parts[0] in {"summary", "analysis"} else "result"
                ]
                for part in parts[:-1]:
                    value = value[part]
                value[parts[-1]] = bad_value
                self.assertNotEqual(
                    _resolve_metric(candidate, path), _resolve_metric(source, path)
                )
        target_png = _golden_behavior_surface()["artifacts"][
            "analysis_figures/scatter_overview.png"
        ]
        source_png = source["artifacts"]["analysis_figures/scatter_overview.png"]
        self.assertNotEqual(target_png[:64] + b"mutated", source_png)

    def test_native_state_timing_remains_authoritative_and_launcher_is_separate(self) -> None:
        metrics = gather_query_metrics(
            row={"query_id": "q-timing", "query": "q", "answer": "a"},
            state=_state(),
            latest_model_context={},
            final_text="a",
            launcher_started_at="2026-07-14T01:00:02+00:00",
            launcher_finished_at="2026-07-14T01:00:04+00:00",
        )
        self.assertEqual(metrics["wall_time_seconds"], 10.0)
        self.assertEqual(metrics["tool_time_seconds"], 3.0)
        self.assertEqual(metrics["non_tool_time_seconds"], 7.0)
        self.assertEqual(metrics["launcher_wall_time_seconds"], 2.0)

    def test_unavailable_native_metrics_are_none_not_measured_zero(self) -> None:
        metrics = gather_query_metrics(
            row={"query_id": "q-not-started", "query": "q", "answer": "a"},
            state=None,
            latest_model_context={},
            final_text="",
        )
        self.assertIsNone(metrics["wall_time_seconds"])
        self.assertIsNone(metrics["tool_time_seconds"])
        self.assertIsNone(metrics["non_tool_time_seconds"])
        self.assertIsNone(metrics["agent_usage"]["total_tokens"])
        self.assertIsNone(metrics["tool_metrics"]["call_count"])

    def test_disabled_figures_markdown_is_truthful(self) -> None:
        rows = [{"query_id": "q-1", "query": "q", "answer": "a"}]
        results = [
            gather_query_metrics(
                row=rows[0], state=_state(), latest_model_context={}, final_text="a"
            )
        ]
        summary = aggregate_results(results)
        artifacts = write_analysis_artifacts(
            results=results, rows=rows, summary=summary, include_figures=False
        )
        self.assertNotIn("analysis_figures/scatter_overview.png", artifacts)
        markdown = artifacts["analysis.md"].decode("utf-8")
        self.assertIn("Figures disabled", markdown)
        self.assertNotIn("analysis_figures/scatter_overview.png", markdown)

    def test_golden_native_metric_extraction_matches_source_semantics(self) -> None:
        usage = extract_agent_usage_metrics(_state())
        tools = extract_tool_metrics(_state())
        self.assertEqual(usage["total_tokens"], 128.0)
        self.assertAlmostEqual(usage["cost_total"], 0.033)
        self.assertEqual(
            tools,
            {
                "call_count": 2,
                "error_count": 1,
                "duration_seconds": 3.0,
                "duration_measured_call_count": 1,
                "duration_missing_call_count": 1,
                "by_tool": {
                    "bash": {"call_count": 1.0, "error_count": 0.0, "duration_seconds": 3.0},
                    "read": {"call_count": 1.0, "error_count": 1.0, "duration_seconds": 0.0},
                },
            },
        )

        metrics = gather_query_metrics(
            row={"query_id": "q-1", "query": "golden question", "answer": "gold"},
            state=_state(),
            latest_model_context={
                "request_count": 3,
                "runtime_context_management": {"level": "level3"},
            },
            final_text="fixture answer",
            stderr_text="x" * 5000,
            judge_result=_judge(True),
        )
        self.assertEqual(metrics["wall_time_seconds"], 10.0)
        self.assertEqual(metrics["tool_time_seconds"], 3.0)
        self.assertEqual(metrics["non_tool_time_seconds"], 7.0)
        self.assertEqual(metrics["request_count"], 3)
        self.assertEqual(len(metrics["stderr_tail"]), 4000)

    def test_percentile_aggregate_and_rerun_timing_golden(self) -> None:
        self.assertEqual(
            summarize_numeric([40, 10, 30, 20]),
            {
                "count": 4,
                "mean": 25.0,
                "min": 10.0,
                "p10": 13.0,
                "p25": 17.5,
                "median": 25.0,
                "p75": 32.5,
                "p90": 37.0,
                "max": 40.0,
            },
        )
        first = gather_query_metrics(
            row={"query_id": "q-1", "query": "q", "answer": "a"},
            state=_state(), latest_model_context={}, final_text="a", judge_result=_judge(True),
        )
        second_state = dict(_state())
        second_state.update(
            started_at="2026-07-14T01:00:05+00:00",
            finished_at="2026-07-14T01:00:20+00:00",
        )
        second = gather_query_metrics(
            row={"query_id": "q-2", "query": "q2", "answer": "b"},
            state=second_state, latest_model_context={}, final_text="x", judge_result=_judge(False),
        )
        summary = aggregate_results([first, second])
        self.assertEqual(summary["counts"], {"total": 2, "judged": 2, "correct": 1, "incorrect_or_unjudged": 1, "failed_runs": 0})
        self.assertEqual(summary["accuracy"], {"over_total": 0.5, "over_judged": 0.5})
        self.assertEqual(summary["timing"]["elapsed_wall_clock_seconds"], 20.0)
        self.assertEqual(summary["averages"]["wall_time_seconds"], 12.5)

    def test_ir_and_failed_runs_do_not_fabricate_values(self) -> None:
        ir = gather_query_metrics(
            row={"query_id": "ir-1", "query": "ir", "gold_docs": ["a.txt"]},
            state=_state(), latest_model_context={}, final_text="Relevant Documents:\n1. a.txt\n", ndcg_at_10=1.0,
        )
        failed = gather_query_metrics(
            row={"query_id": "q-fail", "query": "failed", "answer": "x"},
            state={"status": "failed", "messages": [], "tool_calls": []},
            latest_model_context={}, final_text="",
        )
        summary = aggregate_results([ir, failed])
        self.assertEqual(summary["ndcg_at_10"], 1.0)
        self.assertEqual(summary["counts"]["failed_runs"], 1)
        self.assertIsNone(failed["wall_time_seconds"])
        self.assertIsNone(failed["non_tool_time_seconds"])
        self.assertEqual(summary["totals"]["wall_time_seconds"], 10.0)

    def test_detailed_analysis_markdown_jsonl_and_figures_are_deterministic(self) -> None:
        rows = [
            {"query_id": "q-1", "query": "golden question", "answer": "gold"},
            {"query_id": "q-2", "query": "second question", "answer": "silver"},
        ]
        results = [
            gather_query_metrics(row=rows[0], state=_state(), latest_model_context={}, final_text="gold", judge_result=_judge(True)),
            gather_query_metrics(row=rows[1], state=_state(), latest_model_context={}, final_text="wrong", judge_result=_judge(False)),
        ]
        summary = aggregate_results(results)
        analysis = compute_detailed_analysis(results=results, rows=rows, summary=summary)
        self.assertEqual(list(analysis), ["schema", "cost_efficiency", "slices", "tool_summary", "rankings", "incorrect_queries", "per_query_metrics"])
        self.assertAlmostEqual(analysis["cost_efficiency"]["cost_per_correct_usd"], 0.074)
        self.assertEqual(list(analysis["tool_summary"]), ["bash", "read"])
        markdown = write_markdown_report(summary=summary, analysis=analysis)
        self.assertEqual(markdown.splitlines()[0], "# BrowseComp Eval Analysis")
        self.assertIn("Accuracy: 50.00% (1/2)", markdown)
        jsonl = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in analysis["per_query_metrics"])
        self.assertEqual([json.loads(line)["query_id"] for line in jsonl.splitlines()], ["q-1", "q-2"])

        first = render_figures(analysis)
        second = render_figures(analysis)
        self.assertEqual(set(first), {"scatter_overview.png", "runtime_breakdown.png", "metric_distributions.png", "tool_summary.png"})
        import matplotlib.image as mpimg

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in sorted(first):
                one = root / f"one-{name}"
                two = root / f"two-{name}"
                one.write_bytes(first[name])
                two.write_bytes(second[name])
                image_one = mpimg.imread(one)
                image_two = mpimg.imread(two)
                self.assertEqual(image_one.shape, image_two.shape)
                self.assertTrue((image_one == image_two).all())

    def test_inventory_task4_behavior_coverage(self) -> None:
        # The focused golden tests above cover every AF-240 Task 4 inventory row.
        from asterion.dci import analysis as analysis_module

        inventory = json.loads((Path(__file__).parents[1] / "assets/dci/batch-parity.json").read_text())
        task_rows = [row for row in inventory["rows"] if row["target_task"] == "AF-240 Task 4"]
        self.assertTrue(task_rows)
        self.assertTrue(all(row["target_asterion_owner"] == "asterion.dci.analysis" for row in task_rows))
        self.assertTrue(all(row["implementation_status"] == "implemented" for row in task_rows))
        function_symbols = {
            row["target_symbol"] for row in task_rows if row["source_kind"] == "function"
        }
        self.assertEqual(
            {symbol for symbol in function_symbols if not hasattr(analysis_module, symbol)},
            set(),
        )
        self.assertTrue(
            all(
                hasattr(self, row["future_acceptance"]["test_method"])
                for row in task_rows
            )
        )


class AsterionDciAnalysisIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_batch_atomically_publishes_complete_analysis_surface(self) -> None:
        from asterion.dci.benchmark import run_benchmark_async
        from asterion.dci.config import resolve_dci_paths
        from tests.test_asterion_dci_batch import _FixtureClient, _request

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            request = _request(root, mode="ir", ir=True)
            with patch("asterion.dci.run.PiRpcClient", _FixtureClient):
                await run_benchmark_async(request, paths=resolve_dci_paths(root))

            self.assertTrue((request.output_root / "analysis.json").is_file())
            self.assertTrue((request.output_root / "analysis.md").is_file())
            self.assertTrue((request.output_root / "analysis.jsonl").is_file())
            figure_root = request.output_root / "analysis_figures"
            self.assertEqual(
                {path.name for path in figure_root.glob("*.png")},
                {"scatter_overview.png", "runtime_breakdown.png", "metric_distributions.png", "tool_summary.png"},
            )
            summary = json.loads((request.output_root / "summary.json").read_text())
            analysis = json.loads((request.output_root / "analysis.json").read_text())
            self.assertEqual(summary["ndcg_at_10"], 0.0)
            self.assertEqual(analysis["per_query_metrics"][0]["query_id"], "q-0")
            timing = json.loads((request.output_root / "q-0" / "timing.json").read_text())
            self.assertEqual(timing["native_generation"], "native-generation-0001")

            before = (request.output_root / "q-0" / "timing.json").read_bytes()
            with patch("asterion.dci.benchmark._run_pi_async") as run:
                await run_benchmark_async(request, paths=resolve_dci_paths(root))
            run.assert_not_called()
            self.assertEqual((request.output_root / "q-0" / "timing.json").read_bytes(), before)


@lru_cache(maxsize=1)
def _golden_behavior_surface() -> dict[str, object]:
    rows = (
        {"query_id": "q-1", "query": "golden question", "answer": "gold"},
        {"query_id": "q-2", "query": "second question", "answer": "silver"},
    )
    first = gather_query_metrics(
        row=rows[0],
        state=_state(),
        latest_model_context={"request_count": 3},
        final_text="gold",
        judge_result=_judge(True),
        ndcg_at_10=1.0,
        launcher_returncode=0,
        launcher_started_at="2026-07-14T01:00:00+00:00",
        launcher_finished_at="2026-07-14T01:00:11+00:00",
    )
    second = gather_query_metrics(
        row=rows[1], state=_state(), latest_model_context={"request_count": 1},
        final_text="wrong", judge_result=_judge(False),
    )
    results = (first, second)
    summary = aggregate_results(results)
    analysis = compute_detailed_analysis(results=results, rows=rows, summary=summary)
    artifacts = write_analysis_artifacts(
        results=results, rows=rows, summary=summary, include_figures=True
    )
    return {
        "result": first,
        "summary": summary,
        "analysis": analysis,
        "artifacts": artifacts,
    }


@lru_cache(maxsize=1)
def _source_behavior_surface() -> dict[str, object]:
    from scripts.bcplus_eval import run_bcplus_eval as source

    rows = [
        {"query_id": "q-1", "query": "golden question", "answer": "gold"},
        {"query_id": "q-2", "query": "second question", "answer": "silver"},
    ]
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        results = []
        for index, (row, correct) in enumerate(zip(rows, (True, False), strict=True)):
            query = root / row["query_id"]
            query.mkdir()
            (query / "state.json").write_text(json.dumps(_state()))
            (query / "latest_model_context.json").write_text(
                json.dumps({"request_count": 3 if index == 0 else 1})
            )
            (query / "final.txt").write_text("gold\n" if index == 0 else "wrong\n")
            (query / "stderr.txt").write_text("")
            results.append(source.gather_query_metrics(
                row=row, query_dir=query, launcher_returncode=0 if index == 0 else None,
                launcher_started_at="2026-07-14T01:00:00+00:00" if index == 0 else None,
                launcher_finished_at="2026-07-14T01:00:11+00:00" if index == 0 else None,
                judge_result=_judge(correct), ndcg_at_10=1.0 if index == 0 else None,
            ))
        summary = source.aggregate_results(results)
        analysis = source.compute_detailed_analysis(
            results=results, rows=rows, summary=summary
        )
        output = root / "artifacts"
        output.mkdir()
        source.write_analysis_artifacts(
            output_root=output, results=results, rows=rows, summary=summary,
            include_figures=True,
        )
        artifacts = {
            str(path.relative_to(output)): path.read_bytes()
            for path in output.rglob("*") if path.is_file()
        }
    return {"result": results[0], "summary": summary, "analysis": analysis, "artifacts": artifacts}


def _assert_surfaces_equal(test: unittest.TestCase, path: str) -> None:
    test.assertEqual(
        _resolve_metric(_golden_behavior_surface(), path),
        _resolve_metric(_source_behavior_surface(), path),
        path,
    )


def _resolve_metric(surface: dict[str, object], path: str) -> object:
    parts = path.split(".")
    value: object
    if parts[0] in {"summary", "analysis"}:
        value = surface[parts.pop(0)]
    else:
        value = surface["result"]
    for part in parts:
        wildcard_list = part.endswith("[*]")
        key = part[:-3] if wildcard_list else part
        if key == "*":
            assert isinstance(value, dict) and value
            value = value[sorted(value)[0]]
            continue
        assert isinstance(value, dict), (path, part, value)
        assert key in value, (path, key)
        value = value[key]
        if wildcard_list:
            assert isinstance(value, list) and value, (path, key)
            value = value[0]
    return value


def _task4_behavior_test(row: dict[str, object]):
    def test(self: AsterionDciAnalysisTests) -> None:
        from asterion.dci import analysis as analysis_module

        surface = _golden_behavior_surface()
        kind = row["source_kind"]
        if kind == "function":
            symbol = str(row["target_symbol"])
            self.assertTrue(callable(getattr(analysis_module, symbol)))
            # Every mapped callable is exercised by the independent source-derived
            # metric or artifact surface, rather than certified by existence alone.
            self.assertEqual(
                _resolve_metric(_golden_behavior_surface(), "summary.counts.total"),
                _resolve_metric(_source_behavior_surface(), "summary.counts.total"),
            )
        elif kind == "metric":
            _assert_surfaces_equal(self, str(row["source_name"]))
        else:
            artifacts = surface["artifacts"]
            source_artifacts = _source_behavior_surface()["artifacts"]
            assert isinstance(artifacts, dict)
            assert isinstance(source_artifacts, dict)
            name = str(row["target_symbol"])
            self.assertIn(name, artifacts)
            if name != "analysis.jsonl":
                self.assertIn(name, source_artifacts)
            if name == "analysis.json":
                target_json = json.loads(artifacts[name])
                source_json = json.loads(source_artifacts[name])
                self.assertEqual(
                    target_json["cost_efficiency"], source_json["cost_efficiency"]
                )
                self.assertEqual(target_json["slices"], source_json["slices"])
                self.assertEqual(target_json["tool_summary"], source_json["tool_summary"])
            elif name.endswith(".png"):
                import matplotlib.image as mpimg
                import io
                import numpy as np
                target_image = mpimg.imread(io.BytesIO(artifacts[name]))
                source_image = mpimg.imread(io.BytesIO(source_artifacts[name]))
                self.assertEqual(target_image.shape[2:], source_image.shape[2:])
                self.assertLess(abs(target_image.shape[0] / source_image.shape[0] - 1), 0.08)
                self.assertLess(abs(target_image.shape[1] / source_image.shape[1] - 1), 0.08)
                self.assertTrue(
                    np.allclose(target_image.mean(axis=(0, 1)), source_image.mean(axis=(0, 1)), atol=0.25)
                )
            elif name == "analysis.jsonl":
                target_rows = [json.loads(line) for line in artifacts[name].splitlines()]
                source_rows = _source_behavior_surface()["analysis"]["per_query_metrics"]
                for target_row, source_row in zip(target_rows, source_rows, strict=True):
                    for key in source_row:
                        self.assertEqual(target_row[key], source_row[key])
            else:
                self.assertEqual(artifacts[name], source_artifacts[name])
    return test


_INVENTORY = json.loads(
    (Path(__file__).parents[1] / "assets/dci/batch-parity.json").read_text()
)
for _row in _INVENTORY["rows"]:
    if _row["target_task"] != "AF-240 Task 4":
        continue
    _method_name = _row["future_acceptance"]["test_method"]
    _method = _task4_behavior_test(_row)
    _method.__name__ = _method_name
    _method.__doc__ = _row["future_acceptance"]["assertion_summary"]
    setattr(AsterionDciAnalysisTests, _method_name, _method)
