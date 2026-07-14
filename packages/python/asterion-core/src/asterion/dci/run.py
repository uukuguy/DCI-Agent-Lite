"""Native artifact boundary for an independent Asterion DCI Pi run."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from typing import TYPE_CHECKING

from asterion.dci.config import DciPaths
from asterion.dci.pi_rpc import PiRpcClient
from asterion.dci.provenance import format_pi_revision_warning
from asterion.runtime.host import RunEvent

if TYPE_CHECKING:
    from asterion.dci.artifacts import DciConversationFeatures
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
    conversation_features: DciConversationFeatures | None = None
    pi_package_dir: Path | None = None
    pi_agent_dir: Path | None = None
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


_RESUME_TIMEOUT_UNSET = object()
_THINKING_LEVELS = {"off", "minimal", "low", "medium", "high", "xhigh"}


def validate_dci_run_request(
    request: DciRunRequest, paths: DciPaths | None = None
) -> None:
    """Validate every behavior-affecting request value before filesystem mutation."""

    def text(value: object, *, optional: bool = False) -> None:
        if value is None and optional:
            return
        if not isinstance(value, str) or not value.strip():
            raise ValueError("DCI run request is invalid")

    text(request.run_id)
    text(request.question)
    text(request.tools)
    text(request.provider, optional=True)
    text(request.model, optional=True)
    text(request.runtime_context_level, optional=True)
    text(request.thinking_level, optional=True)
    if request.thinking_level not in _THINKING_LEVELS | {None}:
        raise ValueError("DCI run request is invalid")
    if request.max_turns is not None and (
        isinstance(request.max_turns, bool)
        or not isinstance(request.max_turns, int)
        or request.max_turns <= 0
    ):
        raise ValueError("DCI run request is invalid")
    if request.timeout_seconds is not None and (
        isinstance(request.timeout_seconds, bool)
        or not isinstance(request.timeout_seconds, float)
        or not math.isfinite(request.timeout_seconds)
        or request.timeout_seconds < 0
    ):
        raise ValueError("DCI run request is invalid")
    if request.node_max_old_space_size_mb is not None and (
        isinstance(request.node_max_old_space_size_mb, bool)
        or not isinstance(request.node_max_old_space_size_mb, int)
        or request.node_max_old_space_size_mb <= 0
    ):
        raise ValueError("DCI run request is invalid")
    for value in (
        request.keep_session,
        request.show_tools,
        request.resume,
        request.stream_text,
    ):
        if type(value) is not bool:
            raise ValueError("DCI run request is invalid")
    if not isinstance(request.extra_args, tuple) or any(
        not isinstance(value, str) or not value for value in request.extra_args
    ):
        raise ValueError("DCI run request is invalid")
    for value in (
        request.cwd,
        request.system_prompt_file,
        request.append_system_prompt_file,
        request.pi_package_dir,
        request.pi_agent_dir,
    ):
        if value is not None and (
            not isinstance(value, Path) or not value.is_absolute()
        ):
            raise ValueError("DCI run request is invalid")
    if request.conversation_features is not None:
        from asterion.dci.artifacts import DciConversationFeatures

        if not isinstance(request.conversation_features, DciConversationFeatures):
            raise ValueError("DCI run request is invalid")
    if paths is not None:
        for value in (
            paths.repo_root,
            paths.output_root,
            paths.pi.repo_dir,
            paths.pi.package_dir,
            paths.pi.agent_dir,
        ):
            if not isinstance(value, Path) or not value.is_absolute():
                raise ValueError("DCI run request is invalid")
        if (
            request.pi_package_dir is not None
            and request.pi_package_dir != paths.pi.package_dir
        ):
            raise ValueError("DCI run request is invalid")
        if (
            request.pi_agent_dir is not None
            and request.pi_agent_dir != paths.pi.agent_dir
        ):
            raise ValueError("DCI run request is invalid")


def request_from_runtime_options(
    options: DciRuntimeOptions,
    *,
    run_id: str,
    question: str,
    cwd: Path,
    stream_text: bool = True,
) -> DciRunRequest:
    """Convert resolved shared runtime settings into one immutable native request."""

    request = DciRunRequest(
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
    try:
        validate_dci_run_request(request)
    except ValueError:
        raise DciRunError("DCI resume validation failed") from None
    return request


def resume_request_from_output_dir(
    output_dir: Path,
    *,
    extra_args: tuple[str, ...] | None = None,
    timeout_seconds: float | None | object = _RESUME_TIMEOUT_UNSET,
) -> DciRunRequest:
    """Reconstruct a safe immutable resume request from native run state."""

    from asterion.dci.artifacts import (
        DciArtifactError,
        DciRunLock,
        DciConversationFeatures,
        _read_json_object_at,
        extra_args_fingerprint,
    )

    lock = None
    try:
        lock = DciRunLock.acquire(Path(output_dir).absolute(), create=False)
        state = _read_json_object_at(lock._directory_fd, "state.json")
    except (DciArtifactError, OSError, ValueError):
        raise DciRunError("DCI resume validation failed") from None
    finally:
        if lock is not None:
            lock.release()
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
    persisted_timeout = _optional_timeout(state, "timeout_seconds")
    runtime_context_level = _optional_string(state, "runtime_context_level")
    thinking_level = _optional_string(state, "thinking_level")
    node_max_old_space_size_mb = _optional_positive_int(
        state, "node_max_old_space_size_mb"
    )
    keep_session = _required_bool(state, "keep_session")
    extra_args_count = _required_nonnegative_int(state, "extra_args_count")
    persisted_fingerprint = _required_string(state, "extra_args_fingerprint")
    if extra_args is None:
        if extra_args_count:
            raise DciRunError("DCI resume validation failed")
        supplied_extra_args: tuple[str, ...] = ()
    else:
        supplied_extra_args = extra_args
    try:
        supplied_fingerprint = extra_args_fingerprint(supplied_extra_args)
    except ValueError:
        raise DciRunError("DCI resume validation failed") from None
    if (
        len(supplied_extra_args) != extra_args_count
        or supplied_fingerprint != persisted_fingerprint
    ):
        raise DciRunError("DCI resume validation failed")
    show_tools = _required_bool(state, "show_tools")
    system_prompt = _optional_path(state, "system_prompt_file")
    append_system_prompt = _optional_path(state, "append_system_prompt_file")
    stream_text = _required_bool(state, "stream_text")
    if "conversation_features" not in state:
        raise DciRunError("DCI resume validation failed")
    try:
        conversation_features = DciConversationFeatures.from_mapping(
            state.get("conversation_features")
        )
    except ValueError:
        raise DciRunError("DCI resume validation failed") from None
    pi_package_dir = Path(_required_string(state, "pi_package_dir"))
    pi_agent_dir = Path(_required_string(state, "pi_agent_dir"))
    if timeout_seconds is _RESUME_TIMEOUT_UNSET:
        resumed_timeout = persisted_timeout
    elif timeout_seconds is None:
        resumed_timeout = None
    elif (
        isinstance(timeout_seconds, bool)
        or not isinstance(timeout_seconds, float)
        or not math.isfinite(timeout_seconds)
        or timeout_seconds < 0
    ):
        raise DciRunError("DCI resume validation failed")
    else:
        resumed_timeout = float(timeout_seconds)
    candidate = DciRunRequest(
        run_id=run_id,
        question=question,
        cwd=cwd,
        provider=provider,
        model=model,
        tools=tools,
        max_turns=max_turns,
        timeout_seconds=resumed_timeout,
        runtime_context_level=runtime_context_level,
        thinking_level=thinking_level,
        node_max_old_space_size_mb=node_max_old_space_size_mb,
        keep_session=keep_session,
        extra_args=supplied_extra_args,
        show_tools=show_tools,
        system_prompt_file=system_prompt,
        append_system_prompt_file=append_system_prompt,
        conversation_features=conversation_features,
        pi_package_dir=pi_package_dir,
        pi_agent_dir=pi_agent_dir,
        resume=True,
        stream_text=stream_text,
    )
    try:
        validate_dci_run_request(candidate)
    except (TypeError, ValueError):
        raise DciRunError("DCI resume validation failed") from None
    return candidate


def run_pi_research(
    paths: DciPaths,
    request: DciRunRequest,
    *,
    output_dir: Path | None = None,
    conversation_features: DciConversationFeatures | None = None,
) -> DciRunResult:
    """Run Pi once and persist complete native conversation evidence."""

    from asterion.dci.artifacts import DciArtifactError, DciRunRecorder

    if conversation_features is not None:
        if (
            request.conversation_features is not None
            and request.conversation_features != conversation_features
        ):
            raise DciRunError(
                "DCI resume validation failed"
                if request.resume
                else "DCI run request is invalid"
            )
        request = replace(request, conversation_features=conversation_features)
    try:
        validate_dci_run_request(request, paths)
    except ValueError:
        raise DciRunError(
            "DCI resume validation failed"
            if request.resume
            else "DCI run request is invalid"
        ) from None
    destination = (
        Path(output_dir)
        if output_dir is not None
        else paths.output_root / request.run_id
    )
    destination = destination.absolute()
    try:
        recorder = DciRunRecorder(
            output_dir=destination,
            request=request,
            paths=paths,
            features=request.conversation_features,
            resume=request.resume,
        )
    except DciArtifactError as exc:
        message = "DCI resume validation failed" if request.resume else str(exc)
        raise DciRunError(message) from None
    except ValueError:
        message = (
            "DCI resume validation failed"
            if request.resume
            else "DCI artifact setup failed"
        )
        raise DciRunError(message) from None

    client: PiRpcClient | None = None
    try:
        warning = format_pi_revision_warning(recorder.pi_source)
        if warning is not None:
            recorder.add_note(warning)
            print(f"[runner] WARNING: {warning}", file=sys.stderr)
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
        client.start()
        final_text = client.prompt_and_wait(
            request.question,
            max_turns=request.max_turns,
            timeout_seconds=request.timeout_seconds,
            on_event=recorder.record_event,
        )
        stderr_getter = getattr(client, "get_stderr", None)
        stderr_text = stderr_getter() if callable(stderr_getter) else ""
        normalized_events = recorder.finalize(
            status="completed",
            final_text=final_text,
            stderr_text=stderr_text,
            release_lock=False,
        )
        return DciRunResult(
            output_dir=destination,
            final_text=final_text,
            events=normalized_events,
            status="completed",
        )
    except (OSError, RuntimeError, ValueError):
        stderr_getter = (
            getattr(client, "get_stderr", None) if client is not None else None
        )
        stderr_text = stderr_getter() if callable(stderr_getter) else ""
        if not recorder._finalization_started:
            recorder.finalize(
                status="failed", stderr_text=stderr_text, release_lock=False
            )
        raise DciRunError("DCI Pi execution failed") from None
    finally:
        try:
            if client is not None:
                client.stop()
        finally:
            recorder.close()


def _pi_extra_args(request: DciRunRequest) -> tuple[str, ...]:
    """Return only typed controls advertised by the current Pi CLI."""

    values: list[str] = []
    if request.thinking_level:
        values.extend(["--thinking", request.thinking_level])
    return tuple(values)


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


def _required_nonnegative_int(state: dict[str, object], name: str) -> int:
    value = _optional_int(state, name)
    if value is None or value < 0:
        raise DciRunError("DCI resume validation failed")
    return value


def _optional_timeout(state: dict[str, object], name: str) -> float | None:
    value = state.get(name)
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, float)
        or not math.isfinite(value)
        or value < 0
    ):
        raise DciRunError("DCI resume validation failed")
    return float(value)


def _optional_path(state: dict[str, object], name: str) -> Path | None:
    value = _optional_string(state, name)
    return Path(value) if value is not None else None


def _required_bool(state: dict[str, object], name: str) -> bool:
    value = state.get(name)
    if not isinstance(value, bool):
        raise DciRunError("DCI resume validation failed")
    return value
