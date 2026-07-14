"""Native artifact boundary for an independent Asterion DCI Pi run."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from asterion.adapters.pi import PiProtocolAdapter, map_pi_capabilities
from asterion.dci.config import DciPaths
from asterion.dci.pi_rpc import PiRpcClient
from asterion.runtime.host import RunEvent
from asterion.runtime.protocol import (
    MAX_DEADLINE_MS,
    PROTOCOL_VERSION,
    validate_event_stream,
    validate_run_request,
)

if TYPE_CHECKING:
    from asterion.dci.config import DciRuntimeOptions


@dataclass(frozen=True)
class DciRunRequest:
    """Inputs for one new Pi-backed DCI research run."""

    run_id: str
    question: str
    cwd: Path
    provider: str | None = None
    model: str | None = None
    tools: str = "read,bash"
    max_turns: int | None = None
    timeout_seconds: float | None = 3600.0
    runtime_context_level: str | None = None
    thinking_level: str | None = None
    node_max_old_space_size_mb: int | None = None
    keep_session: bool = False
    extra_args: tuple[str, ...] = ()
    show_tools: bool = False
    system_prompt_file: Path | None = None
    append_system_prompt_file: Path | None = None
    resume: bool = False
    stream_text: bool = True


@dataclass(frozen=True)
class DciRunResult:
    """Completed native DCI run plus its protocol-normalized events."""

    output_dir: Path
    final_text: str
    events: tuple[RunEvent, ...]
    status: str


class DciRunError(RuntimeError):
    """Safe public error for a failed Pi execution."""


def request_from_runtime_options(
    options: DciRuntimeOptions,
    *,
    run_id: str,
    question: str,
    cwd: Path,
    stream_text: bool = True,
) -> DciRunRequest:
    """Convert resolved shared runtime settings into one immutable native request."""

    return DciRunRequest(
        run_id=run_id,
        question=question,
        cwd=cwd,
        provider=options.provider,
        model=options.model,
        tools=options.tools,
        timeout_seconds=options.timeout_seconds,
        runtime_context_level=options.runtime_context_level,
        thinking_level=options.thinking_level,
        node_max_old_space_size_mb=options.node_max_old_space_size_mb,
        keep_session=options.keep_session,
        extra_args=options.extra_args,
        stream_text=stream_text,
    )


def resume_request_from_output_dir(output_dir: Path) -> DciRunRequest:
    """Reconstruct a safe immutable resume request from native run state."""

    state = _load_resume_state(Path(output_dir).resolve())
    status = _required_string(state, "status")
    if status not in {"failed", "incomplete", "running"}:
        raise DciRunError("DCI resume validation failed")
    run_id = _required_string(state, "run_id")
    question = _required_string(state, "question")
    cwd = Path(_required_string(state, "cwd"))
    provider = _optional_string(state, "provider")
    model = _optional_string(state, "model")
    tools = _required_string(state, "tools")
    max_turns = _optional_int(state, "max_turns")
    runtime_context_level = _optional_string(state, "runtime_context_level")
    thinking_level = _optional_string(state, "thinking_level")
    node_max_old_space_size_mb = _optional_positive_int(state, "node_max_old_space_size_mb")
    keep_session = _required_bool(state, "keep_session")
    return DciRunRequest(
        run_id=run_id,
        question=question,
        cwd=cwd,
        provider=provider,
        model=model,
        tools=tools,
        max_turns=max_turns,
        runtime_context_level=runtime_context_level,
        thinking_level=thinking_level,
        node_max_old_space_size_mb=node_max_old_space_size_mb,
        keep_session=keep_session,
        resume=True,
    )


def run_pi_research(
    paths: DciPaths,
    request: DciRunRequest,
    *,
    output_dir: Path | None = None,
) -> DciRunResult:
    """Run Pi once and persist the AF-180 native artifact subset."""

    destination = Path(output_dir) if output_dir is not None else paths.output_root / request.run_id
    destination = destination.resolve()
    existing_state: dict[str, object] | None = None
    attempt = 1
    if destination.exists() and any(destination.iterdir()):
        if not request.resume:
            raise DciRunError("DCI output directory is not empty")
        existing_state = _load_resume_state(destination)
        _validate_resume_request(existing_state, request)
        attempt = int(existing_state.get("resume_count", 0)) + 2
    elif request.resume:
        raise DciRunError("DCI resume validation failed")
    destination.mkdir(parents=True, exist_ok=True)

    question_path = destination / "question.txt"
    events_path = destination / "events.jsonl"
    final_path = destination / "final.txt"
    stderr_path = destination / "stderr.txt"
    state_path = destination / "state.json"
    protocol_dir = destination / "protocol"
    protocol_dir.mkdir(exist_ok=True)
    attempt_stem = f"attempt-{attempt:04d}"
    protocol_request_path = protocol_dir / f"{attempt_stem}.request.json"
    protocol_events_path = protocol_dir / f"{attempt_stem}.events.jsonl"
    question_path.write_text(f"{request.question}\n", encoding="utf-8")
    if not events_path.exists():
        events_path.write_text("", encoding="utf-8")
    protocol_events_path.write_text("", encoding="utf-8")

    capabilities = map_pi_capabilities(request.tools)
    protocol_run_id = f"{request.run_id}-{attempt_stem}"
    protocol_request: dict[str, object] = {
        "protocol": PROTOCOL_VERSION,
        "run_id": protocol_run_id,
        "input": {"text": request.question},
        "requested_capabilities": capabilities,
    }
    if request.timeout_seconds is not None and request.timeout_seconds > 0:
        deadline_ms = int(round(request.timeout_seconds * 1000))
        if deadline_ms <= MAX_DEADLINE_MS:
            protocol_request["deadline_ms"] = max(1, deadline_ms)
    validate_run_request(protocol_request)
    _write_json(protocol_request_path, protocol_request)

    normalized_events: list[dict[str, object]] = []

    def emit_normalized(event: dict[str, object]) -> None:
        normalized_events.append(dict(event))
        _append_jsonl(protocol_events_path, event)

    adapter = PiProtocolAdapter(
        run_id=protocol_run_id,
        capabilities=capabilities,
        emit=emit_normalized,
    )
    adapter.start()

    def record_raw(event: dict[str, Any]) -> None:
        _append_jsonl(events_path, event)
        adapter.consume(event)

    client = PiRpcClient(
        package_dir=paths.pi.package_dir,
        cwd=request.cwd,
        agent_dir=paths.pi.agent_dir,
        provider=request.provider,
        model=request.model,
        tools=request.tools,
        show_tools=request.show_tools,
        system_prompt_file=request.system_prompt_file,
        append_system_prompt_file=request.append_system_prompt_file,
        extra_args=request.extra_args,
        literal_extra_args=_pi_extra_args(request),
        keep_session=request.keep_session,
        node_max_old_space_size_mb=request.node_max_old_space_size_mb,
        stream_text=request.stream_text,
    )
    try:
        client.start()
        final_text = client.prompt_and_wait(
            request.question,
            max_turns=request.max_turns,
            timeout_seconds=request.timeout_seconds,
            on_event=record_raw,
        )
        final_path.write_text(_with_trailing_newline(final_text), encoding="utf-8")
        adapter.complete(
            artifact={
                "artifact_id": "final-answer",
                "kind": "answer",
                "media_type": "text/plain",
                "uri": "final.txt",
            }
        )
        validate_event_stream(normalized_events)
        _write_state(
            state_path,
            request,
            attempt - 1,
            "completed",
            question_path,
            final_path,
            events_path,
            stderr_path,
        )
        return DciRunResult(
            output_dir=destination,
            final_text=final_text,
            events=tuple(RunEvent.from_mapping(event) for event in normalized_events),
            status="completed",
        )
    except (OSError, RuntimeError, ValueError):
        if not adapter.terminal:
            adapter.fail()
        stderr_getter = getattr(client, "get_stderr", None)
        stderr_text = stderr_getter() if callable(stderr_getter) else ""
        _write_bounded(stderr_path, stderr_text)
        _write_state(
            state_path,
            request,
            attempt - 1,
            "failed",
            question_path,
            final_path,
            events_path,
            stderr_path,
        )
        raise DciRunError("DCI Pi execution failed") from None
    finally:
        client.stop()


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _pi_extra_args(request: DciRunRequest) -> tuple[str, ...]:
    """Return only typed controls advertised by the current Pi CLI."""

    values: list[str] = []
    if request.thinking_level:
        values.extend(["--thinking", request.thinking_level])
    return tuple(values)


def _runtime_context_control(request: DciRunRequest) -> dict[str, object] | None:
    """Record an explicit diagnostic for a legacy request Pi cannot implement.

    Current Pi exposes no runtime context-level control.  Do not fabricate an
    argv flag: the source runtime-context example controls Pi thinking instead.
    """

    if request.runtime_context_level is None:
        return None
    return {
        "requested_level": request.runtime_context_level,
        "effective_pi_control": None,
        "status": "unsupported",
    }


def _append_jsonl(path: Path, value: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def _with_trailing_newline(value: str) -> str:
    return value if value.endswith("\n") else f"{value}\n"


def _write_bounded(path: Path, stderr_text: str, *, limit: int = 16_384) -> None:
    path.write_text(stderr_text[-limit:], encoding="utf-8")


def _write_state(
    path: Path,
    request: DciRunRequest,
    resume_count: int,
    status: str,
    question_path: Path,
    final_path: Path,
    events_path: Path,
    stderr_path: Path,
) -> None:
    _write_json(
        path,
        {
            "run_id": request.run_id,
            "status": status,
            "question": request.question,
            "cwd": str(request.cwd),
            "provider": request.provider,
            "model": request.model,
            "tools": request.tools,
            "max_turns": request.max_turns,
            "runtime_context_level": request.runtime_context_level,
            "runtime_context_control": _runtime_context_control(request),
            "thinking_level": request.thinking_level,
            "node_max_old_space_size_mb": request.node_max_old_space_size_mb,
            "keep_session": request.keep_session,
            "resume_count": resume_count,
            "question_path": str(question_path),
            "final_path": str(final_path),
            "events_path": str(events_path),
            "stderr_path": str(stderr_path),
        },
    )


def _load_resume_state(destination: Path) -> dict[str, object]:
    try:
        value = json.loads((destination / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise DciRunError("DCI resume validation failed") from None
    if not isinstance(value, dict):
        raise DciRunError("DCI resume validation failed")
    return value


def _validate_resume_request(state: dict[str, object], request: DciRunRequest) -> None:
    if state.get("status") == "completed":
        raise DciRunError("DCI resume validation failed")
    expected = {
        "run_id": request.run_id,
        "question": request.question,
        "cwd": str(request.cwd),
        "provider": request.provider,
        "model": request.model,
        "tools": request.tools,
        "max_turns": request.max_turns,
        "runtime_context_level": request.runtime_context_level,
        "thinking_level": request.thinking_level,
        "node_max_old_space_size_mb": request.node_max_old_space_size_mb,
        "keep_session": request.keep_session,
    }
    if any(state.get(name) != value for name, value in expected.items()):
        raise DciRunError("DCI resume validation failed")


def _required_string(state: dict[str, object], name: str) -> str:
    value = state.get(name)
    if not isinstance(value, str) or not value:
        raise DciRunError("DCI resume validation failed")
    return value


def _optional_string(state: dict[str, object], name: str) -> str | None:
    value = state.get(name)
    if value is None:
        return None
    if not isinstance(value, str):
        raise DciRunError("DCI resume validation failed")
    return value


def _optional_int(state: dict[str, object], name: str) -> int | None:
    value = state.get(name)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise DciRunError("DCI resume validation failed")
    return value


def _optional_positive_int(state: dict[str, object], name: str) -> int | None:
    value = _optional_int(state, name)
    if value is not None and value <= 0:
        raise DciRunError("DCI resume validation failed")
    return value


def _required_bool(state: dict[str, object], name: str) -> bool:
    value = state.get(name)
    if not isinstance(value, bool):
        raise DciRunError("DCI resume validation failed")
    return value
