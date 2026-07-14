"""Cache-safe evaluation of durable independent Asterion DCI run directories."""

from __future__ import annotations

import asyncio
import math
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from asterion.dci.artifacts import (
    DciArtifactError,
    DciRunLock,
    validate_completed_run_evidence,
)
from asterion.dci.judge import (
    DciJudgeError,
    JudgeConfig,
    judge_answer_sync,
    judge_request_fingerprint,
)


class DciEvaluationError(RuntimeError):
    """Safe public error for native-run evaluation failures."""


def evaluate_run_directory(
    output_dir: Path,
    *,
    gold_answer: str,
    judge_config: JudgeConfig,
    predicted_answer: str | None = None,
    _cancel_event: threading.Event | None = None,
) -> dict[str, object]:
    """Evaluate one completed native run under its recorder writer authority."""

    if not isinstance(gold_answer, str) or not gold_answer.strip():
        raise DciEvaluationError("DCI evaluation input is invalid")
    lock: DciRunLock | None = None
    try:
        lock = DciRunLock.acquire_existing(Path(output_dir), wait=True)
        state, question, durable_prediction = validate_completed_run_evidence(lock)
        prediction = (
            predicted_answer if predicted_answer is not None else durable_prediction
        )
        if not isinstance(prediction, str):
            raise DciEvaluationError("DCI evaluation input is invalid")
        fingerprint = judge_request_fingerprint(
            config=judge_config,
            question=question,
            gold_answer=gold_answer,
            predicted_answer=prediction,
        )
        cached = _load_reusable_result(lock, fingerprint, judge_config)
        if cached is not None:
            _persist_state_summary(lock, state, cached)
            return cached
        if _cancel_event is not None and _cancel_event.is_set():
            raise DciEvaluationError("DCI evaluation was cancelled")
        judged = judge_answer_sync(
            config=judge_config,
            question=question,
            gold_answer=gold_answer,
            predicted_answer=prediction,
            cancel_event=_cancel_event,
        )
        result = dict(judged)
        result["judge_request_fingerprint"] = fingerprint
        if not _valid_verdict(result, fingerprint, judge_config):
            raise DciEvaluationError("DCI evaluation failed")
        lock.write_json("eval_result.json", result)
        _persist_state_summary(lock, state, result)
        return result
    except DciEvaluationError:
        raise
    except (DciArtifactError, DciJudgeError, OSError, ValueError) as error:
        raise DciEvaluationError("DCI evaluation failed") from error
    finally:
        if lock is not None:
            lock.release()


async def evaluate_run_directory_async(
    output_dir: Path,
    *,
    gold_answer: str,
    judge_config: JudgeConfig,
    predicted_answer: str | None = None,
) -> dict[str, object]:
    """Evaluate asynchronously, draining a started blocking transport on cancellation."""

    cancel_event = threading.Event()
    work = asyncio.create_task(
        asyncio.to_thread(
            evaluate_run_directory,
            output_dir,
            gold_answer=gold_answer,
            judge_config=judge_config,
            predicted_answer=predicted_answer,
            _cancel_event=cancel_event,
        )
    )
    try:
        await asyncio.wait({work})
        return work.result()
    except asyncio.CancelledError:
        cancel_event.set()
        await _drain_cancelled_work(work)
        raise


async def _drain_cancelled_work(work: asyncio.Task[object]) -> None:
    while not work.done():
        current = asyncio.current_task()
        if current is not None:
            current.uncancel()
        try:
            await asyncio.wait({work})
        except asyncio.CancelledError:
            continue
    try:
        work.result()
    except Exception:
        pass


def _load_reusable_result(
    lock: DciRunLock, fingerprint: str, config: JudgeConfig
) -> dict[str, object] | None:
    value = lock.read_optional_json("eval_result.json")
    if value is None:
        return None
    return value if _valid_verdict(value, fingerprint, config) else None


def _valid_verdict(
    value: dict[str, Any], fingerprint: str, config: JudgeConfig
) -> bool:
    expected_keys = set(config.public_dict()) | {
        "judged_at",
        "attempts",
        "judge_request_fingerprint",
        "is_correct",
        "normalized_prediction",
        "reason",
        "usage",
        "cost_estimate_usd",
    }
    judged_at = value.get("judged_at")
    try:
        timestamp = (
            datetime.fromisoformat(judged_at) if isinstance(judged_at, str) else None
        )
    except ValueError:
        timestamp = None
    attempts = value.get("attempts")
    return (
        set(value) == expected_keys
        and value.get("judge_request_fingerprint") == fingerprint
        and isinstance(value.get("is_correct"), bool)
        and isinstance(value.get("normalized_prediction"), str)
        and isinstance(value.get("reason"), str)
        and timestamp is not None
        and timestamp.tzinfo is not None
        and isinstance(attempts, int)
        and not isinstance(attempts, bool)
        and 1 <= attempts <= 3
        and _valid_usage(value.get("usage"))
        and _valid_cost(value.get("cost_estimate_usd"))
        and all(
            value.get(name) == expected
            for name, expected in config.public_dict().items()
        )
    )


def _valid_usage(value: object) -> bool:
    required = {"input_tokens", "output_tokens", "total_tokens"}
    allowed = required | {"input_tokens_details"}
    if (
        not isinstance(value, dict)
        or not required.issubset(value)
        or set(value) - allowed
    ):
        return False
    numbers = [value[name] for name in required]
    details = value.get("input_tokens_details")
    if details is not None:
        if not isinstance(details, dict) or set(details) != {"cached_tokens"}:
            return False
        numbers.append(details["cached_tokens"])
    return all(
        isinstance(number, (int, float))
        and not isinstance(number, bool)
        and math.isfinite(number)
        and number >= 0
        for number in numbers
    )


def _valid_cost(value: object) -> bool:
    names = {"input_cost", "cached_input_cost", "output_cost", "total_cost"}
    return (
        isinstance(value, dict)
        and set(value) == names
        and all(
            isinstance(value[name], (int, float))
            and not isinstance(value[name], bool)
            and math.isfinite(value[name])
            and value[name] >= 0
            for name in names
        )
    )


def _persist_state_summary(
    lock: DciRunLock, state: dict[str, Any], result: dict[str, object]
) -> None:
    state["evaluation"] = {
        name: result.get(name)
        for name in (
            "judge_model",
            "judge_base_url",
            "judge_api",
            "judged_at",
            "judge_request_fingerprint",
            "is_correct",
            "normalized_prediction",
            "reason",
            "usage",
            "cost_estimate_usd",
        )
    }
    lock.write_json("state.json", state)
