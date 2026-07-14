"""Bounded, durable batch orchestration for independent Asterion DCI runs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import stat
import threading
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

from asterion.dci.artifacts import (
    DciArtifactError,
    DciConversationFeatures,
    DciRunLock,
    extra_args_fingerprint,
    validate_completed_run_evidence,
)
from asterion.dci.config import DciPaths, DciRuntimeOptions
from asterion.dci.datasets import (
    BenchmarkRow,
    DatasetError,
    build_ir_prompt,
    build_qa_prompt,
    canonical_input_identity,
    load_benchmark_rows,
)
from asterion.dci.evaluation import evaluate_run_directory_async
from asterion.dci.judge import JudgeConfig
from asterion.dci.run import (
    DciRunResult,
    request_from_runtime_options,
    resume_request_from_output_dir,
    run_pi_research,
)

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


class DciBenchmarkError(RuntimeError):
    """Safe public error for an invalid or incompatible benchmark."""


class _NativeEvidenceError(RuntimeError):
    """Internal classification for unsafe per-query native evidence."""


@dataclass(frozen=True)
class BenchmarkRequest:
    dataset: Path
    output_root: Path
    cwd: Path
    judge_config: JudgeConfig
    runtime_options: DciRuntimeOptions
    limit: int | None = None
    mode: str = "qa"
    profile: str | None = None
    corpus: Path | None = None
    corpus_hint: str | None = None
    max_concurrency: int = 1
    max_turns: int | None = None
    system_prompt_file: Path | None = None
    append_system_prompt_file: Path | None = None
    conversation_features: DciConversationFeatures | None = None
    resume_policy: str = "compatible"
    analysis: bool = True
    figures: bool = True


@dataclass(frozen=True)
class BenchmarkResult:
    output_root: Path
    counts: dict[str, int]


async def run_benchmark_async(
    request: BenchmarkRequest, *, paths: DciPaths
) -> BenchmarkResult:
    """Run one bounded batch while retaining its writer lock until all work drains."""

    rows, output_root, config, row_documents = _prepare(request)
    _preflight_existing(output_root, config, row_documents)
    lock = _BatchLock.acquire(output_root)
    tasks: list[asyncio.Task[tuple[int, dict[str, object]]]] = []
    results: dict[int, dict[str, object]] = {}
    try:
        _preflight_locked(lock, config, row_documents)
        lock.write_json("config.json", config)
        semaphore = asyncio.Semaphore(request.max_concurrency)

        async def worker(index: int, row: BenchmarkRow) -> tuple[int, dict[str, object]]:
            async with semaphore:
                return index, await _run_row(
                    request, paths, lock, row, row_documents[index]
                )

        tasks = [
            asyncio.create_task(worker(index, row)) for index, row in enumerate(rows)
        ]
        pending: set[asyncio.Task[tuple[int, dict[str, object]]]] = set(tasks)
        while pending:
            done, pending = await asyncio.wait(
                pending, return_when=asyncio.FIRST_COMPLETED
            )
            for task in done:
                index, value = task.result()
                results[index] = value
            _publish_aggregates(lock, results)
        counts = _counts(results)
        return BenchmarkResult(output_root=output_root, counts=counts)
    except asyncio.CancelledError:
        for task in tasks:
            task.cancel()
        await _drain_tasks(tasks)
        raise
    except BaseException:
        for task in tasks:
            task.cancel()
        await _drain_tasks(tasks)
        raise
    finally:
        lock.release()


def run_benchmark(request: BenchmarkRequest, *, paths: DciPaths) -> BenchmarkResult:
    """Synchronous compatibility wrapper for command-line callers."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(run_benchmark_async(request, paths=paths))
    raise DciBenchmarkError("DCI benchmark sync API cannot run inside an event loop")


def _prepare(
    request: BenchmarkRequest,
) -> tuple[tuple[BenchmarkRow, ...], Path, dict[str, object], tuple[dict[str, object], ...]]:
    if request.mode not in {"qa", "ir"}:
        raise DciBenchmarkError("DCI benchmark mode is invalid")
    for value, label in (
        (request.max_concurrency, "concurrency"),
        (request.max_turns, "max turns"),
    ):
        if value is not None and (
            isinstance(value, bool) or not isinstance(value, int) or value < 1
        ):
            raise DciBenchmarkError(f"DCI benchmark {label} is invalid")
    if request.limit is not None and (
        isinstance(request.limit, bool)
        or not isinstance(request.limit, int)
        or request.limit < 1
    ):
        raise DciBenchmarkError("DCI benchmark limit is invalid")
    if request.resume_policy not in {"compatible", "fresh", "reuse"}:
        raise DciBenchmarkError("DCI benchmark resume policy is invalid")
    try:
        rows = load_benchmark_rows(request.dataset)
    except DatasetError as error:
        raise DciBenchmarkError("DCI benchmark dataset is invalid") from error
    if request.limit is not None:
        rows = rows[: request.limit]
    if any((row.is_ir if request.mode == "qa" else not row.is_ir) for row in rows):
        raise DciBenchmarkError("DCI benchmark dataset does not match its mode")
    output_root = Path(os.path.abspath(os.path.normpath(request.output_root)))
    _reject_symlink_components(output_root)
    corpus_identity = (
        str(canonical_input_identity(request.corpus)) if request.corpus else None
    )
    runtime = _runtime_document(request.runtime_options)
    judge = request.judge_config.public_dict()
    judge_fingerprint = _fingerprint(judge)
    dataset_identity = canonical_input_identity(request.dataset)
    dataset_digest = _file_digest(dataset_identity)
    config: dict[str, object] = {
        "schema": "asterion.dci.batch/v1",
        "dataset": {"identity": str(dataset_identity), "sha256": dataset_digest},
        "mode": request.mode,
        "profile": request.profile,
        "corpus_identity": corpus_identity,
        "corpus_hint": request.corpus_hint,
        "cwd": str(canonical_input_identity(request.cwd)),
        "runtime": runtime,
        "conversation_features": (
            request.conversation_features.to_mapping()
            if request.conversation_features is not None
            else DciConversationFeatures().to_mapping()
        ),
        "max_concurrency": request.max_concurrency,
        "max_turns": request.max_turns,
        "resume_policy": request.resume_policy,
        "analysis": request.analysis,
        "figures": request.figures,
        "judge": judge,
        "judge_configuration_fingerprint": judge_fingerprint,
        "prompt_resources": _prompt_resource_digests(request),
    }
    config["run_fingerprint"] = _fingerprint(
        {key: value for key, value in config.items() if key not in {"judge", "judge_configuration_fingerprint"}}
    )
    config["batch_fingerprint"] = _fingerprint(config)
    documents: list[dict[str, object]] = []
    for row in rows:
        prompt = _prompt(request, row)
        identity = {
            "schema": "asterion.dci.batch-row/v1",
            "row": row.as_dict(),
            "mode": request.mode,
            "profile": request.profile,
            "prompt": prompt,
            "corpus_identity": corpus_identity,
            "corpus_hint": request.corpus_hint,
            "cwd": config["cwd"],
            "runtime": runtime,
            "conversation_features": config["conversation_features"],
            "max_turns": request.max_turns,
            "prompt_resources": config["prompt_resources"],
        }
        documents.append(
            {
                "schema": "asterion.dci.batch-item/v1",
                "query_id": row.query_id,
                "input": row.as_dict(),
                "prompt": prompt,
                "row_fingerprint": _fingerprint(identity),
                "judge_configuration_fingerprint": judge_fingerprint,
            }
        )
    return rows, output_root, config, tuple(documents)


async def _run_row(
    request: BenchmarkRequest,
    paths: DciPaths,
    lock: _BatchLock,
    row: BenchmarkRow,
    item: dict[str, object],
) -> dict[str, object]:
    query = lock.open_query(row.query_id)
    try:
        existing_item = query.read_optional_json("item.json")
        if existing_item is not None and existing_item.get("row_fingerprint") != item["row_fingerprint"]:
            raise DciBenchmarkError("DCI benchmark row is incompatible")
        query.write_json("item.json", item)
        query.write_text("input_question.txt", str(item["prompt"]))
        existing = query.read_optional_json("result.json")
        if _reusable_result(existing, item, request.mode):
            return existing  # type: ignore[return-value]
    finally:
        query.close()

    query_dir = lock.path / row.query_id
    native_dir = query_dir / "native"
    try:
        completed = _completed_run(native_dir)
        if not completed:
            native = request_from_runtime_options(
                request.runtime_options,
                run_id=row.query_id,
                question=str(item["prompt"]),
                cwd=canonical_input_identity(request.cwd),
                stream_text=False,
            )
            native = replace(
                native,
                max_turns=request.max_turns,
                system_prompt_file=request.system_prompt_file,
                append_system_prompt_file=request.append_system_prompt_file,
                conversation_features=request.conversation_features,
            )
            if request.resume_policy != "fresh" and _resumable_run(native_dir):
                native = resume_request_from_output_dir(
                    native_dir, extra_args=request.runtime_options.extra_args
                )
            await _run_pi_async(paths, native, output_dir=native_dir)
        result: dict[str, object] = {
            "schema": "asterion.dci.batch-result/v1",
            "query_id": row.query_id,
            "row_fingerprint": item["row_fingerprint"],
            "status": "completed",
        }
        if request.mode == "qa":
            assert row.answer is not None
            verdict = await evaluate_run_directory_async(
                native_dir,
                gold_answer=row.answer,
                judge_config=request.judge_config,
            )
            result["is_correct"] = verdict["is_correct"]
            result["judge_configuration_fingerprint"] = item[
                "judge_configuration_fingerprint"
            ]
            fingerprint = verdict.get("judge_request_fingerprint")
            if isinstance(fingerprint, str):
                result["judge_request_fingerprint"] = fingerprint
        _write_query_result(lock, row.query_id, result)
        return result
    except asyncio.CancelledError:
        result = _failed_result(row.query_id, item["row_fingerprint"], "cancelled")
        _write_query_result(lock, row.query_id, result)
        raise
    except DciBenchmarkError:
        raise
    except Exception:
        result = _failed_result(row.query_id, item["row_fingerprint"], "failed")
        _write_query_result(lock, row.query_id, result)
        return result


async def _run_pi_async(
    paths: DciPaths, request: Any, *, output_dir: Path
) -> DciRunResult:
    cancel_event = threading.Event()
    work = asyncio.create_task(
        asyncio.to_thread(
            run_pi_research,
            paths,
            request,
            output_dir=output_dir,
            _cancel_event=cancel_event,
        )
    )
    try:
        await asyncio.wait({work})
        return work.result()
    except asyncio.CancelledError:
        cancel_event.set()
        await _drain_tasks([work])
        raise


async def _drain_tasks(tasks: list[asyncio.Task[Any]]) -> None:
    pending = [task for task in tasks if not task.done()]
    while pending:
        current = asyncio.current_task()
        if current is not None:
            current.uncancel()
        try:
            await asyncio.wait(pending)
        except asyncio.CancelledError:
            continue
        pending = [task for task in pending if not task.done()]
    for task in tasks:
        try:
            task.result()
        except (asyncio.CancelledError, Exception):
            pass


def _preflight_existing(
    output_root: Path,
    config: dict[str, object],
    items: tuple[dict[str, object], ...],
) -> None:
    if not output_root.exists():
        return
    config_path = output_root / "config.json"
    if config_path.exists():
        value = _read_public_json(config_path)
        if value.get("run_fingerprint") != config["run_fingerprint"]:
            raise DciBenchmarkError("DCI benchmark configuration is incompatible")
    for item in items:
        path = output_root / str(item["query_id"]) / "item.json"
        if not path.exists():
            continue
        value = _read_public_json(path)
        if not isinstance(value, dict) or value.get("row_fingerprint") != item["row_fingerprint"]:
            raise DciBenchmarkError("DCI benchmark row is incompatible")


def _preflight_locked(
    lock: _BatchLock,
    config: dict[str, object],
    items: tuple[dict[str, object], ...],
) -> None:
    existing = lock.read_optional_json("config.json")
    if existing is not None and existing.get("run_fingerprint") != config["run_fingerprint"]:
        raise DciBenchmarkError("DCI benchmark configuration is incompatible")
    for item in items:
        query = lock.open_existing_query(str(item["query_id"]))
        if query is None:
            continue
        try:
            existing_item = query.read_optional_json("item.json")
        finally:
            query.close()
        if existing_item is not None and existing_item.get("row_fingerprint") != item["row_fingerprint"]:
            raise DciBenchmarkError("DCI benchmark row is incompatible")


def _read_public_json(path: Path) -> dict[str, Any]:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, UnicodeError, ValueError) as error:
        raise DciBenchmarkError("DCI benchmark evidence is invalid") from error
    if not isinstance(value, dict):
        raise DciBenchmarkError("DCI benchmark evidence is invalid")
    return value


def _runtime_document(options: DciRuntimeOptions) -> dict[str, object]:
    return {
        "provider": options.provider,
        "model": options.model,
        "tools": options.tools,
        "timeout_seconds": options.timeout_seconds,
        "runtime_context_level": options.runtime_context_level,
        "thinking_level": options.thinking_level,
        "node_max_old_space_size_mb": options.node_max_old_space_size_mb,
        "keep_session": options.keep_session,
        "extra_args_count": len(options.extra_args),
        "extra_args_fingerprint": extra_args_fingerprint(options.extra_args),
    }


def _prompt(request: BenchmarkRequest, row: BenchmarkRow) -> str:
    if request.corpus is None:
        return row.query
    if request.mode == "ir":
        return build_ir_prompt(row.query, request.corpus, request.corpus_hint)
    return build_qa_prompt(row.query, request.corpus)


def _prompt_resource_digests(request: BenchmarkRequest) -> dict[str, object]:
    value: dict[str, object] = {}
    for name in ("system_prompt_file", "append_system_prompt_file"):
        path = getattr(request, name)
        value[name] = (
            None
            if path is None
            else {
                "identity": str(canonical_input_identity(path)),
                "sha256": _file_digest(canonical_input_identity(path)),
            }
        )
    return value


def _file_digest(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as error:
        raise DciBenchmarkError("DCI benchmark input resource is invalid") from error


def _fingerprint(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _completed_run(path: Path) -> bool:
    state_path = path / "state.json"
    if not state_path.exists():
        return False
    lock: DciRunLock | None = None
    try:
        state = _read_public_json(state_path)
        if state.get("status") != "completed":
            return False
        lock = DciRunLock.acquire_existing(path, wait=True)
        validate_completed_run_evidence(lock)
        return True
    except (DciArtifactError, DciBenchmarkError, OSError, ValueError) as error:
        raise _NativeEvidenceError("DCI benchmark native evidence is invalid") from error
    finally:
        if lock is not None:
            lock.release()


def _resumable_run(path: Path) -> bool:
    try:
        state = json.loads((path / "state.json").read_text(encoding="utf-8"))
        return isinstance(state, dict) and state.get("status") in {"failed", "incomplete", "running"}
    except (OSError, UnicodeError, ValueError):
        return False


def _reusable_result(value: object, item: dict[str, object], mode: str) -> bool:
    if not isinstance(value, dict) or value.get("status") != "completed" or value.get("row_fingerprint") != item["row_fingerprint"]:
        return False
    if mode == "ir":
        return "is_correct" not in value
    return type(value.get("is_correct")) is bool and value.get("judge_configuration_fingerprint") == item["judge_configuration_fingerprint"]


def _failed_result(query_id: str, row_fingerprint: object, status: str) -> dict[str, object]:
    return {"schema": "asterion.dci.batch-result/v1", "query_id": query_id, "row_fingerprint": row_fingerprint, "status": status}


def _write_query_result(lock: _BatchLock, query_id: str, result: dict[str, object]) -> None:
    query = lock.open_query(query_id)
    try:
        query.write_json("result.json", result)
    finally:
        query.close()


def _counts(results: dict[int, dict[str, object]]) -> dict[str, int]:
    values = tuple(results[index] for index in sorted(results))
    return {"total": len(values), "correct": sum(value.get("is_correct") is True for value in values), "failed": sum(value.get("status") != "completed" for value in values)}


def _publish_aggregates(lock: _BatchLock, results: dict[int, dict[str, object]]) -> None:
    ordered = [results[index] for index in sorted(results)]
    lock.write_text("results.jsonl", "".join(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in ordered))
    lock.write_json("summary.json", {"schema": "asterion.dci.batch-summary/v1", "counts": _counts(results)})


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for component in path.parts[1:]:
        current /= component
        if current.is_symlink():
            raise DciBenchmarkError("DCI benchmark destination is unsafe")


def _open_or_create_output_directory(path: Path) -> int:
    descriptor = os.open("/", os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        for component in path.parts[1:]:
            try:
                next_descriptor = os.open(
                    component,
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=descriptor,
                )
            except FileNotFoundError:
                os.mkdir(component, 0o700, dir_fd=descriptor)
                next_descriptor = os.open(
                    component,
                    os.O_RDONLY
                    | getattr(os, "O_DIRECTORY", 0)
                    | getattr(os, "O_NOFOLLOW", 0),
                    dir_fd=descriptor,
                )
            os.close(descriptor)
            descriptor = next_descriptor
        os.fchmod(descriptor, 0o700)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


class _Directory:
    def __init__(self, fd: int) -> None:
        self.fd = fd

    def read_optional_json(self, name: str) -> dict[str, Any] | None:
        try:
            fd = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=self.fd)
        except FileNotFoundError:
            return None
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise DciBenchmarkError("DCI benchmark evidence is invalid")
            with os.fdopen(fd, encoding="utf-8") as handle:
                fd = -1
                value = json.load(handle)
        except (OSError, UnicodeError, ValueError) as error:
            raise DciBenchmarkError("DCI benchmark evidence is invalid") from error
        finally:
            if fd >= 0:
                os.close(fd)
        if not isinstance(value, dict):
            raise DciBenchmarkError("DCI benchmark evidence is invalid")
        return value

    def write_json(self, name: str, value: object) -> None:
        self.write_text(name, json.dumps(value, ensure_ascii=False, indent=2) + "\n")

    def write_text(self, name: str, value: str) -> None:
        temporary = f".{name}.{secrets.token_hex(16)}.tmp"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=self.fd)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                fd = -1
                handle.write(value)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                target = os.stat(name, dir_fd=self.fd, follow_symlinks=False)
                if stat.S_ISLNK(target.st_mode):
                    raise DciBenchmarkError("DCI benchmark destination is unsafe")
            except FileNotFoundError:
                pass
            os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
        finally:
            if fd >= 0:
                os.close(fd)
            try:
                os.unlink(temporary, dir_fd=self.fd)
            except FileNotFoundError:
                pass

    def close(self) -> None:
        os.close(self.fd)


class _BatchLock(_Directory):
    LOCK_NAME = ".asterion-dci-batch.lock"

    def __init__(self, path: Path, fd: int) -> None:
        super().__init__(fd)
        self.path = path
        self.lock_fd: int | None = None

    @classmethod
    def acquire(cls, path: Path) -> _BatchLock:
        if fcntl is None:
            raise DciBenchmarkError("DCI benchmark locking is unavailable")
        _reject_symlink_components(path)
        try:
            fd = _open_or_create_output_directory(path)
        except OSError as error:
            raise DciBenchmarkError("DCI benchmark destination is unsafe") from error
        lock = cls(path, fd)
        try:
            os.fchmod(fd, 0o700)
            lock.lock_fd = os.open(cls.LOCK_NAME, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=fd)
            os.fchmod(lock.lock_fd, 0o600)
            fcntl.flock(lock.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return lock
        except (BlockingIOError, OSError) as error:
            lock.release()
            raise DciBenchmarkError("DCI benchmark is already running") from error

    def open_query(self, name: str) -> _Directory:
        try:
            os.mkdir(name, 0o700, dir_fd=self.fd)
        except FileExistsError:
            pass
        try:
            fd = os.open(name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=self.fd)
            os.fchmod(fd, 0o700)
            return _Directory(fd)
        except OSError as error:
            raise DciBenchmarkError("DCI benchmark query destination is unsafe") from error

    def open_existing_query(self, name: str) -> _Directory | None:
        try:
            fd = os.open(name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=self.fd)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise DciBenchmarkError("DCI benchmark query destination is unsafe") from error
        return _Directory(fd)

    def release(self) -> None:
        if self.lock_fd is not None:
            try:
                fcntl.flock(self.lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(self.lock_fd)
                self.lock_fd = None
        if self.fd >= 0:
            os.close(self.fd)
            self.fd = -1
