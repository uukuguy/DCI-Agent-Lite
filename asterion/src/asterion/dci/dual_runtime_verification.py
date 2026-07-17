"""Body-free verification for bounded dual-runtime DCI application evidence."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path

from asterion.capabilities.dci_research.complete import complete_application_identity


class DciDualRuntimeVerificationError(RuntimeError):
    """Safe failure for invalid private dual-runtime evidence."""


def _private_file(path: Path) -> bytes:
    try:
        metadata = path.lstat()
        raw = path.read_bytes()
    except OSError:
        raise DciDualRuntimeVerificationError("private runtime evidence is unavailable") from None
    if path.is_symlink() or not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600:
        raise DciDualRuntimeVerificationError("private runtime evidence is unsafe")
    return raw


def _document(path: Path) -> tuple[dict[str, object], bytes]:
    raw = _private_file(path)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        raise DciDualRuntimeVerificationError("private runtime evidence is invalid") from None
    if not isinstance(value, dict):
        raise DciDualRuntimeVerificationError("private runtime evidence is invalid")
    return value, raw


def _contained_path(value: object, corpus: Path) -> bool:
    if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
        return False
    candidate = Path(value)
    resolved = candidate.resolve() if candidate.is_absolute() else (corpus / candidate).resolve()
    return resolved == corpus or resolved.is_relative_to(corpus)


def audit_restricted_pi_application(*, run_dir: Path, corpus_dir: Path) -> dict[str, object]:
    """Rehash and validate one real read/grep-only Pi complete-application run."""

    run = Path(run_dir).resolve()
    corpus = Path(corpus_dir).resolve()
    if not run.is_dir() or not corpus.is_dir() or run.is_symlink() or corpus.is_symlink():
        raise DciDualRuntimeVerificationError("runtime evidence boundary is invalid")
    state, state_raw = _document(run / "state.json")
    request, request_raw = _document(run / "protocol/attempt-0001.request.json")
    evaluation, evaluation_raw = _document(run / "eval_result.json")
    events_raw = _private_file(run / "protocol/attempt-0001.events.jsonl")
    try:
        events = [json.loads(line) for line in events_raw.splitlines() if line]
    except (TypeError, ValueError):
        raise DciDualRuntimeVerificationError("private runtime evidence is invalid") from None
    if (
        state.get("status") != "completed"
        or state.get("tools") != "read,grep"
        or state.get("max_turns") != 4
        or request.get("requested_capabilities") != ["filesystem.read", "pi.tool.grep"]
        or evaluation.get("is_correct") is not True
    ):
        raise DciDualRuntimeVerificationError("restricted Pi contract did not complete")
    calls = [event for event in events if event.get("type") == "tool.call"]
    if not calls:
        raise DciDualRuntimeVerificationError("restricted Pi tool evidence is unavailable")
    tool_counts = {"read": 0, "grep": 0}
    error_count = 0
    for event in calls:
        payload = event.get("payload")
        if not isinstance(payload, dict) or payload.get("name") not in tool_counts:
            raise DciDualRuntimeVerificationError("restricted Pi tool surface was violated")
        arguments = payload.get("arguments")
        if not isinstance(arguments, dict) or not _contained_path(arguments.get("path"), corpus):
            raise DciDualRuntimeVerificationError("restricted Pi corpus boundary was violated")
        tool_counts[str(payload["name"])] += 1
    for event in events:
        if event.get("type") == "tool.result" and event.get("payload", {}).get("is_error") is True:
            error_count += 1
    fingerprint = evaluation.get("judge_request_fingerprint")
    if not isinstance(fingerprint, str) or re.fullmatch(r"[0-9a-f]{64}", fingerprint) is None:
        raise DciDualRuntimeVerificationError("restricted Pi evaluation identity is invalid")
    artifacts = {
        "state.json": hashlib.sha256(state_raw).hexdigest(),
        "attempt-0001.request.json": hashlib.sha256(request_raw).hexdigest(),
        "attempt-0001.events.jsonl": hashlib.sha256(events_raw).hexdigest(),
        "eval_result.json": hashlib.sha256(evaluation_raw).hexdigest(),
    }
    return {
        "schema": "asterion.dci.dual-runtime-acceptance/v1",
        "runtime_id": "pi.reference",
        "status": "completed",
        "implementation_sha256": complete_application_identity(),
        "tools": tool_counts,
        "tool_call_count": sum(tool_counts.values()),
        "tool_error_count": error_count,
        "corpus_contained": True,
        "web_calls": 0,
        "subagent_calls": 0,
        "judge_request_fingerprint": fingerprint,
        "private_artifacts": artifacts,
        "full_dataset": False,
    }


def write_private_report(path: Path, report: dict[str, object]) -> str:
    """Atomically write one private report and return its digest."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.tmp")
    raw = json.dumps(report, sort_keys=True, indent=2).encode() + b"\n"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, raw)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, target)
    return hashlib.sha256(raw).hexdigest()
