"""Test-only stable semantic projections for the independent DCI products."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path


def _json_object(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"missing mandatory artifact: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"malformed JSON artifact: {path.name}") from error
    if not isinstance(value, dict):
        raise ValueError(f"malformed JSON artifact: {path.name}")
    return value


def _jsonl_objects(path: Path) -> list[dict[str, object]]:
    if not path.is_file():
        raise ValueError(f"missing mandatory artifact: {path.name}")
    values: list[dict[str, object]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError
            values.append(value)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"malformed JSONL artifact: {path.name}") from error
    if not values:
        raise ValueError(f"malformed JSONL artifact: {path.name}")
    return values


def _required_string(value: Mapping[str, object], field: str, artifact: str) -> str:
    item = value.get(field)
    if not isinstance(item, str) or not item:
        raise ValueError(f"malformed {artifact}: {field}")
    return item


def canonical_run_semantics(root: Path) -> dict[str, object]:
    """Project either product's native run directory onto common stable semantics."""

    directory = Path(root)
    state = _json_object(directory / "state.json")
    raw_events = _jsonl_objects(directory / "events.jsonl")
    attempts = sorted((directory / "protocol").glob("attempt-*.events.jsonl"))
    if not attempts:
        raise ValueError("missing mandatory artifact: protocol events JSONL")
    protocol_events = _jsonl_objects(attempts[-1])
    terminal_type = protocol_events[-1].get("type")
    terminals = {"run.completed": "completed", "run.failed": "failed"}
    if terminal_type not in terminals:
        raise ValueError("malformed protocol events JSONL: terminal event")
    status = _required_string(state, "status", "state.json")
    if status not in {"completed", "failed"}:
        raise ValueError("malformed state.json: status")
    if terminals[terminal_type] != status:
        raise ValueError("native lifecycle evidence disagrees")
    provenance: object = state.get("pi_source")
    if provenance is None:
        provenance_attempts = state.get("pi_source_attempts")
        if isinstance(provenance_attempts, list) and provenance_attempts:
            provenance = provenance_attempts[-1]
    if not isinstance(provenance, Mapping):
        raise ValueError("malformed state.json: Pi provenance")
    commit = provenance.get("commit")
    dirty = provenance.get("dirty")
    if not isinstance(commit, str) or type(dirty) is not bool:
        raise ValueError("malformed state.json: Pi provenance")
    resume_count = state.get("resume_count")
    if isinstance(resume_count, bool) or not isinstance(resume_count, int):
        raise ValueError("malformed state.json: resume_count")
    final_present = (directory / "final.txt").is_file()
    if final_present:
        try:
            final_text = (directory / "final.txt").read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise ValueError("malformed final.txt") from error
        if not final_text.strip():
            raise ValueError("malformed final.txt")
    return {
        "status": status,
        "event_stream": "parseable-jsonl",
        "raw_event_types": [event.get("type") for event in raw_events],
        "final_present": final_present,
        "final_answer": "provider-prose" if final_present else None,
        "state_present": True,
        "provider": _required_string(state, "provider", "state.json"),
        "model": _required_string(state, "model", "state.json"),
        "tools": _required_string(state, "tools", "state.json"),
        "pi_provenance": {"commit": commit, "dirty": dirty},
        "resume_count": resume_count,
        "protocol_attempt_count": len(attempts),
        "protocol_terminal": terminals[terminal_type],
    }


def canonical_judge_semantics(
    result: Mapping[str, object],
) -> dict[str, object]:
    """Retain Judge request identity and typed verdict while dropping provider prose/time."""

    verdict = result.get("is_correct")
    if type(verdict) is not bool:
        raise ValueError("Judge verdict must be boolean")
    fingerprint = result.get("judge_request_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint:
        raise ValueError("Judge request fingerprint is missing")
    configuration = {
        key: value
        for key, value in sorted(result.items())
        if key.startswith("judge_") and key != "judge_request_fingerprint"
    }
    projected: dict[str, object] = {
        "is_correct": verdict,
        "judge_request_fingerprint": fingerprint,
        "configuration": configuration,
    }
    attempts = result.get("attempts")
    if attempts is not None:
        if isinstance(attempts, bool) or not isinstance(attempts, int):
            raise ValueError("Judge attempts count is malformed")
        projected["attempts"] = attempts
    usage = result.get("usage")
    if usage is not None:
        if not isinstance(usage, Mapping):
            raise ValueError("Judge usage counts are malformed")
        projected["usage"] = dict(usage)
    return projected


def canonical_batch_semantics(root: Path) -> dict[str, object]:
    """Project native batch evidence without hiding counts, failures, or reuse."""

    directory = Path(root)
    state = _json_object(directory / "state.json")
    summary = _json_object(directory / "summary.json")
    exports = _json_object(directory / "exports.json")
    results = _jsonl_objects(directory / "results.jsonl")
    status = _required_string(state, "status", "state.json")
    counts = state.get("counts")
    if not isinstance(counts, dict) or any(
        isinstance(value, bool) or not isinstance(value, int)
        for value in counts.values()
    ):
        raise ValueError("malformed state.json: counts")
    ndcg = summary.get("ndcg_at_10")
    if isinstance(ndcg, bool) or not isinstance(ndcg, (int, float)):
        raise ValueError("malformed summary.json: ndcg_at_10")
    failure_classification: list[str] = []
    reuse_decisions: list[bool] = []
    for result in results:
        row_status = _required_string(result, "status", "results.jsonl")
        reused = result.get("reused")
        if type(reused) is not bool:
            raise ValueError("malformed results.jsonl: reused")
        reuse_decisions.append(reused)
        if row_status != "completed":
            failure_classification.append(row_status)
    if any(isinstance(value, bool) or not isinstance(value, int) for value in exports.values()):
        raise ValueError("malformed exports.json: counts")
    return {
        "status": status,
        "counts": counts,
        "failure_classification": failure_classification,
        "ndcg_at_10": ndcg,
        "exports": exports,
        "reuse_decisions": reuse_decisions,
    }
