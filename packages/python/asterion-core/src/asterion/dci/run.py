"""Native artifact boundary for an independent Asterion DCI Pi run."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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
    extra_args: tuple[str, ...] = ()
    show_tools: bool = False
    system_prompt_file: Path | None = None
    append_system_prompt_file: Path | None = None


@dataclass(frozen=True)
class DciRunResult:
    """Completed native DCI run plus its protocol-normalized events."""

    output_dir: Path
    final_text: str
    events: tuple[RunEvent, ...]
    status: str


class DciRunError(RuntimeError):
    """Safe public error for a failed Pi execution."""


def run_pi_research(
    paths: DciPaths,
    request: DciRunRequest,
    *,
    output_dir: Path | None = None,
) -> DciRunResult:
    """Run Pi once and persist the AF-180 native artifact subset."""

    destination = Path(output_dir) if output_dir is not None else paths.output_root / request.run_id
    destination = destination.resolve()
    if destination.exists() and any(destination.iterdir()):
        raise DciRunError("DCI output directory is not empty")
    destination.mkdir(parents=True, exist_ok=True)

    question_path = destination / "question.txt"
    events_path = destination / "events.jsonl"
    final_path = destination / "final.txt"
    stderr_path = destination / "stderr.txt"
    state_path = destination / "state.json"
    protocol_dir = destination / "protocol"
    protocol_dir.mkdir(exist_ok=True)
    protocol_request_path = protocol_dir / "attempt-0001.request.json"
    protocol_events_path = protocol_dir / "attempt-0001.events.jsonl"
    question_path.write_text(f"{request.question}\n", encoding="utf-8")
    events_path.write_text("", encoding="utf-8")
    protocol_events_path.write_text("", encoding="utf-8")

    capabilities = map_pi_capabilities(request.tools)
    protocol_run_id = f"{request.run_id}-attempt-0001"
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
            request.run_id,
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
            request.run_id,
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


def _append_jsonl(path: Path, value: dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def _with_trailing_newline(value: str) -> str:
    return value if value.endswith("\n") else f"{value}\n"


def _write_bounded(path: Path, stderr_text: str, *, limit: int = 16_384) -> None:
    path.write_text(stderr_text[-limit:], encoding="utf-8")


def _write_state(
    path: Path,
    run_id: str,
    status: str,
    question_path: Path,
    final_path: Path,
    events_path: Path,
    stderr_path: Path,
) -> None:
    _write_json(
        path,
        {
            "run_id": run_id,
            "status": status,
            "question_path": str(question_path),
            "final_path": str(final_path),
            "events_path": str(events_path),
            "stderr_path": str(stderr_path),
        },
    )
