"""Pure metric, aggregate, report, and figure analysis for Asterion DCI batches."""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any


def _number(value: object) -> float | None:
    return float(value) if not isinstance(value, bool) and isinstance(value, (int, float)) else None


safe_float = _number


def _datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def seconds_between(start: object, end: object) -> float | None:
    started = _datetime(start)
    finished = _datetime(end)
    if started is None or finished is None:
        return None
    return max(0.0, (finished - started).total_seconds())


def extract_agent_usage_metrics(state: Mapping[str, Any]) -> dict[str, float]:
    totals = {
        "input_tokens": 0.0,
        "output_tokens": 0.0,
        "cache_read_tokens": 0.0,
        "cache_write_tokens": 0.0,
        "total_tokens": 0.0,
        "cost_input": 0.0,
        "cost_output": 0.0,
        "cost_cache_read": 0.0,
        "cost_cache_write": 0.0,
        "cost_total": 0.0,
    }
    for item in state.get("messages", ()):
        if not isinstance(item, Mapping) or item.get("event") != "message_end":
            continue
        message = item.get("message")
        if not isinstance(message, Mapping) or message.get("role") != "assistant":
            continue
        usage = message.get("usage") if isinstance(message.get("usage"), Mapping) else {}
        cost = usage.get("cost") if isinstance(usage.get("cost"), Mapping) else {}
        for target, source in (
            ("input_tokens", usage.get("input")),
            ("output_tokens", usage.get("output")),
            ("cache_read_tokens", usage.get("cacheRead")),
            ("cache_write_tokens", usage.get("cacheWrite")),
            ("total_tokens", usage.get("totalTokens")),
            ("cost_input", cost.get("input")),
            ("cost_output", cost.get("output")),
            ("cost_cache_read", cost.get("cacheRead")),
            ("cost_cache_write", cost.get("cacheWrite")),
            ("cost_total", cost.get("total")),
        ):
            totals[target] += _number(source) or 0.0
    return totals


def extract_tool_metrics(state: Mapping[str, Any]) -> dict[str, Any]:
    starts: dict[str, Mapping[str, Any]] = {}
    durations: list[float] = []
    calls = errors = 0
    by_tool: dict[str, dict[str, float]] = {}
    for entry in state.get("tool_calls", ()):
        if not isinstance(entry, Mapping):
            continue
        call_id = str(entry.get("toolCallId") or "")
        tool = str(entry.get("toolName") or "unknown")
        metrics = by_tool.setdefault(
            tool, {"call_count": 0.0, "error_count": 0.0, "duration_seconds": 0.0}
        )
        if entry.get("event") == "tool_execution_start":
            starts[call_id] = entry
            continue
        if entry.get("event") != "tool_execution_end":
            continue
        calls += 1
        metrics["call_count"] += 1.0
        if entry.get("isError") is True:
            errors += 1
            metrics["error_count"] += 1.0
        start = starts.pop(call_id, None)
        duration = seconds_between(start.get("recorded_at") if start else None, entry.get("recorded_at"))
        if duration is not None:
            durations.append(duration)
            metrics["duration_seconds"] += duration
    return {
        "call_count": calls,
        "error_count": errors,
        "duration_seconds": sum(durations),
        "duration_measured_call_count": len(durations),
        "duration_missing_call_count": max(0, calls - len(durations)),
        "by_tool": dict(sorted(by_tool.items())),
    }


def gather_query_metrics(
    *,
    row: Mapping[str, Any],
    state: Mapping[str, Any] | None,
    latest_model_context: Mapping[str, Any],
    final_text: str,
    stderr_text: str = "",
    judge_result: Mapping[str, Any] | None = None,
    ndcg_at_10: float | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
    launcher_returncode: int | None = None,
    launcher_started_at: str | None = None,
    launcher_finished_at: str | None = None,
) -> dict[str, Any]:
    available = state is not None
    state = state or {}
    agent_usage: dict[str, Any] = extract_agent_usage_metrics(state) if available else {
        key: None for key in (
            "input_tokens", "output_tokens", "cache_read_tokens",
            "cache_write_tokens", "total_tokens", "cost_input", "cost_output",
            "cost_cache_read", "cost_cache_write", "cost_total",
        )
    }
    tool_metrics: dict[str, Any] = extract_tool_metrics(state) if available else {
        "call_count": None, "error_count": None, "duration_seconds": None,
        "duration_measured_call_count": None,
        "duration_missing_call_count": None, "by_tool": {},
    }
    started_at = started_at or state.get("started_at")
    finished_at = finished_at or state.get("finished_at")
    wall = seconds_between(started_at, finished_at)
    tool_time = _number(tool_metrics["duration_seconds"])
    non_tool = None if wall is None or tool_time is None else max(0.0, wall - tool_time)
    usage = judge_result.get("usage") if judge_result and isinstance(judge_result.get("usage"), Mapping) else {}
    cost = judge_result.get("cost_estimate_usd") if judge_result and isinstance(judge_result.get("cost_estimate_usd"), Mapping) else {}
    runtime = latest_model_context.get("runtime_context_management")
    latest = latest_model_context.get("latest")
    if runtime is None and isinstance(latest, Mapping):
        runtime = latest.get("runtime_context_management")
    return {
        "query_id": str(row["query_id"]),
        "question": row.get("query"),
        "gold_answer": row.get("answer"),
        "final_text": final_text.strip(),
        "run_status": state.get("status"),
        "run_error": state.get("error"),
        "launcher_returncode": launcher_returncode,
        "launcher_started_at": launcher_started_at,
        "launcher_finished_at": launcher_finished_at,
        "launcher_wall_time_seconds": seconds_between(
            launcher_started_at, launcher_finished_at
        ),
        "agent_started_at": started_at,
        "agent_finished_at": finished_at,
        "wall_time_seconds": wall,
        "tool_time_seconds": tool_time,
        "non_tool_time_seconds": non_tool,
        "event_count": state.get("event_count"),
        "turn_count": state.get("turn_count") if state.get("turn_count") is not None else sum(
            isinstance(item, Mapping)
            and item.get("event") == "message_end"
            and isinstance(item.get("message"), Mapping)
            and item["message"].get("role") == "assistant"
            for item in state.get("messages", ())
        ),
        "tool_metrics": tool_metrics,
        "agent_usage": agent_usage,
        "judge_result": dict(judge_result) if judge_result is not None else None,
        "judge_usage": dict(usage),
        "judge_cost_estimate_usd": dict(cost),
        "is_correct": None if judge_result is None else judge_result.get("is_correct"),
        "ndcg_at_10": ndcg_at_10,
        "runtime_context_management": runtime,
        "conversation_features": state.get("conversation_features"),
        "request_count": latest_model_context.get("request_count"),
        "stderr_tail": stderr_text[-4000:],
    }


def _sum(results: Sequence[Mapping[str, Any]], path: tuple[str, ...]) -> float:
    total = 0.0
    for result in results:
        value: object = result
        for key in path:
            value = value.get(key) if isinstance(value, Mapping) else None
        total += _number(value) or 0.0
    return total


def compute_run_batch_timing(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    starts = [_datetime(result.get("agent_started_at")) for result in results]
    ends = [_datetime(result.get("agent_finished_at")) for result in results]
    valid_starts = [value for value in starts if value is not None]
    valid_ends = [value for value in ends if value is not None]
    if not valid_starts or not valid_ends:
        return {"started_at": None, "finished_at": None, "elapsed_wall_clock_seconds": None}
    start = min(valid_starts)
    end = max(valid_ends)
    return {
        "started_at": start.isoformat(),
        "finished_at": end.isoformat(),
        "elapsed_wall_clock_seconds": max(0.0, (end - start).total_seconds()),
    }


def aggregate_results(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(results)
    judged = sum(result.get("is_correct") is not None for result in results)
    correct = sum(result.get("is_correct") is True for result in results)
    failed = sum(result.get("run_status") != "completed" for result in results)
    paths = {
        "wall_time_seconds": ("wall_time_seconds",),
        "launcher_wall_time_seconds": ("launcher_wall_time_seconds",),
        "tool_time_seconds": ("tool_time_seconds",),
        "non_tool_time_seconds": ("non_tool_time_seconds",),
        "event_count": ("event_count",),
        "turn_count": ("turn_count",),
        "tool_call_count": ("tool_metrics", "call_count"),
        "tool_error_count": ("tool_metrics", "error_count"),
        "agent_input_tokens": ("agent_usage", "input_tokens"),
        "agent_output_tokens": ("agent_usage", "output_tokens"),
        "agent_cache_read_tokens": ("agent_usage", "cache_read_tokens"),
        "agent_cache_write_tokens": ("agent_usage", "cache_write_tokens"),
        "agent_total_tokens": ("agent_usage", "total_tokens"),
        "agent_cost_total": ("agent_usage", "cost_total"),
        "judge_input_tokens": ("judge_usage", "input_tokens"),
        "judge_output_tokens": ("judge_usage", "output_tokens"),
        "judge_total_tokens": ("judge_usage", "total_tokens"),
        "judge_cost_total": ("judge_cost_estimate_usd", "total_cost"),
    }
    totals = {name: _sum(results, path) for name, path in paths.items()}
    totals["overall_cost_total"] = totals["agent_cost_total"] + totals["judge_cost_total"]
    ndcg = [float(value) for result in results if (value := _number(result.get("ndcg_at_10"))) is not None]
    return {
        "schema": "asterion.dci.batch-summary/v1",
        "counts": {"total": total, "judged": judged, "correct": correct, "incorrect_or_unjudged": total - correct, "failed_runs": failed},
        "accuracy": {"over_total": correct / total if total else 0.0, "over_judged": correct / judged if judged else 0.0},
        "ndcg_at_10": sum(ndcg) / len(ndcg) if ndcg else None,
        "timing": compute_run_batch_timing(results),
        "totals": totals,
        "averages": {
            name: totals[name] / total if total else 0.0
            for name in ("wall_time_seconds", "tool_time_seconds", "tool_call_count", "turn_count", "agent_total_tokens", "judge_total_tokens", "overall_cost_total")
        },
    }


def compute_percentile(sorted_values: Sequence[float], quantile: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    index = (len(sorted_values) - 1) * quantile
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    weight = index - lower
    return float(sorted_values[lower] * (1.0 - weight) + sorted_values[upper] * weight)


def summarize_numeric(values: Sequence[float]) -> dict[str, Any]:
    cleaned = sorted(float(value) for value in values)
    if not cleaned:
        return {key: None if key != "count" else 0 for key in ("count", "mean", "min", "p10", "p25", "median", "p75", "p90", "max")}
    return {
        "count": len(cleaned), "mean": sum(cleaned) / len(cleaned), "min": cleaned[0],
        "p10": compute_percentile(cleaned, 0.1), "p25": compute_percentile(cleaned, 0.25),
        "median": compute_percentile(cleaned, 0.5), "p75": compute_percentile(cleaned, 0.75),
        "p90": compute_percentile(cleaned, 0.9), "max": cleaned[-1],
    }


def _enrich(results: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    by_id = {str(row["query_id"]): row for row in rows}
    records: list[dict[str, Any]] = []
    tools: set[str] = set()
    for result in results:
        query_id = str(result.get("query_id"))
        row = by_id.get(query_id, {})
        tool_metrics = result.get("tool_metrics") if isinstance(result.get("tool_metrics"), Mapping) else {}
        by_tool = tool_metrics.get("by_tool") if isinstance(tool_metrics.get("by_tool"), Mapping) else {}
        tools.update(str(name) for name in by_tool)
        counts = {str(name): _number(value.get("call_count")) or 0.0 for name, value in by_tool.items() if isinstance(value, Mapping)}
        durations = {str(name): _number(value.get("duration_seconds")) or 0.0 for name, value in by_tool.items() if isinstance(value, Mapping)}
        wall = _number(result.get("wall_time_seconds"))
        tool_time = _number(result.get("tool_time_seconds"))
        agent = result.get("agent_usage") if isinstance(result.get("agent_usage"), Mapping) else {}
        judge = result.get("judge_usage") if isinstance(result.get("judge_usage"), Mapping) else {}
        judge_cost = result.get("judge_cost_estimate_usd") if isinstance(result.get("judge_cost_estimate_usd"), Mapping) else {}
        question = str(result.get("question") or row.get("query") or "")
        final = str(result.get("final_text") or "")
        agent_cost = _number(agent.get("cost_total"))
        judge_cost_total = _number(judge_cost.get("total_cost"))
        overall_cost = (
            (agent_cost or 0.0) + (judge_cost_total or 0.0)
            if agent_cost is not None or judge_cost_total is not None
            else None
        )
        records.append({
            "query_id": query_id, "query": question,
            "gold_answer": str(result.get("gold_answer") or row.get("answer") or ""),
            "final_text": final, "run_status": result.get("run_status"), "is_correct": result.get("is_correct"),
            "ndcg_at_10": result.get("ndcg_at_10"),
            "judge_reason": (result.get("judge_result") or {}).get("reason") if isinstance(result.get("judge_result"), Mapping) else None,
            "question_word_count": len(question.split()), "question_char_count": len(question), "answer_char_count": len(final),
            "gold_doc_count": len(row.get("gold_docs") or row.get("gold_ids") or ()),
            "wall_time_seconds": wall, "tool_time_seconds": tool_time,
            "launcher_wall_time_seconds": _number(result.get("launcher_wall_time_seconds")),
            "non_tool_time_seconds": _number(result.get("non_tool_time_seconds")),
            "tool_time_share": tool_time / wall if wall and tool_time is not None else None,
            "turn_count": _number(result.get("turn_count")), "request_count": _number(result.get("request_count")),
            "event_count": _number(result.get("event_count")),
            "tool_call_count": _number(tool_metrics.get("call_count")),
            "tool_error_count": _number(tool_metrics.get("error_count")),
            "tool_counts": dict(sorted(counts.items())), "tool_durations": dict(sorted(durations.items())),
            "agent_input_tokens": _number(agent.get("input_tokens")),
            "agent_output_tokens": _number(agent.get("output_tokens")),
            "agent_cache_read_tokens": _number(agent.get("cache_read_tokens")),
            "agent_total_tokens": _number(agent.get("total_tokens")),
            "agent_cost_total": agent_cost,
            "judge_total_tokens": _number(judge.get("total_tokens")),
            "judge_cost_total": judge_cost_total, "overall_cost_total": overall_cost,
        })
    return records, sorted(tools)


def enrich_results(
    results: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], list[str]]:
    return _enrich(results, rows)


def _slice(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    names = ("wall_time_seconds", "tool_time_seconds", "tool_time_share", "turn_count", "tool_call_count", "tool_error_count", "agent_total_tokens", "overall_cost_total", "question_word_count")
    return {name: summarize_numeric([value for row in records if (value := _number(row.get(name))) is not None]) for name in names}


def build_slice_stats(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return _slice(records)


def rank_records(
    records: Sequence[Mapping[str, Any]], key: str, top_k: int = 10
) -> list[dict[str, Any]]:
    selected = [row for row in records if _number(row.get(key)) is not None]
    selected.sort(key=lambda row: (-float(row[key]), str(row["query_id"])))
    return [
        {
            "query_id": row["query_id"],
            "value": row[key],
            "is_correct": row["is_correct"],
            "wall_time_seconds": row["wall_time_seconds"],
            "overall_cost_total": row["overall_cost_total"],
            "tool_call_count": row["tool_call_count"],
            "turn_count": row["turn_count"],
        }
        for row in selected[:top_k]
    ]


def compute_detailed_analysis(*, results: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> dict[str, Any]:
    records, tools = _enrich(results, rows)
    tool_summary: dict[str, Any] = {}
    for tool in tools:
        used = [row for row in records if row["tool_counts"].get(tool, 0) > 0]
        calls = sum(row["tool_counts"].get(tool, 0.0) for row in records)
        duration = sum(row["tool_durations"].get(tool, 0.0) for row in records)
        errors = sum(float(((result.get("tool_metrics") or {}).get("by_tool") or {}).get(tool, {}).get("error_count", 0) or 0) for result in results)
        correct = sum(row.get("is_correct") is True for row in used)
        tool_summary[tool] = {
            "queries_used": len(used), "queries_used_rate": len(used) / len(records) if records else 0.0,
            "correct_when_used": correct, "accuracy_when_used": correct / len(used) if used else None,
            "total_calls": calls, "avg_calls_per_query": calls / len(records) if records else 0.0,
            "avg_calls_when_used": calls / len(used) if used else None,
            "total_duration_seconds": duration, "avg_duration_per_call_seconds": duration / calls if calls else None,
            "total_error_count": errors,
        }
    totals = summary.get("totals") if isinstance(summary.get("totals"), Mapping) else {}
    counts = summary.get("counts") if isinstance(summary.get("counts"), Mapping) else {}
    total_cost = _number(totals.get("overall_cost_total")) or 0.0
    total_tokens = _number(totals.get("agent_total_tokens")) or 0.0
    correct_count = int(_number(counts.get("correct")) or 0)
    incorrect = [row for row in records if row.get("is_correct") is False]
    return {
        "schema": "asterion.dci.batch-analysis/v1",
        "cost_efficiency": {"cost_per_correct_usd": total_cost / correct_count if correct_count else None, "agent_tokens_per_correct": total_tokens / correct_count if correct_count else None},
        "slices": {"all": _slice(records), "correct": _slice([row for row in records if row.get("is_correct") is True]), "incorrect": _slice(incorrect)},
        "tool_summary": tool_summary,
        "rankings": {"slowest_queries": rank_records(records, "wall_time_seconds"), "most_expensive_queries": rank_records(records, "overall_cost_total"), "highest_token_queries": rank_records(records, "agent_total_tokens"), "most_tool_heavy_queries": rank_records(records, "tool_call_count")},
        "incorrect_queries": [{"query_id": row["query_id"], "wall_time_seconds": row["wall_time_seconds"], "overall_cost_total": row["overall_cost_total"], "tool_call_count": row["tool_call_count"], "turn_count": row["turn_count"], "gold_answer": row["gold_answer"], "predicted_answer": row["final_text"], "judge_reason": row["judge_reason"], "query": row["query"]} for row in incorrect],
        "per_query_metrics": records,
    }


def _seconds(value: object) -> str:
    number = _number(value)
    return "n/a" if number is None else f"{number:.1f}s"


format_seconds = _seconds


def _usd(value: object) -> str:
    number = _number(value)
    return "n/a" if number is None else f"${number:.4f}"


format_usd = _usd


def _format(value: object, digits: int = 1) -> str:
    number = _number(value)
    return "n/a" if number is None else f"{number:.{digits}f}"


format_number = _format


def write_markdown_report(
    *, summary: Mapping[str, Any], analysis: Mapping[str, Any], include_figures: bool = True
) -> str:
    counts = summary.get("counts") or {}
    accuracy = summary.get("accuracy") or {}
    totals = summary.get("totals") or {}
    averages = summary.get("averages") or {}
    efficiency = analysis.get("cost_efficiency") or {}
    rankings = analysis.get("rankings") or {}
    incorrect = analysis.get("incorrect_queries") or ()
    slices = analysis.get("slices") or {}
    correct_wall = ((slices.get("correct") or {}).get("wall_time_seconds") or {})
    incorrect_wall = ((slices.get("incorrect") or {}).get("wall_time_seconds") or {})
    ndcg = summary.get("ndcg_at_10")
    headline = f"- NDCG@10: {ndcg:.4f}" if _number(ndcg) is not None else f"- Accuracy: {float(accuracy.get('over_total', 0)):.2%} ({counts.get('correct', 0)}/{counts.get('total', 0)})"
    lines = [
        "# BrowseComp Eval Analysis", "", "## Headline", "", headline,
        f"- Failed runs: {counts.get('failed_runs', 0)}",
        f"- Total cost: {_usd(totals.get('overall_cost_total'))}",
        f"- Cost per correct: {_usd(efficiency.get('cost_per_correct_usd'))}",
        f"- Avg wall time: {_seconds(averages.get('wall_time_seconds'))}",
        f"- Avg tool calls: {_format(averages.get('tool_call_count'))}",
        f"- Avg agent tokens: {_format(averages.get('agent_total_tokens'))}",
        "", "## Outcome Slices", "",
        f"- Correct median wall time: {_seconds(correct_wall.get('median'))}",
        f"- Incorrect median wall time: {_seconds(incorrect_wall.get('median'))}",
        "", "## Figures", "",
    ]
    if include_figures:
        lines.extend([
            "- `analysis_figures/scatter_overview.png`",
            "- `analysis_figures/runtime_breakdown.png`",
            "- `analysis_figures/metric_distributions.png`",
            "- `analysis_figures/tool_summary.png`",
        ])
    else:
        lines.append("- Figures disabled by configuration.")
    lines.extend([
        "", "## Slowest Queries", "",
        "| Query ID | Wall Time | Cost | Tool Calls | Correct |",
        "| --- | --- | --- | --- | --- |",
    ])
    for row in (rankings.get("slowest_queries") or ())[:5]:
        lines.append(f"| {row.get('query_id')} | {_seconds(row.get('value'))} | {_usd(row.get('overall_cost_total'))} | {_format(row.get('tool_call_count'))} | {row.get('is_correct')} |")
    lines.extend(["", "## Most Expensive Queries", "", "| Query ID | Cost | Wall Time | Tool Calls | Correct |", "| --- | --- | --- | --- | --- |"])
    for row in (rankings.get("most_expensive_queries") or ())[:5]:
        lines.append(f"| {row.get('query_id')} | {_usd(row.get('value'))} | {_seconds(row.get('wall_time_seconds'))} | {_format(row.get('tool_call_count'))} | {row.get('is_correct')} |")
    lines.extend(["", "## Incorrect Queries", ""])
    lines.extend(f"- qid={row.get('query_id')} wall={_seconds(row.get('wall_time_seconds'))} cost={_usd(row.get('overall_cost_total'))} reason={row.get('judge_reason') or 'n/a'}" for row in incorrect)
    if not incorrect:
        lines.append("- None")
    return "\n".join(lines) + "\n"


def scatter_by_outcome(
    axis: Any,
    records: Sequence[Mapping[str, Any]],
    *,
    x_key: str,
    y_key: str,
    xlabel: str,
    ylabel: str,
    size_key: str,
) -> None:
    labeled = False
    for label, color, outcome in (
        ("Correct", "#2E8B57", True),
        ("Incorrect", "#C0392B", False),
        ("Unjudged", "#7F8C8D", None),
    ):
        subset = [
            row
            for row in records
            if _number(row.get(x_key)) is not None
            and _number(row.get(y_key)) is not None
            and row.get("is_correct") is outcome
        ]
        if not subset:
            continue
        sizes = [30.0 + min(float(row.get(size_key, 0) or 0) / 2500.0, 180.0) for row in subset]
        axis.scatter(
            [float(row[x_key]) for row in subset],
            [float(row[y_key]) for row in subset],
            s=sizes,
            alpha=0.8,
            c=color,
            edgecolors="white",
            linewidths=0.8,
            label=label,
        )
        labeled = True
    axis.set_xlabel(xlabel)
    axis.set_ylabel(ylabel)
    axis.grid(alpha=0.2)
    if labeled:
        axis.legend(frameon=False)


def add_boxplot_panel(
    axis: Any,
    records: Sequence[Mapping[str, Any]],
    *,
    metric_key: str,
    title: str,
    ylabel: str,
) -> None:
    groups: list[list[float]] = []
    labels: list[str] = []
    colors: list[str] = []
    for label, color, outcome in (("Correct", "#2E8B57", True), ("Incorrect", "#C0392B", False)):
        values = [float(row[metric_key]) for row in records if _number(row.get(metric_key)) is not None and row.get("is_correct") is outcome]
        if values:
            groups.append(values)
            labels.append(label)
            colors.append(color)
    if not groups:
        axis.text(0.5, 0.5, "No judged data", ha="center", va="center", transform=axis.transAxes)
        axis.set_title(title)
        return
    boxes = axis.boxplot(groups, patch_artist=True, widths=0.55)
    for box, color in zip(boxes["boxes"], colors, strict=True):
        box.set_facecolor(color)
        box.set_alpha(0.75)
    axis.set_xticks(range(1, len(labels) + 1))
    axis.set_xticklabels(labels)
    axis.set_title(title)
    axis.set_ylabel(ylabel)
    axis.grid(axis="y", alpha=0.2)


def plot_scatter_overview(records: Sequence[Mapping[str, Any]]) -> bytes:
    return render_figures({"per_query_metrics": list(records)})["scatter_overview.png"]


def plot_runtime_breakdown(records: Sequence[Mapping[str, Any]]) -> bytes:
    return render_figures({"per_query_metrics": list(records)})["runtime_breakdown.png"]


def plot_metric_distributions(records: Sequence[Mapping[str, Any]]) -> bytes:
    return render_figures({"per_query_metrics": list(records)})["metric_distributions.png"]


def plot_tool_summary(analysis: Mapping[str, Any]) -> bytes:
    return render_figures(analysis)["tool_summary.png"]


def render_figures(analysis: Mapping[str, Any]) -> dict[str, bytes]:
    import matplotlib
    matplotlib.use("Agg", force=True)
    from matplotlib import pyplot as plt

    records = list(analysis.get("per_query_metrics") or ())
    figures: dict[str, Any] = {}
    fig, axes = plt.subplots(1, 2, figsize=(15, 6))
    scatter_by_outcome(axes[0], records, x_key="wall_time_seconds", y_key="overall_cost_total", xlabel="Wall Time (s)", ylabel="Overall Cost (USD)", size_key="agent_total_tokens")
    axes[0].set_title("Latency vs Cost")
    scatter_by_outcome(axes[1], records, x_key="tool_call_count", y_key="agent_total_tokens", xlabel="Tool Calls", ylabel="Agent Total Tokens", size_key="wall_time_seconds")
    axes[1].set_title("Tool Calls vs Tokens")
    fig.suptitle("BrowseComp Eval Overview", fontweight="bold")
    figures["scatter_overview.png"] = fig

    fig, ax = plt.subplots(figsize=(14, 6))
    ordered = sorted(records, key=lambda row: (-float(row.get("wall_time_seconds") or 0), str(row.get("query_id"))))
    x = list(range(len(ordered)))
    non_tool = [row.get("non_tool_time_seconds") or 0 for row in ordered]
    tool = [row.get("tool_time_seconds") or 0 for row in ordered]
    ax.bar(x, non_tool, color="#7F8C8D", label="Non-tool time")
    ax.bar(x, tool, bottom=non_tool, color="#F39C12", label="Tool time")
    ax.set(title="Per-query Runtime Breakdown", xlabel="Query ID (sorted by wall time)", ylabel="Seconds")
    ax.legend(frameon=False)
    figures["runtime_breakdown.png"] = fig

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    for ax, key, title in zip(axes.flat, ("wall_time_seconds", "overall_cost_total", "tool_call_count", "agent_total_tokens"), ("Wall Time", "Overall Cost", "Tool Calls", "Agent Tokens"), strict=True):
        add_boxplot_panel(ax, records, metric_key=key, title=title, ylabel={"wall_time_seconds": "Seconds", "overall_cost_total": "USD", "tool_call_count": "Calls", "agent_total_tokens": "Tokens"}[key])
    fig.suptitle("Correct vs Incorrect Distributions", fontweight="bold")
    figures["metric_distributions.png"] = fig

    tool_summary = analysis.get("tool_summary") or {}
    names = sorted(tool_summary, key=lambda name: (-float(tool_summary[name].get("total_calls", 0) or 0), name))
    fig, axes = plt.subplots(1, 2, figsize=(14, max(4, len(names) * 0.7)))
    axes[0].barh(names, [tool_summary[name].get("total_calls", 0) for name in names], color="#34495E")
    axes[0].set(title="Tool Calls by Tool", xlabel="Calls")
    axes[1].barh(names, [tool_summary[name].get("total_duration_seconds", 0) for name in names], color="#F39C12")
    axes[1].set(title="Measured Tool Time by Tool", xlabel="Seconds")
    figures["tool_summary.png"] = fig

    result: dict[str, bytes] = {}
    for name, figure in figures.items():
        figure.tight_layout()
        stream = io.BytesIO()
        figure.savefig(stream, format="png", dpi=200, bbox_inches="tight", metadata={"Software": "Asterion"})
        plt.close(figure)
        result[name] = stream.getvalue()
    return result


def write_analysis_artifacts(*, results: Sequence[Mapping[str, Any]], rows: Sequence[Mapping[str, Any]], summary: Mapping[str, Any], include_figures: bool) -> dict[str, bytes]:
    import json
    analysis = compute_detailed_analysis(results=results, rows=rows, summary=summary)
    artifacts = {
        "analysis.json": (json.dumps(analysis, ensure_ascii=False, indent=2) + "\n").encode(),
        "analysis.jsonl": "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in analysis["per_query_metrics"]).encode(),
        "analysis.md": write_markdown_report(
            summary=summary, analysis=analysis, include_figures=include_figures
        ).encode(),
    }
    if include_figures:
        artifacts.update({f"analysis_figures/{name}": value for name, value in render_figures(analysis).items()})
    return artifacts


__all__ = [
    "add_boxplot_panel", "aggregate_results", "build_slice_stats",
    "compute_detailed_analysis", "compute_percentile", "compute_run_batch_timing",
    "enrich_results", "extract_agent_usage_metrics", "extract_tool_metrics",
    "format_number", "format_seconds", "format_usd", "gather_query_metrics",
    "plot_metric_distributions", "plot_runtime_breakdown", "plot_scatter_overview",
    "plot_tool_summary", "rank_records", "render_figures", "safe_float",
    "scatter_by_outcome", "seconds_between", "summarize_numeric",
    "write_analysis_artifacts", "write_markdown_report",
]
