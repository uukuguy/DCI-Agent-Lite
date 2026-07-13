"""Deterministic JSONL benchmark orchestration for independent Asterion DCI runs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from asterion.dci.config import DciPaths
from asterion.dci.evaluation import evaluate_run_directory
from asterion.dci.judge import JudgeConfig
from asterion.dci.run import DciRunRequest, run_pi_research


class DciBenchmarkError(RuntimeError):
    """Safe public error for an invalid benchmark request or dataset."""


@dataclass(frozen=True)
class BenchmarkRequest:
    dataset: Path
    output_root: Path
    cwd: Path
    judge_config: JudgeConfig


@dataclass(frozen=True)
class BenchmarkResult:
    output_root: Path
    counts: dict[str, int]


def run_benchmark(request: BenchmarkRequest, *, paths: DciPaths) -> BenchmarkResult:
    """Run or reuse explicit dataset rows through Asterion-native boundaries only."""

    rows = _load_rows(request.dataset)
    output_root = Path(request.output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for row in rows:
        query_dir = output_root / row["query_id"]
        existing = _read_json(query_dir / "result.json")
        if isinstance(existing, dict) and isinstance(existing.get("is_correct"), bool):
            results.append(existing)
            continue
        if not _is_completed_native_run(query_dir):
            run_pi_research(
                paths,
                DciRunRequest(run_id=row["query_id"], question=row["query"], cwd=request.cwd),
                output_dir=query_dir,
            )
        verdict = evaluate_run_directory(query_dir, gold_answer=row["answer"], judge_config=request.judge_config)
        result = {"query_id": row["query_id"], "is_correct": verdict["is_correct"]}
        _write_json(query_dir / "result.json", result)
        results.append(result)
    counts = {"total": len(results), "correct": sum(item.get("is_correct") is True for item in results)}
    _write_json(output_root / "summary.json", {"counts": counts})
    return BenchmarkResult(output_root=output_root, counts=counts)


def _load_rows(dataset: Path) -> list[dict[str, str]]:
    try:
        lines = Path(dataset).read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise DciBenchmarkError("DCI benchmark dataset is invalid") from error
    rows: list[dict[str, str]] = []
    identities: set[str] = set()
    for line in lines:
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise DciBenchmarkError("DCI benchmark dataset is invalid") from error
        if not isinstance(value, dict) or any(not isinstance(value.get(name), str) or not value[name] for name in ("query_id", "query", "answer")):
            raise DciBenchmarkError("DCI benchmark dataset is invalid")
        query_id = value["query_id"]
        if query_id in identities or Path(query_id).is_absolute() or Path(query_id).name != query_id:
            raise DciBenchmarkError("DCI benchmark dataset is invalid")
        identities.add(query_id)
        rows.append({"query_id": query_id, "query": value["query"], "answer": value["answer"]})
    return sorted(rows, key=lambda row: row["query_id"])


def _is_completed_native_run(directory: Path) -> bool:
    state = _read_json(directory / "state.json")
    return isinstance(state, dict) and state.get("status") == "completed" and (directory / "final.txt").is_file()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
