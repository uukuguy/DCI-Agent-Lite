"""Bounded, durable batch orchestration for independent Asterion DCI runs."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
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
    load_benchmark_rows_bytes,
)
from asterion.dci.evaluation import (
    _load_reusable_result,
    evaluate_run_directory_async,
)
from asterion.dci.judge import JudgeConfig, judge_request_fingerprint
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


class _StaleJudgeResult(RuntimeError):
    """A valid prior result needs evaluation under the current Judge identity."""


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


@dataclass
class _SnapshotAuthority:
    paths: dict[str, Path]
    fds: tuple[int, ...]

    def close(self) -> None:
        for descriptor in self.fds:
            os.close(descriptor)


async def run_benchmark_async(
    request: BenchmarkRequest, *, paths: DciPaths
) -> BenchmarkResult:
    """Run one bounded batch while retaining its writer lock until all work drains."""

    rows, output_root, config, row_documents, snapshots = _prepare(request)
    lock = _BatchLock.acquire(output_root)
    tasks: list[asyncio.Task[tuple[int, dict[str, object]]]] = []
    results: dict[int, dict[str, object]] = {}
    snapshot_authority: _SnapshotAuthority | None = None
    batch_started = False
    try:
        _preflight_locked(lock, config, row_documents)
        snapshot_authority = _publish_input_snapshots(lock, snapshots)
        lock.write_json("config.json", config)
        _publish_batch_state(lock, "running", {})
        batch_started = True
        semaphore = asyncio.Semaphore(request.max_concurrency)

        async def worker(index: int, row: BenchmarkRow) -> tuple[int, dict[str, object]]:
            async with semaphore:
                return index, await _run_row(
                    request,
                    paths,
                    lock,
                    row,
                    row_documents[index],
                    snapshot_authority,
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
        _publish_batch_state(lock, "completed", results)
        return BenchmarkResult(output_root=output_root, counts=counts)
    except asyncio.CancelledError:
        if not batch_started:
            raise
        for task in tasks:
            task.cancel()
        await _drain_tasks(tasks)
        results.update(_drained_task_results(tasks))
        results = _terminal_results(
            lock,
            rows,
            row_documents,
            trusted=results,
            missing_status="not_started",
        )
        _publish_aggregates(lock, results)
        _publish_batch_state(lock, "cancelled", results)
        raise
    except BaseException:
        if not batch_started:
            raise
        for task in tasks:
            task.cancel()
        await _drain_tasks(tasks)
        results.update(_drained_task_results(tasks))
        results = _terminal_results(
            lock,
            rows,
            row_documents,
            trusted=results,
            missing_status="not_started",
        )
        _publish_aggregates(lock, results)
        _publish_batch_state(lock, "failed", results)
        raise
    finally:
        if snapshot_authority is not None:
            snapshot_authority.close()
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
) -> tuple[
    tuple[BenchmarkRow, ...],
    Path,
    dict[str, object],
    tuple[dict[str, object], ...],
    dict[str, bytes],
]:
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
        dataset_raw = _read_input_snapshot(request.dataset)
        rows = load_benchmark_rows_bytes(dataset_raw)
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
    dataset_digest = hashlib.sha256(dataset_raw).hexdigest()
    snapshots: dict[str, bytes] = {}
    prompt_resources: dict[str, object] = {}
    for name in ("system_prompt_file", "append_system_prompt_file"):
        path = getattr(request, name)
        if path is None:
            prompt_resources[name] = None
            continue
        raw = _read_input_snapshot(path)
        snapshots[name] = raw
        prompt_resources[name] = {
            "identity": str(canonical_input_identity(path)),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
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
        "analysis": request.analysis,
        "figures": request.figures,
        "judge": judge,
        "judge_configuration_fingerprint": judge_fingerprint,
        "prompt_resources": prompt_resources,
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
                "identity": identity,
                "row_fingerprint": _fingerprint(identity),
                "judge_configuration_fingerprint": judge_fingerprint,
            }
        )
    return rows, output_root, config, tuple(documents), snapshots


async def _run_row(
    request: BenchmarkRequest,
    paths: DciPaths,
    lock: _BatchLock,
    row: BenchmarkRow,
    item: dict[str, object],
    snapshots: _SnapshotAuthority,
) -> dict[str, object]:
    query = lock.open_query(row.query_id)
    try:
        existing_item = query.read_optional_json("item.json")
        if existing_item is not None:
            _validate_item_document(existing_item)
            if not _same_run_item(existing_item, item):
                raise DciBenchmarkError("DCI benchmark row is incompatible")
        query.write_json("item.json", item)
        query.write_text("input_question.txt", str(item["prompt"]))
        existing = query.read_optional_json("result.json")
        generation = _result_generation(existing) or _latest_generation(query)

        if existing is not None and existing.get("status") != "completed":
            _validate_terminal_result(existing, item)

        if (
            request.resume_policy != "fresh"
            and existing is not None
            and existing.get("status") == "completed"
        ):
            _validate_result_shape(existing, item, request.mode)
            native = query.open_existing_query(str(existing["native_generation"]))
            if native is None:
                raise DciBenchmarkError("DCI benchmark result evidence is invalid")
            try:
                try:
                    _validate_exact_reuse(
                        native,
                        existing,
                        item,
                        row,
                        request,
                        query_path=lock.path / row.query_id,
                    )
                except _StaleJudgeResult:
                    pass
                else:
                    return existing
            finally:
                native.close()

        if request.resume_policy == "reuse":
            result = _failed_result(row.query_id, item["row_fingerprint"], "failed")
            query.write_json("result.json", result)
            return result

        if request.resume_policy == "fresh" or generation is None:
            generation = _next_generation(query)
            native_authority = query.open_query(generation)
            native_state = "missing"
        else:
            native_authority = query.open_existing_query(generation)
            if native_authority is None:
                raise DciBenchmarkError("DCI benchmark native evidence is invalid")
            native_state = _native_state(native_authority, lock.path / row.query_id / generation)
        native_dir = lock.path / row.query_id / generation
        try:
            if native_state == "malformed":
                result = _failed_result(row.query_id, item["row_fingerprint"], "failed")
                query.write_json("result.json", result)
                return result
            if native_state != "completed":
                native_request = request_from_runtime_options(
                    request.runtime_options,
                    run_id=row.query_id,
                    question=str(item["prompt"]),
                    cwd=canonical_input_identity(request.cwd),
                    stream_text=False,
                )
                native_request = replace(
                    native_request,
                    max_turns=request.max_turns,
                    system_prompt_file=request.system_prompt_file,
                    append_system_prompt_file=request.append_system_prompt_file,
                    conversation_features=request.conversation_features,
                )
                if native_state in {"failed", "incomplete", "running"}:
                    native_request = resume_request_from_output_dir(
                        native_dir,
                        extra_args=request.runtime_options.extra_args,
                        _directory_fd=native_authority.fd,
                    )
                await _run_pi_async(
                    paths,
                    native_request,
                    output_dir=native_dir,
                    output_directory_fd=native_authority.fd,
                    resource_fds=snapshots.fds,
                    system_prompt_override=snapshots.paths.get("system_prompt_file"),
                    append_system_prompt_override=snapshots.paths.get(
                        "append_system_prompt_file"
                    ),
                )
            result: dict[str, object] = {
                "schema": "asterion.dci.batch-result/v1",
                "query_id": row.query_id,
                "row_fingerprint": item["row_fingerprint"],
                "status": "completed",
                "mode": request.mode,
                "native_generation": generation,
            }
            if request.mode == "qa":
                assert row.answer is not None
                verdict = await evaluate_run_directory_async(
                    native_dir,
                    gold_answer=row.answer,
                    judge_config=request.judge_config,
                    _directory_fd=native_authority.fd,
                )
                result["is_correct"] = verdict["is_correct"]
                result["judge_configuration_fingerprint"] = item[
                    "judge_configuration_fingerprint"
                ]
                result["judge_request_fingerprint"] = verdict[
                    "judge_request_fingerprint"
                ]
            query.write_json("result.json", result)
            return result
        finally:
            native_authority.close()
    except asyncio.CancelledError:
        result = _failed_result(row.query_id, item["row_fingerprint"], "cancelled")
        query.write_json("result.json", result)
        raise
    except DciBenchmarkError:
        raise
    except Exception:
        result = _failed_result(row.query_id, item["row_fingerprint"], "failed")
        query.write_json("result.json", result)
        return result
    finally:
        query.close()


async def _run_pi_async(
    paths: DciPaths,
    request: Any,
    *,
    output_dir: Path,
    output_directory_fd: int | None = None,
    resource_fds: tuple[int, ...] = (),
    system_prompt_override: Path | None = None,
    append_system_prompt_override: Path | None = None,
) -> DciRunResult:
    cancel_event = threading.Event()
    work = asyncio.create_task(
        asyncio.to_thread(
            run_pi_research,
            paths,
            request,
            output_dir=output_dir,
            _cancel_event=cancel_event,
            _output_directory_fd=output_directory_fd,
            _resource_fds=resource_fds,
            _system_prompt_override=system_prompt_override,
            _append_system_prompt_override=append_system_prompt_override,
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
    names = lock.list_names()
    if existing is None:
        if names - {lock.LOCK_NAME}:
            raise DciBenchmarkError("DCI benchmark configuration evidence is missing")
    else:
        _validate_config_document(existing)
        if existing.get("run_fingerprint") != config["run_fingerprint"]:
            raise DciBenchmarkError("DCI benchmark configuration is incompatible")
    for item in items:
        query = lock.open_existing_query(str(item["query_id"]))
        if query is None:
            continue
        try:
            existing_item = query.read_optional_json("item.json")
            if existing_item is None and query.list_names():
                raise DciBenchmarkError("DCI benchmark item evidence is missing")
            if existing_item is not None:
                _validate_item_document(existing_item)
        finally:
            query.close()
        if existing_item is not None and not _same_run_item(existing_item, item):
            raise DciBenchmarkError("DCI benchmark row is incompatible")


def _validate_config_document(value: dict[str, Any]) -> None:
    expected = {
        "schema", "dataset", "mode", "profile", "corpus_identity", "corpus_hint",
        "cwd", "runtime", "conversation_features", "max_concurrency", "max_turns",
        "analysis", "figures", "judge", "judge_configuration_fingerprint",
        "prompt_resources", "run_fingerprint", "batch_fingerprint",
    }
    if set(value) != expected or value.get("schema") != "asterion.dci.batch/v1":
        raise DciBenchmarkError("DCI benchmark configuration evidence is invalid")
    batch_payload = dict(value)
    batch_fingerprint = batch_payload.pop("batch_fingerprint", None)
    if batch_fingerprint != _fingerprint(batch_payload):
        raise DciBenchmarkError("DCI benchmark configuration evidence is invalid")
    run_payload = {
        key: item
        for key, item in batch_payload.items()
        if key not in {"judge", "judge_configuration_fingerprint", "run_fingerprint"}
    }
    if value.get("run_fingerprint") != _fingerprint(run_payload):
        raise DciBenchmarkError("DCI benchmark configuration evidence is invalid")


def _validate_item_document(value: dict[str, Any]) -> None:
    expected = {
        "schema", "query_id", "input", "prompt", "identity", "row_fingerprint",
        "judge_configuration_fingerprint",
    }
    if set(value) != expected or value.get("schema") != "asterion.dci.batch-item/v1":
        raise DciBenchmarkError("DCI benchmark item evidence is invalid")
    identity = value.get("identity")
    if not isinstance(identity, dict):
        raise DciBenchmarkError("DCI benchmark item evidence is invalid")
    if value.get("row_fingerprint") != _fingerprint(identity):
        raise DciBenchmarkError("DCI benchmark item evidence is invalid")
    if identity.get("row") != value.get("input") or identity.get("prompt") != value.get("prompt"):
        raise DciBenchmarkError("DCI benchmark item evidence is invalid")


def _same_run_item(left: dict[str, Any], right: dict[str, object]) -> bool:
    return {
        key: value
        for key, value in left.items()
        if key != "judge_configuration_fingerprint"
    } == {
        key: value
        for key, value in right.items()
        if key != "judge_configuration_fingerprint"
    }


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


def _read_input_snapshot(path: Path) -> bytes:
    descriptor: int | None = None
    try:
        descriptor = os.open(
            path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        )
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise DciBenchmarkError("DCI benchmark input resource is invalid")
        with os.fdopen(descriptor, "rb") as handle:
            descriptor = None
            return handle.read()
    except DciBenchmarkError:
        raise
    except OSError as error:
        raise DciBenchmarkError("DCI benchmark input resource is invalid") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _publish_input_snapshots(
    lock: _BatchLock, snapshots: dict[str, bytes]
) -> _SnapshotAuthority:
    directory = lock.open_query(".inputs")
    descriptors: list[int] = []
    paths: dict[str, Path] = {}
    try:
        for key, raw in snapshots.items():
            name = f"{key}.txt"
            directory.write_bytes(name, raw)
            descriptor = os.open(
                name,
                os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=directory.fd,
            )
            descriptors.append(descriptor)
            paths[key] = Path(f"/dev/fd/{descriptor}")
        return _SnapshotAuthority(paths=paths, fds=tuple(descriptors))
    except BaseException:
        for descriptor in descriptors:
            os.close(descriptor)
        raise
    finally:
        directory.close()


def _result_generation(value: object) -> str | None:
    if isinstance(value, dict) and isinstance(value.get("native_generation"), str):
        return value["native_generation"]
    return None


_NATIVE_GENERATION_PATTERN = re.compile(
    r"native-generation-(?:[0-9]{4}|[1-9][0-9]{4,})"
)


def _generation_names(query: _Directory) -> tuple[str, ...]:
    return tuple(
        sorted(
            (
                name
                for name in query.list_names()
                if _NATIVE_GENERATION_PATTERN.fullmatch(name)
            ),
            key=lambda name: int(name.rsplit("-", 1)[1]),
        )
    )


def _latest_generation(query: _Directory) -> str | None:
    names = _generation_names(query)
    return names[-1] if names else None


def _next_generation(query: _Directory) -> str:
    names = _generation_names(query)
    number = int(names[-1].rsplit("-", 1)[1]) + 1 if names else 1
    return f"native-generation-{number:04d}"


def _native_state(native: _Directory, display_path: Path) -> str:
    state = native.read_optional_json("state.json")
    if state is None:
        return "missing" if not native.list_names() else "malformed"
    status = state.get("status")
    if status == "completed":
        lock: DciRunLock | None = None
        try:
            lock = DciRunLock.acquire_fd(native.fd, path=display_path, wait=True)
            validate_completed_run_evidence(lock)
            return "completed"
        except (DciArtifactError, OSError, ValueError):
            return "malformed"
        finally:
            if lock is not None:
                lock.release()
    if status in {"failed", "incomplete", "running"}:
        return str(status)
    return "malformed"


def _validate_result_shape(
    value: dict[str, Any], item: dict[str, object], mode: str
) -> None:
    common = {
        "schema", "query_id", "row_fingerprint", "status", "mode",
        "native_generation",
    }
    expected = common | (
        {
            "is_correct", "judge_configuration_fingerprint",
            "judge_request_fingerprint",
        }
        if mode == "qa"
        else set()
    )
    if (
        set(value) != expected
        or value.get("schema") != "asterion.dci.batch-result/v1"
        or value.get("query_id") != item.get("query_id")
        or value.get("row_fingerprint") != item.get("row_fingerprint")
        or value.get("status") != "completed"
        or value.get("mode") != mode
        or not isinstance(value.get("native_generation"), str)
        or not _NATIVE_GENERATION_PATTERN.fullmatch(value["native_generation"])
        or (mode == "qa" and type(value.get("is_correct")) is not bool)
    ):
        raise DciBenchmarkError("DCI benchmark result evidence is invalid")


def _validate_terminal_result(
    value: dict[str, Any], item: dict[str, object]
) -> None:
    if (
        set(value)
        != {"schema", "query_id", "row_fingerprint", "status"}
        or value.get("schema") != "asterion.dci.batch-result/v1"
        or value.get("query_id") != item.get("query_id")
        or value.get("row_fingerprint") != item.get("row_fingerprint")
        or value.get("status") not in {"failed", "cancelled", "not_started"}
    ):
        raise DciBenchmarkError("DCI benchmark terminal result is invalid")


def _validate_exact_reuse(
    native: _Directory,
    result: dict[str, Any],
    item: dict[str, object],
    row: BenchmarkRow,
    request: BenchmarkRequest,
    *,
    query_path: Path,
) -> None:
    display_path = query_path / str(result["native_generation"])
    lock: DciRunLock | None = None
    try:
        lock = DciRunLock.acquire_fd(native.fd, path=display_path, wait=True)
        state, question, prediction = validate_completed_run_evidence(lock)
        if request.mode == "ir":
            return
        assert row.answer is not None
        fingerprint = judge_request_fingerprint(
            config=request.judge_config,
            question=question,
            gold_answer=row.answer,
            predicted_answer=prediction,
        )
        cached = _load_reusable_result(lock, state, fingerprint, request.judge_config)
        if result.get("judge_configuration_fingerprint") != item.get(
            "judge_configuration_fingerprint"
        ):
            raise _StaleJudgeResult
        if (
            cached is None
            or result.get("judge_request_fingerprint") != fingerprint
            or result.get("is_correct") is not cached.get("is_correct")
        ):
            raise DciBenchmarkError("DCI benchmark result evidence is invalid")
    except DciBenchmarkError:
        raise
    except (DciArtifactError, OSError, ValueError) as error:
        raise DciBenchmarkError("DCI benchmark result evidence is invalid") from error
    finally:
        if lock is not None:
            lock.release()


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


def _publish_batch_state(
    lock: _BatchLock, status: str, results: dict[int, dict[str, object]]
) -> None:
    lock.write_json(
        "batch-state.json",
        {
            "schema": "asterion.dci.batch-state/v1",
            "status": status,
            "counts": _counts(results),
        },
    )


def _terminal_results(
    lock: _BatchLock,
    rows: tuple[BenchmarkRow, ...],
    items: tuple[dict[str, object], ...],
    *,
    trusted: dict[int, dict[str, object]],
    missing_status: str,
) -> dict[int, dict[str, object]]:
    results: dict[int, dict[str, object]] = {}
    for index, row in enumerate(rows):
        query = lock.open_query(row.query_id)
        try:
            query.write_json("item.json", items[index])
            query.write_text("input_question.txt", str(items[index]["prompt"]))
            result = trusted.get(index)
            if result is None:
                candidate = query.read_optional_json("result.json")
                if candidate is not None:
                    try:
                        _validate_terminal_result(candidate, items[index])
                    except DciBenchmarkError:
                        candidate = None
                result = candidate
            if result is None:
                result = _failed_result(
                    row.query_id, items[index]["row_fingerprint"], missing_status
                )
                query.write_json("result.json", result)
            results[index] = result
        finally:
            query.close()
    return results


def _drained_task_results(
    tasks: list[asyncio.Task[tuple[int, dict[str, object]]]],
) -> dict[int, dict[str, object]]:
    results: dict[int, dict[str, object]] = {}
    for task in tasks:
        if task.cancelled():
            continue
        try:
            index, result = task.result()
        except Exception:
            continue
        results[index] = result
    return results


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


def _validate_component(name: str) -> None:
    if (
        not name
        or name in {".", ".."}
        or "\0" in name
        or "/" in name
        or (os.altsep is not None and os.altsep in name)
        or os.path.isabs(name)
    ):
        raise DciBenchmarkError("DCI benchmark evidence name is invalid")


class _Directory:
    def __init__(self, fd: int) -> None:
        self.fd = fd

    def read_optional_json(self, name: str) -> dict[str, Any] | None:
        _validate_component(name)
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
        self.write_bytes(name, value.encode("utf-8"))

    def write_bytes(self, name: str, value: bytes) -> None:
        _validate_component(name)
        temporary = f".{name}.{secrets.token_hex(16)}.tmp"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=self.fd)
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as handle:
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

    def list_names(self) -> set[str]:
        return set(os.listdir(self.fd))

    def open_query(self, name: str) -> _Directory:
        _validate_component(name)
        try:
            os.mkdir(name, 0o700, dir_fd=self.fd)
        except FileExistsError:
            pass
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=self.fd,
            )
            os.fchmod(descriptor, 0o700)
            return _Directory(descriptor)
        except OSError as error:
            raise DciBenchmarkError(
                "DCI benchmark query destination is unsafe"
            ) from error

    def open_existing_query(self, name: str) -> _Directory | None:
        _validate_component(name)
        try:
            descriptor = os.open(
                name,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=self.fd,
            )
        except FileNotFoundError:
            return None
        except OSError as error:
            raise DciBenchmarkError(
                "DCI benchmark query destination is unsafe"
            ) from error
        return _Directory(descriptor)

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
        _validate_component(name)
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
        _validate_component(name)
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
