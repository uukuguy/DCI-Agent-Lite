"""Explicit projection from native Asterion DCI runs to package outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from asterion.dci.run import DciRunRequest, DciRunResult
from asterion.packages.execution import PackageExecutionResult
from asterion.runtime.protocol import validate_event_stream


class DciRunExecutor(Protocol):
    """Narrow native DCI executor boundary reserved for application integration."""

    def run(self, request: DciRunRequest) -> DciRunResult: ...


def project_dci_run(result: DciRunResult) -> PackageExecutionResult:
    """Project verified native artifacts without exposing answer or diagnostic bodies."""

    if result.status != "completed" or result.events[-1].type != "run.completed":
        raise ValueError("native DCI run is not completed")
    event_mappings = [event.to_mapping() for event in result.events]
    validate_event_stream(event_mappings)
    final_artifact = next(
        (
            event.payload.get("artifact")
            for event in result.events
            if event.type == "artifact.created"
        ),
        None,
    )
    if not isinstance(final_artifact, dict) or final_artifact.get("uri") != "final.txt":
        raise ValueError("native DCI final artifact is invalid")
    value = {
        "answer_artifact_uri": "final.txt",
        "conversation_artifact_uri": "conversation.json",
        "events_artifact_uri": "events.jsonl",
        "latest_model_context_artifact_uri": "latest_model_context.json",
        "protocol_artifact_uri": "protocol/",
        "state_artifact_uri": "state.json",
    }
    if _has_valid_evaluation(result.output_dir):
        value["evaluation_artifact_uri"] = "eval_result.json"
    return PackageExecutionResult(
        events=(
            {"type": "research.completed", "payload": {"status": "completed"}},
        ),
        artifacts=(
            {
                "artifact_id": "dci-research-result",
                "media_type": "application/vnd.dci.research+json",
                "value": value,
            },
        ),
    )


def _has_valid_evaluation(output_dir: Path) -> bool:
    try:
        value = json.loads((output_dir / "eval_result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(value, dict) and isinstance(value.get("is_correct"), bool)
