"""Durable native artifacts for an independent Asterion DCI run."""

from __future__ import annotations

import json
import os
import secrets
import socket
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from asterion.adapters.pi import PiProtocolAdapter, map_pi_capabilities
from asterion.dci.config import DciPaths
from asterion.dci.run import DciRunRequest
from asterion.runtime.host import RunEvent
from asterion.runtime.protocol import PROTOCOL_VERSION, validate_event_stream, validate_run_request

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
        lock_path = directory.absolute() / cls.LOCK_NAME
        owner_token = secrets.token_hex(32)
        payload = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "owner_token": owner_token,
        }
        try:
            _validate_lock_metadata_at(descriptor, cls.LOCK_NAME)
            _atomic_write_json_at(descriptor, cls.LOCK_NAME, payload)
        except BaseException:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
            raise
        return cls(path=lock_path, owner_token=owner_token, _directory_fd=descriptor)

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
            self._protocol_fd = _open_private_directory_at(self._root_fd, "protocol")
            if resume:
                self.state = _read_json_object_at(self._root_fd, "state.json")
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
            else:
                attempt = 1
                _write_private_text_at(self._root_fd, "events.jsonl", "")
                _write_private_text_at(self._root_fd, "question.txt", f"{request.question}\n")
                self.state = {
                    "run_id": request.run_id,
                    "status": "running",
                    "question": request.question,
                    "cwd": str(request.cwd),
                    "provider": request.provider,
                    "model": request.model,
                    "tools": request.tools,
                    "event_count": 0,
                    "assistant_text": "",
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
                    "messages": [],
                    "final_text": None,
                }
                self.latest_model_context = {"status": "running", "latest": None}
            attempt_stem = f"attempt-{attempt:04d}"
            self._protocol_request_name = f"{attempt_stem}.request.json"
            self._protocol_events_name = f"{attempt_stem}.events.jsonl"
            self.protocol_request_path = self.protocol_dir / self._protocol_request_name
            self.protocol_events_path = self.protocol_dir / self._protocol_events_name
            _write_private_text_at(self._protocol_fd, self._protocol_events_name, "")
            self.normalized: list[dict[str, object]] = []
            capabilities = map_pi_capabilities(request.tools)
            protocol_request: dict[str, object] = {
                "protocol": PROTOCOL_VERSION,
                "run_id": f"{request.run_id}-{attempt_stem}",
                "input": {"text": request.question},
                "requested_capabilities": capabilities,
            }
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
            if event.get("type") == "message_update":
                assistant = event.get("assistantMessageEvent")
                if isinstance(assistant, dict) and assistant.get("type") == "text_delta":
                    delta = assistant.get("delta")
                    if isinstance(delta, str):
                        self.state["assistant_text"] += delta
            if event.get("type") == "message_end":
                message = event.get("message")
                if isinstance(message, dict):
                    self.conversation_full["messages"].append(json.loads(json.dumps(message)))
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
            if stderr_text:
                _write_private_text_at(
                    self._root_fd,
                    "stderr.txt",
                    stderr_text[-16384:],
                )
            self.state["status"] = status
            self.state["assistant_text"] = answer
            self.conversation_full["status"] = status
            self.conversation_full["final_text"] = answer
            if status == "completed":
                self.adapter.complete(
                    artifact={
                        "artifact_id": "final-answer",
                        "kind": "answer",
                        "media_type": "text/plain",
                        "uri": "final.txt",
                    }
                )
            else:
                self.adapter.fail()
            validate_event_stream(self.normalized)
            self._write()
            return tuple(RunEvent.from_mapping(event) for event in self.normalized)
        finally:
            self.close()

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
        for message in conversation["messages"]:
            if message.get("role") != "toolResult":
                continue
            if self.features.externalize_tool_results:
                call_id = str(message.get("toolCallId") or "event")
                tool_results_fd = _open_private_directory_at(self._root_fd, "tool_results")
                try:
                    _atomic_write_json_at(
                        tool_results_fd,
                        f"{call_id}.json",
                        {"message": message},
                    )
                finally:
                    os.close(tool_results_fd)
            if self.features.clear_tool_results:
                message["content"] = [{"type": "text", "text": "[tool result cleared from conversation context]"}]
        return conversation

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
