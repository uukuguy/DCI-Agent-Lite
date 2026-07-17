"""Executable five-stage DCI application implementations."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from collections.abc import Mapping
from typing import Awaitable, Callable

from asterion.dci.analysis import aggregate_results
from asterion.dci.bridge import DciRunExecutor, project_dci_run
from asterion.dci.evaluation import evaluate_run_directory_async
from asterion.dci.judge import JudgeConfig
from asterion.dci.run import DciRunRequest
from asterion.packages.execution import (
    PackageExecutionError,
    PackageExecutionResult,
    PackageInvocation,
)
from asterion.runtime.host import RunRequest
from asterion.runtime.protocol import ProtocolError, validate_event_stream


INPUT_PROTOCOL = "asterion.dci.complete-input/v1"
IMPLEMENTATION_PROTOCOL = "asterion.dci.complete-application/v1"
_IDENTITY_RESOURCES = (
    "capabilities/dci_research/complete.py",
    "capabilities/dci_research/manifests/dci-analysis.json",
    "capabilities/dci_research/manifests/dci-benchmark.json",
    "capabilities/dci_research/manifests/dci-evaluation.json",
    "capabilities/dci_research/manifests/dci-export.json",
    "capabilities/dci_research/manifests/dci-research.json",
    "applications/dci_agent_lite/assemblies/dci-complete-application-claude.json",
    "applications/dci_agent_lite/assemblies/dci-complete-application-pi.json",
)


def complete_application_identity() -> str:
    """Digest the exact shipped implementation and portable application resources."""

    root = resources.files("asterion")
    digest = hashlib.sha256()
    for name in _IDENTITY_RESOURCES:
        raw = root.joinpath(name).read_bytes()
        encoded = name.encode()
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
    return digest.hexdigest()


@dataclass
class _Attempt:
    question: str
    gold_answer: str
    output_dir: Path | None


class DciCompleteAttemptStore:
    """Attempt-scoped private state shared only by one installed application."""

    def __init__(self) -> None:
        self._attempts: dict[str, _Attempt] = {}

    def start(
        self, run_id: str, *, question: str, gold_answer: str, output_dir: Path | None
    ) -> None:
        if run_id in self._attempts:
            raise PackageExecutionError("complete application run is duplicated")
        self._attempts[run_id] = _Attempt(question, gold_answer, output_dir)

    def require(self, run_id: str) -> _Attempt:
        try:
            return self._attempts[run_id]
        except KeyError:
            raise PackageExecutionError("complete application evidence is unavailable") from None

    def finish(self, run_id: str) -> None:
        if self._attempts.pop(run_id, None) is None:
            raise PackageExecutionError("complete application evidence is unavailable")


def _envelope(value: str) -> tuple[str, str]:
    try:
        document = json.loads(value)
    except (TypeError, ValueError):
        raise PackageExecutionError("complete application input is invalid") from None
    if not isinstance(document, dict) or set(document) != {
        "protocol",
        "question",
        "gold_answer",
    }:
        raise PackageExecutionError("complete application input is invalid")
    question = document.get("question")
    gold = document.get("gold_answer")
    if (
        document.get("protocol") != INPUT_PROTOCOL
        or not isinstance(question, str)
        or not question.strip()
        or not isinstance(gold, str)
        or not gold.strip()
    ):
        raise PackageExecutionError("complete application input is invalid")
    return question, gold


def _artifact(invocation: PackageInvocation, media_type: str) -> dict[str, object]:
    matches = [
        item
        for item in invocation.upstream_artifacts
        if item.get("media_type") == media_type
    ]
    if len(matches) != 1 or not isinstance(matches[0].get("value"), Mapping):
        raise PackageExecutionError("complete application upstream evidence is invalid")
    return dict(matches[0]["value"])


def _result(
    *, stage: str, media_type: str, value: dict[str, object]
) -> PackageExecutionResult:
    return PackageExecutionResult(
        events=({"type": f"{stage}.completed", "payload": {"status": "completed"}},),
        artifacts=({
            "artifact_id": f"dci-{stage}-result",
            "media_type": media_type,
            "value": {
                "schema": IMPLEMENTATION_PROTOCOL,
                "implementation_sha256": complete_application_identity(),
                **value,
            },
        },),
    )


def _plain(value: object) -> object:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _bind_research_projection(projected: PackageExecutionResult) -> PackageExecutionResult:
    if len(projected.artifacts) != 1:
        raise PackageExecutionError("complete research evidence is invalid")
    artifact = projected.artifacts[0]
    value = artifact.get("value")
    if not isinstance(value, Mapping):
        raise PackageExecutionError("complete research evidence is invalid")
    return PackageExecutionResult(
        events=projected.events,
        artifacts=({
            "artifact_id": artifact["artifact_id"],
            "media_type": artifact["media_type"],
            "value": {
                "schema": IMPLEMENTATION_PROTOCOL,
                "implementation_sha256": complete_application_identity(),
                **dict(value),
            },
        },),
    )


class DciCompleteResearchImplementation:
    def __init__(self, *, store: DciCompleteAttemptStore, native_executor: DciRunExecutor) -> None:
        self._store = store
        self._native_executor = native_executor

    async def execute(self, invocation: PackageInvocation) -> PackageExecutionResult:
        question, gold = _envelope(invocation.input_text)
        if invocation.runtime.manifest.runtime_id == "pi.reference":
            try:
                native = self._native_executor.run(
                    DciRunRequest(
                        run_id=invocation.run_id,
                        question=question,
                        cwd=Path.cwd(),
                        tools="read,grep",
                        max_turns=4,
                    )
                )
                projected = project_dci_run(native)
                self._store.start(
                    invocation.run_id,
                    question=question,
                    gold_answer=gold,
                    output_dir=native.output_dir,
                )
                return _bind_research_projection(projected)
            except (OSError, RuntimeError, TypeError, ValueError):
                raise PackageExecutionError("complete research execution failed") from None
        try:
            request = RunRequest(
                run_id=invocation.run_id,
                input_text=question,
                requested_capabilities=("filesystem.read",),
            )
            events = tuple(
                event.to_mapping()
                async for event in invocation.runtime.run(request, signal=invocation.signal)
            )
            validate_event_stream(events)
        except (ProtocolError, RuntimeError, TypeError, ValueError):
            raise PackageExecutionError("complete research execution failed") from None
        self._store.start(
            invocation.run_id, question=question, gold_answer=gold, output_dir=None
        )
        answer = next(
            (
                event["payload"]["artifact"]["uri"]
                for event in events
                if event.get("type") == "artifact.created"
                and event.get("payload", {}).get("artifact", {}).get("kind") == "answer"
            ),
            None,
        )
        if not isinstance(answer, str):
            raise PackageExecutionError("complete research evidence is unavailable")
        return _result(
            stage="research",
            media_type="application/vnd.dci.research+json",
            value={"answer_artifact_uri": answer},
        )


Evaluator = Callable[..., Awaitable[dict[str, object]]]


class DciCompleteEvaluationImplementation:
    def __init__(
        self,
        *,
        store: DciCompleteAttemptStore,
        evaluator: Evaluator = evaluate_run_directory_async,
        judge_config: Callable[[], JudgeConfig] = JudgeConfig.from_env,
    ) -> None:
        self._store = store
        self._evaluator = evaluator
        self._judge_config = judge_config

    async def execute(self, invocation: PackageInvocation) -> PackageExecutionResult:
        _artifact(invocation, "application/vnd.dci.research+json")
        attempt = self._store.require(invocation.run_id)
        if attempt.output_dir is None:
            raise PackageExecutionError("complete evaluation evidence is unavailable")
        try:
            verdict = await self._evaluator(
                attempt.output_dir,
                gold_answer=attempt.gold_answer,
                judge_config=self._judge_config(),
            )
        except Exception:
            raise PackageExecutionError("complete evaluation failed") from None
        is_correct = verdict.get("is_correct")
        fingerprint = verdict.get("judge_request_fingerprint")
        if not isinstance(is_correct, bool) or not isinstance(fingerprint, str):
            raise PackageExecutionError("complete evaluation evidence is invalid")
        return _result(
            stage="evaluation",
            media_type="application/vnd.dci.verdict+json",
            value={"is_correct": is_correct, "judge_request_fingerprint": fingerprint},
        )


class DciCompleteBenchmarkImplementation:
    async def execute(self, invocation: PackageInvocation) -> PackageExecutionResult:
        verdict = _artifact(invocation, "application/vnd.dci.verdict+json")
        is_correct = verdict.get("is_correct")
        if not isinstance(is_correct, bool):
            raise PackageExecutionError("complete benchmark evidence is invalid")
        return _result(
            stage="benchmark",
            media_type="application/vnd.dci.benchmark+json",
            value={"total": 1, "judged": 1, "correct": int(is_correct), "failed": 0},
        )


class DciCompleteAnalysisImplementation:
    async def execute(self, invocation: PackageInvocation) -> PackageExecutionResult:
        benchmark = _artifact(invocation, "application/vnd.dci.benchmark+json")
        correct = benchmark.get("correct")
        if type(correct) is not int or correct not in {0, 1}:
            raise PackageExecutionError("complete analysis evidence is invalid")
        aggregate = aggregate_results(({"is_correct": bool(correct), "run_status": "completed"},))
        return _result(
            stage="analysis",
            media_type="application/vnd.dci.analysis+json",
            value={"aggregate": aggregate},
        )


class DciCompleteExportImplementation:
    def __init__(self, *, store: DciCompleteAttemptStore) -> None:
        self._store = store

    async def execute(self, invocation: PackageInvocation) -> PackageExecutionResult:
        analysis = _artifact(invocation, "application/vnd.dci.analysis+json")
        aggregate = analysis.get("aggregate")
        if not isinstance(aggregate, Mapping):
            raise PackageExecutionError("complete export evidence is invalid")
        digest = hashlib.sha256(
            json.dumps(_plain(aggregate), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        self._store.finish(invocation.run_id)
        counts = aggregate.get("counts")
        if not isinstance(counts, Mapping) or type(counts.get("total")) is not int:
            raise PackageExecutionError("complete export evidence is invalid")
        return _result(
            stage="export",
            media_type="application/vnd.dci.export+json",
            value={"analysis_sha256": digest, "total": counts["total"]},
        )


def complete_dci_bindings(
    *, native_executor: DciRunExecutor
) -> tuple[tuple[object, object], ...]:
    from asterion.packages.catalog import PackageRef

    store = DciCompleteAttemptStore()
    return (
        (PackageRef("dci.research", "1.0.0"), DciCompleteResearchImplementation(store=store, native_executor=native_executor)),
        (PackageRef("dci.evaluation", "1.0.0"), DciCompleteEvaluationImplementation(store=store)),
        (PackageRef("dci.benchmark", "1.0.0"), DciCompleteBenchmarkImplementation()),
        (PackageRef("dci.analysis", "1.0.0"), DciCompleteAnalysisImplementation()),
        (PackageRef("dci.export", "1.0.0"), DciCompleteExportImplementation(store=store)),
    )
