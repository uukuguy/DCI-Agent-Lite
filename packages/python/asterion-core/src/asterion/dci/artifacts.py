"""Durable native artifacts for an independent Asterion DCI run."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import socket
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from asterion.adapters.pi import PiProtocolAdapter, map_pi_capabilities
from asterion.dci.config import DciPaths
from asterion.dci.provenance import collect_pi_provenance
from asterion.dci.run import DciRunRequest
from asterion.runtime.host import RunEvent
from asterion.runtime.protocol import (
    MAX_DEADLINE_MS,
    PROTOCOL_VERSION,
    validate_event_stream,
    validate_run_request,
)

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised only on non-POSIX hosts
    fcntl = None  # type: ignore[assignment]


class DciArtifactError(RuntimeError):
    """Safe failure at the native artifact filesystem boundary."""


def _reject_symlink(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise DciArtifactError(f"DCI {label} must not be a symlink")


def _open_flags(flags: int) -> int:
    return flags | getattr(os, "O_NOFOLLOW", 0)


def _validate_leaf_name(name: str) -> None:
    if not name or name in {".", ".."} or Path(name).name != name:
        raise DciArtifactError("DCI artifact name is invalid")


def _read_json_object_at(directory_fd: int, name: str) -> dict[str, Any]:
    _validate_leaf_name(name)
    descriptor: int | None = None
    try:
        descriptor = os.open(name, _open_flags(os.O_RDONLY), dir_fd=directory_fd)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise DciArtifactError("DCI artifact JSON is invalid")
        handle = os.fdopen(descriptor, encoding="utf-8")
        descriptor = None
        with handle:
            value = json.load(handle)
    except DciArtifactError:
        raise
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DciArtifactError("DCI artifact JSON is invalid") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    if not isinstance(value, dict):
        raise DciArtifactError("DCI artifact JSON is invalid")
    return value


def _reject_symlink_at(directory_fd: int, name: str, *, label: str) -> None:
    _validate_leaf_name(name)
    try:
        entry = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    if stat.S_ISLNK(entry.st_mode):
        raise DciArtifactError(f"DCI {label} must not be a symlink")


def _atomic_write_json_at(directory_fd: int, name: str, payload: Any) -> None:
    _validate_leaf_name(name)
    _reject_symlink_at(directory_fd, name, label="JSON target")
    temporary = f".{name}.{secrets.token_hex(16)}.tmp"
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            _open_flags(os.O_CREAT | os.O_EXCL | os.O_WRONLY),
            0o600,
            dir_fd=directory_fd,
        )
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = None
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(
            temporary,
            name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
        )
        try:
            os.fsync(directory_fd)
        except OSError:
            # Some filesystems do not support directory fsync; the file itself is durable.
            pass
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            os.unlink(temporary, dir_fd=directory_fd)
        except FileNotFoundError:
            pass


def _open_directory(path: Path) -> int:
    _reject_symlink(path, label="directory")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        return os.open(path, _open_flags(flags))
    except OSError as exc:
        raise DciArtifactError("DCI artifact directory is invalid") from exc


def _open_private_directory_at(parent_fd: int, name: str) -> int:
    _validate_leaf_name(name)
    try:
        os.mkdir(name, 0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(name, _open_flags(flags), dir_fd=parent_fd)
    except OSError as exc:
        raise DciArtifactError("DCI artifact directory is invalid") from exc
    try:
        os.fchmod(descriptor, 0o700)
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def atomic_write_json(path: Path, payload: Any) -> None:
    """Atomically replace one private JSON document in its existing directory."""

    destination = Path(path)
    parent = destination.parent
    _reject_symlink(parent, label="JSON parent")
    try:
        resolved_parent = parent.resolve(strict=True)
    except OSError as exc:
        raise DciArtifactError("DCI JSON parent is invalid") from exc
    if not resolved_parent.is_dir():
        raise DciArtifactError("DCI JSON parent is invalid")
    directory_fd = _open_directory(resolved_parent)
    try:
        _atomic_write_json_at(directory_fd, destination.name, payload)
    finally:
        os.close(directory_fd)


def _read_json_object(path: Path) -> dict[str, Any]:
    directory_fd = _open_directory(path.parent)
    try:
        return _read_json_object_at(directory_fd, path.name)
    finally:
        os.close(directory_fd)


def _validate_lock_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"pid", "hostname", "created_at", "owner_token"}:
        raise DciArtifactError("DCI run lock is invalid")
    pid = payload["pid"]
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise DciArtifactError("DCI run lock is invalid")
    if not isinstance(payload["hostname"], str) or not payload["hostname"]:
        raise DciArtifactError("DCI run lock is invalid")
    if not isinstance(payload["owner_token"], str) or not payload["owner_token"]:
        raise DciArtifactError("DCI run lock is invalid")
    created_at = payload["created_at"]
    if not isinstance(created_at, str):
        raise DciArtifactError("DCI run lock is invalid")
    try:
        timestamp = datetime.fromisoformat(created_at)
    except ValueError as exc:
        raise DciArtifactError("DCI run lock is invalid") from exc
    if timestamp.tzinfo is None:
        raise DciArtifactError("DCI run lock is invalid")
    return payload


def _lock_payload_at(directory_fd: int, name: str) -> dict[str, Any]:
    return _validate_lock_payload(_read_json_object_at(directory_fd, name))


def _lock_payload(path: Path) -> dict[str, Any]:
    return _validate_lock_payload(_read_json_object(path))


def _acquire_directory_fd(path: Path) -> int:
    """Open, verify, privatize, and exclusively lock one run directory."""

    if fcntl is None:
        raise DciArtifactError("DCI run locking is unavailable")
    _reject_symlink(path, label="output directory")
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    _reject_symlink(path, label="output directory")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, _open_flags(flags))
    except OSError as exc:
        raise DciArtifactError("DCI output directory is invalid") from exc
    try:
        os.fchmod(descriptor, 0o700)
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(descriptor)
        raise DciArtifactError("DCI run directory is locked") from exc
    except OSError as exc:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise DciArtifactError("DCI run locking failed") from exc
    return descriptor


def _validate_lock_metadata_at(directory_fd: int, name: str) -> None:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    metadata = _lock_payload_at(directory_fd, name)
    if metadata["hostname"] != socket.gethostname():
        raise DciArtifactError("DCI run lock metadata is foreign")


@dataclass
class DciRunLock:
    """OS-backed exclusive lock plus diagnostic metadata for one run directory."""

    LOCK_NAME = ".dci-run.lock"

    path: Path
    owner_token: str
    _directory_fd: int
    _released: bool = False

    @classmethod
    def acquire(cls, output_dir: Path) -> DciRunLock:
        directory = Path(output_dir)
        descriptor = _acquire_directory_fd(directory)
        try:
            lock_path = directory.absolute() / cls.LOCK_NAME
            owner_token = secrets.token_hex(32)
            payload = {
                "pid": os.getpid(),
                "hostname": socket.gethostname(),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "owner_token": owner_token,
            }
            _validate_lock_metadata_at(descriptor, cls.LOCK_NAME)
            _atomic_write_json_at(descriptor, cls.LOCK_NAME, payload)
            return cls(path=lock_path, owner_token=owner_token, _directory_fd=descriptor)
        except BaseException:
            try:
                try:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
                except OSError:
                    pass
            finally:
                os.close(descriptor)
            raise

    def release(self) -> None:
        if self._released:
            return
        try:
            if fcntl is not None:
                fcntl.flock(self._directory_fd, fcntl.LOCK_UN)
        finally:
            try:
                os.close(self._directory_fd)
            except OSError:
                pass
            self._released = True


@dataclass(frozen=True)
class DciConversationFeatures:
    """Opt-in processing controls for the investigator-facing conversation view."""

    clear_tool_results: bool = False
    clear_tool_results_keep_last: int = 3
    externalize_tool_results: bool = False
    strip_thinking: bool = False
    strip_usage: bool = False

    def __post_init__(self) -> None:
        for name in (
            "clear_tool_results",
            "externalize_tool_results",
            "strip_thinking",
            "strip_usage",
        ):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be boolean")
        keep_last = self.clear_tool_results_keep_last
        if isinstance(keep_last, bool) or not isinstance(keep_last, int) or keep_last < 0:
            raise ValueError("clear_tool_results_keep_last must be >= 0")

    def to_mapping(self) -> dict[str, object]:
        return {
            "clear_tool_results": self.clear_tool_results,
            "clear_tool_results_keep_last": self.clear_tool_results_keep_last,
            "externalize_tool_results": self.externalize_tool_results,
            "strip_thinking": self.strip_thinking,
            "strip_usage": self.strip_usage,
        }

    @classmethod
    def from_mapping(cls, value: object) -> DciConversationFeatures:
        if value is None:
            return cls()
        if not isinstance(value, dict):
            raise ValueError("DCI conversation features are invalid")
        known = {
            "clear_tool_results",
            "clear_tool_results_keep_last",
            "externalize_tool_results",
            "strip_thinking",
            "strip_usage",
        }
        if unknown := set(value) - known:
            raise ValueError(
                f"DCI conversation features contain unknown fields: {', '.join(sorted(unknown))}"
            )
        return cls(
            clear_tool_results=value.get("clear_tool_results", False),
            clear_tool_results_keep_last=value.get("clear_tool_results_keep_last", 3),
            externalize_tool_results=value.get("externalize_tool_results", False),
            strip_thinking=value.get("strip_thinking", False),
            strip_usage=value.get("strip_usage", False),
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _duration_seconds(started_at: object, finished_at: object) -> float | None:
    if not isinstance(started_at, str) or not isinstance(finished_at, str):
        return None
    try:
        duration = datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)
    except ValueError:
        return None
    return max(0.0, duration.total_seconds())


def _safe_tool_stem(value: object) -> str:
    text = value if isinstance(value, str) else "event"
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", text.replace("\\", "/"))
    text = text.strip(".-_") or "event"
    return text[:80]


def _bounded_text_tail(value: str, maximum_bytes: int) -> str:
    encoded = value.encode("utf-8", errors="replace")
    return encoded[-maximum_bytes:].decode("utf-8", errors="replace")


def _validate_recorder_resume_state(
    state: dict[str, Any],
    request: DciRunRequest,
) -> None:
    if state.get("status") not in {"failed", "incomplete", "running"}:
        raise DciArtifactError("DCI resume state is invalid")
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
        raise DciArtifactError("DCI resume state is invalid")


def _write_private_text_at(
    directory_fd: int,
    name: str,
    value: str,
    *,
    append: bool = False,
) -> None:
    _validate_leaf_name(name)
    _reject_symlink_at(directory_fd, name, label="artifact target")
    flags = os.O_CREAT | os.O_WRONLY | (os.O_APPEND if append else os.O_TRUNC)
    descriptor = os.open(name, _open_flags(flags), 0o600, dir_fd=directory_fd)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "a" if append else "w", encoding="utf-8") as handle:
            handle.write(value)
            handle.flush()
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _write_private_text(path: Path, value: str, *, append: bool = False) -> None:
    destination = Path(path)
    directory_fd = _open_directory(destination.parent)
    try:
        _write_private_text_at(directory_fd, destination.name, value, append=append)
    finally:
        os.close(directory_fd)


class DciRunRecorder:
    """Persist raw and processed DCI run evidence without crossing product boundaries."""

    def __init__(
        self,
        *,
        output_dir: Path,
        request: DciRunRequest,
        paths: DciPaths,
        features: DciConversationFeatures | None = None,
        resume: bool = False,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.request = request
        self.paths = paths
        self.features = features or DciConversationFeatures()
        self.lock = DciRunLock.acquire(self.output_dir)
        self._root_fd = self.lock._directory_fd
        self._protocol_fd: int | None = None
        self._closed = False
        self.events_path = self.output_dir / "events.jsonl"
        self.state_path = self.output_dir / "state.json"
        self.question_path = self.output_dir / "question.txt"
        self.final_path = self.output_dir / "final.txt"
        self.stderr_path = self.output_dir / "stderr.txt"
        self.conversation_full_path = self.output_dir / "conversation_full.json"
        self.conversation_path = self.output_dir / "conversation.json"
        self.latest_model_context_path = self.output_dir / "latest_model_context.json"
        self.protocol_dir = self.output_dir / "protocol"
        try:
            if resume:
                self.state = _read_json_object_at(self._root_fd, "state.json")
                _validate_recorder_resume_state(self.state, request)
                persisted_features = DciConversationFeatures.from_mapping(
                    self.state.get("conversation_features")
                )
                if features is None:
                    self.features = persisted_features
                elif self.features != persisted_features:
                    raise DciArtifactError("DCI resume state is invalid")
                self.conversation_full = _read_json_object_at(
                    self._root_fd,
                    "conversation_full.json",
                )
                self.latest_model_context = _read_json_object_at(
                    self._root_fd,
                    "latest_model_context.json",
                )
                prior_resume_count = self.state.get("resume_count", 0)
                if isinstance(prior_resume_count, bool) or not isinstance(prior_resume_count, int):
                    raise DciArtifactError("DCI resume state is invalid")
                attempt = prior_resume_count + 2
                self.state["resume_count"] = prior_resume_count + 1
                self.state["status"] = "running"
                self.conversation_full["status"] = "running"
                self.latest_model_context["status"] = "running"
                self.conversation_full["pending_message"] = None
            else:
                existing_names = set(os.listdir(self._root_fd))
                if existing_names - {DciRunLock.LOCK_NAME}:
                    raise DciArtifactError("DCI output directory is not empty")
                attempt = 1
                _write_private_text_at(self._root_fd, "events.jsonl", "")
                _write_private_text_at(self._root_fd, "question.txt", f"{request.question}\n")
                self.state = {
                    "run_id": request.run_id,
                    "status": "running",
                    "question_path": str(self.question_path),
                    "final_path": str(self.final_path),
                    "events_path": str(self.events_path),
                    "stderr_path": str(self.stderr_path),
                    "question": request.question,
                    "cwd": str(request.cwd),
                    "provider": request.provider,
                    "model": request.model,
                    "tools": request.tools,
                    "max_turns": request.max_turns,
                    "runtime_context_level": request.runtime_context_level,
                    "runtime_context_control": (
                        {
                            "requested_level": request.runtime_context_level,
                            "effective_pi_control": None,
                            "status": "unsupported",
                        }
                        if request.runtime_context_level is not None
                        else None
                    ),
                    "thinking_level": request.thinking_level,
                    "node_max_old_space_size_mb": request.node_max_old_space_size_mb,
                    "keep_session": request.keep_session,
                    "system_prompt_file": (
                        str(request.system_prompt_file) if request.system_prompt_file else None
                    ),
                    "append_system_prompt_file": (
                        str(request.append_system_prompt_file)
                        if request.append_system_prompt_file
                        else None
                    ),
                    "conversation_features": self.features.to_mapping(),
                    "event_count": 0,
                    "last_event_type": None,
                    "assistant_text": "",
                    "messages": [],
                    "tool_calls": [],
                    "notes": [],
                    "attempts": [],
                    "resume_count": 0,
                    "paths": {
                        "events_jsonl": str(self.events_path),
                        "conversation_full_json": str(self.conversation_full_path),
                        "conversation_json": str(self.conversation_path),
                        "latest_model_context_json": str(self.latest_model_context_path),
                        "final_txt": str(self.final_path),
                        "stderr_txt": str(self.stderr_path),
                    },
                }
                self.conversation_full = {
                    "status": "running",
                    "question": request.question,
                    "cwd": str(request.cwd),
                    "provider": request.provider,
                    "model": request.model,
                    "conversation_features": self.features.to_mapping(),
                    "messages": [],
                    "pending_message": None,
                    "final_text": None,
                    "notes": [],
                    "pi_source_attempts": [],
                }
                self._add_system_prompt()
                self.latest_model_context = {
                    "status": "running",
                    "question": request.question,
                    "cwd": str(request.cwd),
                    "provider": request.provider,
                    "model": request.model,
                    "conversation_features": self.features.to_mapping(),
                    "request_count": 0,
                    "runtime_context_management": None,
                    "latest": None,
                    "notes": [],
                    "pi_source_attempts": [],
                }
            self._protocol_fd = _open_private_directory_at(self._root_fd, "protocol")
            attempt_stem = f"attempt-{attempt:04d}"
            self._attempt_stem = attempt_stem
            self.pi_source = collect_pi_provenance(
                paths.pi.package_dir,
                paths.repo_root / "pi-revision.txt",
                os.environ.get("DCI_PI_REVISION") or None,
            )
            for artifact in (self.state, self.conversation_full, self.latest_model_context):
                snapshots = artifact.setdefault("pi_source_attempts", [])
                if not isinstance(snapshots, list):
                    raise DciArtifactError("DCI resume state is invalid")
                snapshots.append(json.loads(json.dumps(self.pi_source)))
            attempts = self.state.setdefault("attempts", [])
            if not isinstance(attempts, list):
                raise DciArtifactError("DCI resume state is invalid")
            self._attempt_index = len(attempts)
            attempts.append(
                {
                    "attempt": attempt,
                    "status": "running",
                    "command_summary": self._command_summary(),
                    "stderr_tail_characters": 0,
                }
            )
            self._protocol_request_name = f"{attempt_stem}.request.json"
            self._protocol_events_name = f"{attempt_stem}.events.jsonl"
            self.protocol_request_path = self.protocol_dir / self._protocol_request_name
            self.protocol_events_path = self.protocol_dir / self._protocol_events_name
            _write_private_text_at(self._protocol_fd, self._protocol_events_name, "")
            self.normalized: list[dict[str, object]] = []
            self._restore_tool_timing_indexes()
            capabilities = map_pi_capabilities(request.tools)
            protocol_request: dict[str, object] = {
                "protocol": PROTOCOL_VERSION,
                "run_id": f"{request.run_id}-{attempt_stem}",
                "input": {"text": request.question},
                "requested_capabilities": capabilities,
            }
            if request.timeout_seconds is not None and request.timeout_seconds > 0:
                deadline_ms = int(round(request.timeout_seconds * 1000))
                if deadline_ms <= MAX_DEADLINE_MS:
                    protocol_request["deadline_ms"] = max(1, deadline_ms)
            validate_run_request(protocol_request)
            _atomic_write_json_at(self._protocol_fd, self._protocol_request_name, protocol_request)
            self.adapter = PiProtocolAdapter(
                run_id=str(protocol_request["run_id"]),
                capabilities=capabilities,
                emit=self._emit_normalized,
            )
            self.adapter.start()
            self._write()
        except BaseException:
            self.close()
            raise

    def _emit_normalized(self, event: dict[str, object]) -> None:
        self.normalized.append(dict(event))
        self._append_at(self._protocol_directory_fd(), self._protocol_events_name, event)

    def record_event(self, event: dict[str, object]) -> None:
        self._ensure_open()
        try:
            self._append_at(self._root_fd, "events.jsonl", event)
            self.adapter.consume(event)
            self.state["event_count"] += 1
            event_type = event.get("type")
            self.state["last_event_type"] = event_type
            recorded_at = _utc_now()
            if event_type in {"message_start", "message_end"}:
                message = event.get("message")
                self.state["messages"].append(
                    {"event": event_type, "message": json.loads(json.dumps(message))}
                )
                if event_type == "message_start":
                    self.conversation_full["pending_message"] = self._annotate_message(message)
                elif isinstance(message, dict):
                    self.conversation_full["messages"].append(self._annotate_message(message))
                    self.conversation_full["pending_message"] = None
            elif event_type == "message_update":
                assistant = event.get("assistantMessageEvent")
                if isinstance(assistant, dict) and assistant.get("type") == "text_delta":
                    delta = assistant.get("delta")
                    if isinstance(delta, str):
                        self.state["assistant_text"] += delta
                    partial = assistant.get("partial")
                    if isinstance(partial, dict):
                        self.conversation_full["pending_message"] = self._annotate_message(partial)
            elif event_type in {"tool_execution_start", "tool_execution_end"}:
                self._record_tool_timing(event, recorded_at=recorded_at)
            elif event_type == "provider_request_context":
                self._record_latest_model_context(event)
            self._write()
        except BaseException:
            self.close()
            raise

    def finalize(self, *, status: str, final_text: str = "", stderr_text: str = "") -> tuple[RunEvent, ...]:
        self._ensure_open()
        try:
            answer = final_text or self.state["assistant_text"]
            if answer:
                _write_private_text_at(
                    self._root_fd,
                    "final.txt",
                    answer if answer.endswith("\n") else f"{answer}\n",
                )
            stderr_tail = _bounded_text_tail(stderr_text, 16384)
            stderr_section = f"[{self._attempt_stem} status={status}]\n{stderr_tail}"
            if stderr_tail and not stderr_tail.endswith("\n"):
                stderr_section += "\n"
            _write_private_text_at(
                self._root_fd,
                "stderr.txt",
                stderr_section,
                append=self._attempt_index > 0,
            )
            attempt_record = self.state["attempts"][self._attempt_index]
            attempt_record["status"] = status
            attempt_record["stderr_tail_characters"] = len(stderr_tail)
            self.state["status"] = status
            self.state["assistant_text"] = answer
            self.conversation_full["status"] = status
            self.conversation_full["final_text"] = answer
            self.conversation_full["pending_message"] = None
            self.latest_model_context["status"] = status
            if status == "completed":
                artifact = None
                if answer:
                    digest = hashlib.sha256(
                        answer.encode("utf-8") + (b"" if answer.endswith("\n") else b"\n")
                    ).hexdigest()
                    artifact = {
                        "artifact_id": "final-answer",
                        "kind": "answer",
                        "media_type": "text/plain",
                        "uri": "final.txt",
                        "sha256": digest,
                    }
                self.adapter.complete(artifact=artifact)
            else:
                self.adapter.fail()
            validate_event_stream(self.normalized)
            self._write()
            return tuple(RunEvent.from_mapping(event) for event in self.normalized)
        finally:
            self.close()

    def add_note(self, note: str) -> None:
        """Persist one caller-generated safe diagnostic note in every native view."""

        self._ensure_open()
        for artifact in (self.state, self.conversation_full, self.latest_model_context):
            notes = artifact.setdefault("notes", [])
            if not isinstance(notes, list):
                raise DciArtifactError("DCI artifact notes are invalid")
            notes.append(note)
        self._write()

    def close(self) -> None:
        """Idempotently release this recorder's owned writer lock."""

        if self._closed:
            return
        if self._protocol_fd is not None:
            try:
                os.close(self._protocol_fd)
            except OSError:
                pass
            self._protocol_fd = None
        self.lock.release()
        self._closed = True

    def __enter__(self) -> DciRunRecorder:
        self._ensure_open()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _ensure_open(self) -> None:
        if self._closed:
            raise DciArtifactError("DCI run recorder is closed")

    def _command_summary(self) -> dict[str, object]:
        option_names = ["--mode"]
        if self.request.provider is not None:
            option_names.append("--provider")
        if self.request.model is not None:
            option_names.append("--model")
        if self.request.tools:
            option_names.append("--tools")
        if self.request.system_prompt_file is not None:
            option_names.append("--system-prompt")
        if self.request.append_system_prompt_file is not None:
            option_names.append("--append-system-prompt")
        if not self.request.keep_session:
            option_names.append("--no-session")
        typed_count = 1 if self.request.thinking_level is not None else 0
        return {
            "executable": "node",
            "mode": "rpc",
            "option_names": option_names,
            "configured_extra_argument_groups": len(self.request.extra_args),
            "typed_extra_argument_count": typed_count,
        }

    def _write(self) -> None:
        _atomic_write_json_at(self._root_fd, "state.json", self.state)
        _atomic_write_json_at(self._root_fd, "conversation_full.json", self.conversation_full)
        _atomic_write_json_at(
            self._root_fd,
            "latest_model_context.json",
            self.latest_model_context,
        )
        _atomic_write_json_at(
            self._root_fd,
            "conversation.json",
            self._processed_conversation(),
        )

    def _processed_conversation(self) -> dict[str, Any]:
        conversation = json.loads(json.dumps(self.conversation_full))
        messages = conversation.get("messages", [])
        if not isinstance(messages, list):
            return conversation
        tool_messages = [message for message in messages if message.get("role") == "toolResult"]
        tool_names = self._tool_result_names(tool_messages)
        if self.features.externalize_tool_results and tool_messages:
            tool_results_fd = _open_private_directory_at(self._root_fd, "tool_results")
            try:
                for message, name in zip(tool_messages, tool_names, strict=True):
                    stats = self._tool_result_stats(message)
                    payload = {"saved_at": _utc_now(), "message": json.loads(json.dumps(message))}
                    _atomic_write_json_at(tool_results_fd, name, payload)
                    context = self._tool_result_context(message)
                    context["externalized"] = {
                        "path": f"tool_results/{name}",
                        "saved_at": payload["saved_at"],
                        "stats": stats,
                    }
            finally:
                os.close(tool_results_fd)
        if self.features.clear_tool_results:
            clear_count = max(0, len(tool_messages) - self.features.clear_tool_results_keep_last)
            for message in tool_messages[:clear_count]:
                self._clear_tool_result(message)
        for message in messages:
            self._strip_processed_assistant_fields(message)
        pending = conversation.get("pending_message")
        if isinstance(pending, dict):
            self._strip_processed_assistant_fields(pending)
        return conversation

    def _add_system_prompt(self) -> None:
        parts: list[str] = []
        for path in (self.request.system_prompt_file, self.request.append_system_prompt_file):
            if path is not None:
                parts.append(Path(path).read_text(encoding="utf-8").strip("\n"))
        if not parts:
            return
        self.conversation_full["messages"].append(
            {
                "role": "system",
                "content": [{"type": "text", "text": "\n\n".join(parts)}],
                "sources": {
                    "system_prompt_file": (
                        str(self.request.system_prompt_file) if self.request.system_prompt_file else None
                    ),
                    "append_system_prompt_file": (
                        str(self.request.append_system_prompt_file)
                        if self.request.append_system_prompt_file
                        else None
                    ),
                },
            }
        )

    def _restore_tool_timing_indexes(self) -> None:
        self._pending_tool_starts: dict[str, str] = {}
        self._completed_tool_timings: dict[str, dict[str, object]] = {}
        for entry in self.state.get("tool_calls", []):
            if not isinstance(entry, dict):
                continue
            call_id = entry.get("toolCallId")
            if not isinstance(call_id, str) or not call_id:
                continue
            if entry.get("event") == "tool_execution_start" and isinstance(
                entry.get("recorded_at"), str
            ):
                self._pending_tool_starts[call_id] = str(entry["recorded_at"])
            elif entry.get("event") == "tool_execution_end":
                timing = self._tool_timing(
                    call_id,
                    entry.get("started_at"),
                    entry.get("finished_at") or entry.get("recorded_at"),
                )
                if timing is not None:
                    self._completed_tool_timings[call_id] = timing
                self._pending_tool_starts.pop(call_id, None)
        self._refresh_tool_annotations()

    def _record_tool_timing(self, event: dict[str, object], *, recorded_at: str) -> None:
        call_id = event.get("toolCallId")
        started_at: str | None = None
        finished_at: str | None = None
        timing: dict[str, object] | None = None
        if isinstance(call_id, str) and call_id:
            if event.get("type") == "tool_execution_start":
                started_at = recorded_at
                self._pending_tool_starts[call_id] = recorded_at
            else:
                started_at = self._pending_tool_starts.pop(call_id, None)
                finished_at = recorded_at
                timing = self._tool_timing(call_id, started_at, finished_at)
                if timing is not None:
                    self._completed_tool_timings[call_id] = timing
        self.state["tool_calls"].append(
            {
                "recorded_at": recorded_at,
                "event": event.get("type"),
                "toolCallId": call_id,
                "toolName": event.get("toolName"),
                "args": event.get("args"),
                "isError": event.get("isError"),
                "result": event.get("result"),
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": timing.get("duration_seconds") if timing else None,
            }
        )
        self._refresh_tool_annotations()

    @staticmethod
    def _tool_timing(
        call_id: str, started_at: object, finished_at: object
    ) -> dict[str, object] | None:
        duration = _duration_seconds(started_at, finished_at)
        if duration is None or not isinstance(started_at, str) or not isinstance(finished_at, str):
            return None
        return {
            "tool_call_id": call_id,
            "status": "completed",
            "started_at": started_at,
            "finished_at": finished_at,
            "duration_seconds": duration,
            "duration_ms": int(round(duration * 1000)),
        }

    def _annotate_message(self, message: object) -> dict[str, Any] | None:
        if not isinstance(message, dict):
            return None
        result = json.loads(json.dumps(message))
        call_id = result.get("toolCallId")
        if result.get("role") == "toolResult" and isinstance(call_id, str):
            timing = self._completed_tool_timings.get(call_id)
            if timing is not None:
                result["tool_execution"] = json.loads(json.dumps(timing))
        return result

    def _refresh_tool_annotations(self) -> None:
        messages = self.conversation_full.get("messages", [])
        if isinstance(messages, list):
            self.conversation_full["messages"] = [
                self._annotate_message(message) or message for message in messages
            ]
        pending = self.conversation_full.get("pending_message")
        if isinstance(pending, dict):
            self.conversation_full["pending_message"] = self._annotate_message(pending)
        latest = self.latest_model_context.get("latest") if hasattr(self, "latest_model_context") else None
        if isinstance(latest, dict) and isinstance(latest.get("messages"), list):
            latest["messages"] = [
                self._annotate_message(message) or message for message in latest["messages"]
            ]

    def _record_latest_model_context(self, event: dict[str, object]) -> None:
        messages = event.get("messages")
        annotated = (
            [self._annotate_message(message) or message for message in messages]
            if isinstance(messages, list)
            else []
        )
        index = event.get("requestIndex")
        prior = self.latest_model_context.get("request_count", 0)
        self.latest_model_context["request_count"] = max(
            prior if isinstance(prior, int) else 0,
            index if isinstance(index, int) else 0,
        )
        runtime = json.loads(json.dumps(event.get("runtimeContextManagement")))
        self.latest_model_context["runtime_context_management"] = runtime
        self.latest_model_context["latest"] = {
            "captured_at": _utc_now(),
            "request_index": index,
            "model": event.get("model"),
            "runtime_context_management": runtime,
            "message_count": len(annotated),
            "messages": annotated,
            "payload": json.loads(json.dumps(event.get("payload"))),
        }

    @staticmethod
    def _tool_result_context(message: dict[str, Any]) -> dict[str, Any]:
        context = message.setdefault("context_management", {})
        return context.setdefault("tool_result", {})

    @staticmethod
    def _tool_result_stats(message: dict[str, Any]) -> dict[str, int]:
        texts = [
            part.get("text", "")
            for part in message.get("content", [])
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        text = "\n\n".join(value for value in texts if isinstance(value, str))
        return {
            "chars": len(text),
            "lines": len(text.splitlines()) if text else 0,
            "content_blocks": len(message.get("content", [])),
        }

    @staticmethod
    def _tool_result_names(messages: list[dict[str, Any]]) -> list[str]:
        next_suffix: dict[str, int] = {}
        reserved: set[str] = set()
        names: list[str] = []
        for message in messages:
            stem = _safe_tool_stem(message.get("toolCallId"))
            stem_key = stem.casefold()
            suffix_number = next_suffix.get(stem_key, 1)
            while True:
                suffix = "" if suffix_number == 1 else f"-{suffix_number}"
                candidate = f"{stem[: 80 - len(suffix)]}{suffix}.json"
                if candidate.casefold() not in reserved:
                    break
                suffix_number += 1
            reserved.add(candidate.casefold())
            next_suffix[stem_key] = suffix_number + 1
            names.append(candidate)
        return names

    def _clear_tool_result(self, message: dict[str, Any]) -> None:
        context = self._tool_result_context(message)
        stats = context.get("externalized", {}).get("stats") or self._tool_result_stats(message)
        context.update(
            {
                "status": "cleared",
                "stats": stats,
                "cleared_at": _utc_now(),
                "keep_last": self.features.clear_tool_results_keep_last,
            }
        )
        summary = [
            "[tool result cleared from conversation context]",
            f"tool={message.get('toolName', 'unknown')}",
            f"chars={stats.get('chars', 0)}",
            f"lines={stats.get('lines', 0)}",
        ]
        externalized = context.get("externalized")
        if isinstance(externalized, dict) and externalized.get("path"):
            summary.append(f"full_output={externalized['path']}")
        message["content"] = [{"type": "text", "text": "\n".join(summary)}]

    def _strip_processed_assistant_fields(self, message: dict[str, Any]) -> None:
        if message.get("role") != "assistant":
            return
        if self.features.strip_thinking and isinstance(message.get("content"), list):
            message["content"] = [
                part for part in message["content"] if part.get("type") != "thinking"
            ]
        if self.features.strip_usage:
            message.pop("usage", None)

    def _protocol_directory_fd(self) -> int:
        if self._protocol_fd is None:
            raise DciArtifactError("DCI run recorder is closed")
        return self._protocol_fd

    @staticmethod
    def _append_at(directory_fd: int, name: str, value: dict[str, object]) -> None:
        _write_private_text_at(
            directory_fd,
            name,
            json.dumps(value, ensure_ascii=False) + "\n",
            append=True,
        )
