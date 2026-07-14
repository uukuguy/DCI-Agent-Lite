"""Durable native artifacts for an independent Asterion DCI run."""

from __future__ import annotations

import json
import os
import secrets
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from asterion.adapters.pi import PiProtocolAdapter, map_pi_capabilities
from asterion.dci.config import DciPaths
from asterion.dci.run import DciRunRequest
from asterion.runtime.host import RunEvent
from asterion.runtime.protocol import PROTOCOL_VERSION, validate_event_stream, validate_run_request


class DciArtifactError(RuntimeError):
    """Safe failure at the native artifact filesystem boundary."""


def _reject_symlink(path: Path, *, label: str) -> None:
    if path.is_symlink():
        raise DciArtifactError(f"DCI {label} must not be a symlink")


def _private_directory(path: Path) -> None:
    _reject_symlink(path, label="directory")
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    _reject_symlink(path, label="directory")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, _open_flags(flags))
    except OSError as exc:
        raise DciArtifactError("DCI artifact directory is invalid") from exc
    try:
        os.fchmod(descriptor, 0o700)
    finally:
        os.close(descriptor)


def _open_flags(flags: int) -> int:
    return flags | getattr(os, "O_NOFOLLOW", 0)


def _read_json_object(path: Path) -> dict[str, Any]:
    _reject_symlink(path, label="JSON file")
    try:
        descriptor = os.open(path, _open_flags(os.O_RDONLY))
        with os.fdopen(descriptor, encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DciArtifactError("DCI artifact JSON is invalid") from exc
    if not isinstance(value, dict):
        raise DciArtifactError("DCI artifact JSON is invalid")
    return value


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
    destination = resolved_parent / destination.name
    _reject_symlink(destination, label="JSON target")
    temporary = resolved_parent / f".{destination.name}.{secrets.token_hex(16)}.tmp"
    descriptor: int | None = None
    try:
        descriptor = os.open(
            temporary,
            _open_flags(os.O_CREAT | os.O_EXCL | os.O_WRONLY),
            0o600,
        )
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = None
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        try:
            directory_descriptor = os.open(resolved_parent, os.O_RDONLY)
            try:
                os.fsync(directory_descriptor)
            finally:
                os.close(directory_descriptor)
        except OSError:
            # Some filesystems do not support directory fsync; the file itself is durable.
            pass
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _lock_payload(path: Path) -> dict[str, Any]:
    payload = _read_json_object(path)
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


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        raise DciArtifactError("DCI run lock process cannot be verified") from exc
    return True


def _restore_quarantined_lock(quarantined: Path, live_path: Path) -> bool:
    """Restore without overwriting a new live owner."""

    try:
        os.link(quarantined, live_path, follow_symlinks=False)
    except FileExistsError:
        return False
    quarantined.unlink()
    return True


def _remove_owned_lock(path: Path, owner_token: str, expected_stat: os.stat_result) -> bool:
    """Atomically detach a lock name, then delete only the verified owned object."""

    quarantine_dir = path.parent / f".{path.name}.quarantine-{secrets.token_hex(16)}"
    quarantine_dir.mkdir(mode=0o700)
    quarantined = quarantine_dir / "lock"
    try:
        try:
            os.rename(path, quarantined)
        except FileNotFoundError:
            return False
        try:
            moved_stat = quarantined.stat(follow_symlinks=False)
            payload = _lock_payload(quarantined)
        except (FileNotFoundError, DciArtifactError):
            if quarantined.exists() or quarantined.is_symlink():
                _restore_quarantined_lock(quarantined, path)
            return False
        matches_inode = (moved_stat.st_dev, moved_stat.st_ino) == (
            expected_stat.st_dev,
            expected_stat.st_ino,
        )
        if not matches_inode or payload["owner_token"] != owner_token:
            _restore_quarantined_lock(quarantined, path)
            return False
        quarantined.unlink()
        return True
    finally:
        try:
            quarantine_dir.rmdir()
        except OSError:
            # Preserve an unverified raced object rather than deleting it.
            pass


def _stat_lock(path: Path) -> os.stat_result:
    _reject_symlink(path, label="run lock")
    try:
        return path.stat(follow_symlinks=False)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise DciArtifactError("DCI run lock is invalid") from exc


def _existing_lock(path: Path) -> tuple[os.stat_result, dict[str, Any]]:
    observed_stat = _stat_lock(path)
    payload = _lock_payload(path)
    current_stat = _stat_lock(path)
    if (current_stat.st_dev, current_stat.st_ino) != (
        observed_stat.st_dev,
        observed_stat.st_ino,
    ):
        raise DciArtifactError("DCI run lock changed during validation")
    return observed_stat, payload


def _write_lock_payload(descriptor: int, payload: dict[str, Any]) -> None:
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise


def _release_lock(path: Path, owner_token: str) -> bool:
    try:
        observed_stat, payload = _existing_lock(path)
    except (FileNotFoundError, DciArtifactError):
        return False
    if payload["owner_token"] != owner_token:
        return False
    return _remove_owned_lock(path, owner_token, observed_stat)


@dataclass
class DciRunLock:
    """Exclusive owner-token lock for one private native run directory."""

    LOCK_NAME = ".dci-run.lock"

    path: Path
    owner_token: str
    _released: bool = False

    @classmethod
    def acquire(cls, output_dir: Path) -> DciRunLock:
        directory = Path(output_dir)
        _private_directory(directory)
        resolved_directory = directory.resolve(strict=True)
        lock_path = resolved_directory / cls.LOCK_NAME
        owner_token = secrets.token_hex(32)
        payload = {
            "pid": os.getpid(),
            "hostname": socket.gethostname(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "owner_token": owner_token,
        }
        for _ in range(4):
            try:
                descriptor = os.open(
                    lock_path,
                    _open_flags(os.O_CREAT | os.O_EXCL | os.O_WRONLY),
                    0o600,
                )
            except FileExistsError:
                try:
                    observed_stat, existing = _existing_lock(lock_path)
                except FileNotFoundError:
                    continue
                if existing["hostname"] != socket.gethostname():
                    raise DciArtifactError("DCI run directory is locked")
                if _pid_is_alive(existing["pid"]):
                    raise DciArtifactError("DCI run directory is locked")
                if not _remove_owned_lock(lock_path, existing["owner_token"], observed_stat):
                    raise DciArtifactError("DCI run lock changed during acquisition")
                continue
            created_stat = os.fstat(descriptor)
            try:
                _write_lock_payload(descriptor, payload)
            except BaseException:
                _remove_owned_lock(lock_path, owner_token, created_stat)
                raise
            return cls(path=lock_path, owner_token=owner_token)
        raise DciArtifactError("DCI run lock could not be acquired")

    def release(self) -> None:
        if self._released:
            return
        _release_lock(self.path, self.owner_token)
        self._released = True


@dataclass(frozen=True)
class DciConversationFeatures:
    """Opt-in processing controls for the investigator-facing conversation view."""

    clear_tool_results: bool = False
    clear_tool_results_keep_last: int = 3
    externalize_tool_results: bool = False
    strip_thinking: bool = False
    strip_usage: bool = False


def _write_private_text(path: Path, value: str, *, append: bool = False) -> None:
    destination = Path(path)
    _reject_symlink(destination, label="artifact target")
    flags = os.O_CREAT | os.O_WRONLY | (os.O_APPEND if append else os.O_TRUNC)
    descriptor = os.open(destination, _open_flags(flags), 0o600)
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
            _private_directory(self.protocol_dir)
            if resume:
                self.state = _read_json_object(self.state_path)
                self.conversation_full = _read_json_object(self.conversation_full_path)
                self.latest_model_context = _read_json_object(self.latest_model_context_path)
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
                _write_private_text(self.events_path, "")
                _write_private_text(self.question_path, f"{request.question}\n")
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
            self.protocol_request_path = self.protocol_dir / f"{attempt_stem}.request.json"
            self.protocol_events_path = self.protocol_dir / f"{attempt_stem}.events.jsonl"
            _write_private_text(self.protocol_events_path, "")
            self.normalized: list[dict[str, object]] = []
            capabilities = map_pi_capabilities(request.tools)
            protocol_request: dict[str, object] = {
                "protocol": PROTOCOL_VERSION,
                "run_id": f"{request.run_id}-{attempt_stem}",
                "input": {"text": request.question},
                "requested_capabilities": capabilities,
            }
            validate_run_request(protocol_request)
            atomic_write_json(self.protocol_request_path, protocol_request)
            self.adapter = PiProtocolAdapter(
                run_id=str(protocol_request["run_id"]),
                capabilities=capabilities,
                emit=self._emit_normalized,
            )
            self.adapter.start()
            self._write()
        except BaseException:
            self.lock.release()
            raise

    def _emit_normalized(self, event: dict[str, object]) -> None:
        self.normalized.append(dict(event))
        self._append(self.protocol_events_path, event)

    def record_event(self, event: dict[str, object]) -> None:
        self._ensure_open()
        try:
            self._append(self.events_path, event)
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
                _write_private_text(
                    self._contained_path(self.final_path),
                    answer if answer.endswith("\n") else f"{answer}\n",
                )
            if stderr_text:
                _write_private_text(self._contained_path(self.stderr_path), stderr_text[-16384:])
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
        self._json(self.state_path, self.state)
        self._json(self.conversation_full_path, self.conversation_full)
        self._json(self.latest_model_context_path, self.latest_model_context)
        self._json(self.conversation_path, self._processed_conversation())

    def _processed_conversation(self) -> dict[str, Any]:
        conversation = json.loads(json.dumps(self.conversation_full))
        for message in conversation["messages"]:
            if message.get("role") != "toolResult":
                continue
            if self.features.externalize_tool_results:
                call_id = str(message.get("toolCallId") or "event")
                directory = self.output_dir / "tool_results"
                _private_directory(directory)
                self._json(directory / f"{call_id}.json", {"message": message})
            if self.features.clear_tool_results:
                message["content"] = [{"type": "text", "text": "[tool result cleared from conversation context]"}]
        return conversation

    def _contained_path(self, path: Path) -> Path:
        root = self.output_dir.resolve(strict=True)
        try:
            parent = path.parent.resolve(strict=True)
            parent.relative_to(root)
        except (OSError, ValueError) as exc:
            raise DciArtifactError("DCI artifact path escapes the run directory") from exc
        destination = parent / path.name
        _reject_symlink(destination, label="artifact target")
        return destination

    def _append(self, path: Path, value: dict[str, object]) -> None:
        _write_private_text(
            self._contained_path(path),
            json.dumps(value, ensure_ascii=False) + "\n",
            append=True,
        )

    def _json(self, path: Path, value: dict[str, Any]) -> None:
        atomic_write_json(self._contained_path(path), value)
