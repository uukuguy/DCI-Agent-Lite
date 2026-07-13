"""Cache-safe evaluation of durable independent Asterion DCI run directories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from asterion.dci.judge import JudgeConfig, judge_answer_sync, judge_request_fingerprint


class DciEvaluationError(RuntimeError):
    """Safe public error for native-run evaluation failures."""


def evaluate_run_directory(
    output_dir: Path,
    *,
    gold_answer: str,
    judge_config: JudgeConfig,
    predicted_answer: str | None = None,
) -> dict[str, object]:
    """Evaluate one completed native run, reusing only an exact cache identity."""

    destination = Path(output_dir).resolve()
    state, question = _load_completed_state(destination)
    if not gold_answer.strip():
        raise DciEvaluationError("DCI evaluation input is invalid")
    prediction = predicted_answer if predicted_answer is not None else _read_final(destination)
    fingerprint = judge_request_fingerprint(
        config=judge_config,
        question=question,
        gold_answer=gold_answer,
        predicted_answer=prediction,
    )
    result_path = destination / "eval_result.json"
    cached = _load_reusable_result(result_path, fingerprint)
    if cached is not None:
        _persist_state_summary(destination, state, cached)
        return cached
    try:
        judged = judge_answer_sync(
            config=judge_config,
            question=question,
            gold_answer=gold_answer,
            predicted_answer=prediction,
        )
    except RuntimeError as error:
        raise DciEvaluationError("DCI evaluation failed") from error
    result = dict(judged)
    result["judge_request_fingerprint"] = fingerprint
    if not isinstance(result.get("is_correct"), bool):
        raise DciEvaluationError("DCI evaluation failed")
    _write_json(result_path, result)
    _persist_state_summary(destination, state, result)
    return result


def _load_completed_state(destination: Path) -> tuple[dict[str, Any], str]:
    try:
        state = json.loads((destination / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise DciEvaluationError("DCI evaluation native state is invalid") from error
    if not isinstance(state, dict) or state.get("status") != "completed":
        raise DciEvaluationError("DCI evaluation native run is not completed")
    question = state.get("question")
    if not isinstance(question, str) or not question:
        raise DciEvaluationError("DCI evaluation native state is invalid")
    return state, question


def _read_final(destination: Path) -> str:
    try:
        return (destination / "final.txt").read_text(encoding="utf-8").strip()
    except OSError as error:
        raise DciEvaluationError("DCI evaluation final artifact is unavailable") from error


def _load_reusable_result(path: Path, fingerprint: str) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(value, dict) or value.get("judge_request_fingerprint") != fingerprint:
        return None
    if not isinstance(value.get("is_correct"), bool):
        return None
    return value


def _persist_state_summary(
    destination: Path, state: dict[str, Any], result: dict[str, object]
) -> None:
    state["evaluation"] = {
        name: result.get(name)
        for name in (
            "judge_model",
            "judge_base_url",
            "judge_api",
            "judged_at",
            "is_correct",
            "normalized_prediction",
            "reason",
            "cost_estimate_usd",
        )
    }
    _write_json(destination / "state.json", state)


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
