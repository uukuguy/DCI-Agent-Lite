"""Durable native artifacts for an independent Asterion DCI run."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from asterion.adapters.pi import PiProtocolAdapter, map_pi_capabilities
from asterion.dci.config import DciPaths
from asterion.dci.run import DciRunRequest
from asterion.runtime.host import RunEvent
from asterion.runtime.protocol import PROTOCOL_VERSION, validate_event_stream, validate_run_request


@dataclass(frozen=True)
class DciConversationFeatures:
    """Opt-in processing controls for the investigator-facing conversation view."""

    clear_tool_results: bool = False
    clear_tool_results_keep_last: int = 3
    externalize_tool_results: bool = False
    strip_thinking: bool = False
    strip_usage: bool = False


class DciRunRecorder:
    """Persist raw and processed DCI run evidence without crossing product boundaries."""

    def __init__(
        self,
        *,
        output_dir: Path,
        request: DciRunRequest,
        paths: DciPaths,
        features: DciConversationFeatures | None = None,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.request = request
        self.paths = paths
        self.features = features or DciConversationFeatures()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.output_dir / "events.jsonl"
        self.state_path = self.output_dir / "state.json"
        self.question_path = self.output_dir / "question.txt"
        self.final_path = self.output_dir / "final.txt"
        self.stderr_path = self.output_dir / "stderr.txt"
        self.conversation_full_path = self.output_dir / "conversation_full.json"
        self.conversation_path = self.output_dir / "conversation.json"
        self.latest_model_context_path = self.output_dir / "latest_model_context.json"
        self.protocol_dir = self.output_dir / "protocol"
        self.protocol_dir.mkdir(exist_ok=True)
        self.protocol_request_path = self.protocol_dir / "attempt-0001.request.json"
        self.protocol_events_path = self.protocol_dir / "attempt-0001.events.jsonl"
        self.events_path.write_text("", encoding="utf-8")
        self.protocol_events_path.write_text("", encoding="utf-8")
        self.question_path.write_text(f"{request.question}\n", encoding="utf-8")
        self.state: dict[str, Any] = {
            "run_id": request.run_id,
            "status": "running",
            "question": request.question,
            "cwd": str(request.cwd),
            "provider": request.provider,
            "model": request.model,
            "tools": request.tools,
            "event_count": 0,
            "assistant_text": "",
            "paths": {
                "events_jsonl": str(self.events_path),
                "conversation_full_json": str(self.conversation_full_path),
                "conversation_json": str(self.conversation_path),
                "latest_model_context_json": str(self.latest_model_context_path),
                "final_txt": str(self.final_path),
                "stderr_txt": str(self.stderr_path),
            },
        }
        self.conversation_full: dict[str, Any] = {
            "status": "running",
            "question": request.question,
            "messages": [],
            "final_text": None,
        }
        self.latest_model_context: dict[str, Any] = {"status": "running", "latest": None}
        self.normalized: list[dict[str, object]] = []
        capabilities = map_pi_capabilities(request.tools)
        protocol_request: dict[str, object] = {
            "protocol": PROTOCOL_VERSION,
            "run_id": f"{request.run_id}-attempt-0001",
            "input": {"text": request.question},
            "requested_capabilities": capabilities,
        }
        validate_run_request(protocol_request)
        self.protocol_request_path.write_text(json.dumps(protocol_request, indent=2) + "\n", encoding="utf-8")
        self.adapter = PiProtocolAdapter(
            run_id=str(protocol_request["run_id"]),
            capabilities=capabilities,
            emit=self._emit_normalized,
        )
        self.adapter.start()
        self._write()

    def _emit_normalized(self, event: dict[str, object]) -> None:
        self.normalized.append(dict(event))
        self._append(self.protocol_events_path, event)

    def record_event(self, event: dict[str, object]) -> None:
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

    def finalize(self, *, status: str, final_text: str = "", stderr_text: str = "") -> tuple[RunEvent, ...]:
        answer = final_text or self.state["assistant_text"]
        if answer:
            self.final_path.write_text(answer if answer.endswith("\n") else f"{answer}\n", encoding="utf-8")
        if stderr_text:
            self.stderr_path.write_text(stderr_text[-16384:], encoding="utf-8")
        self.state["status"] = status
        self.state["assistant_text"] = answer
        self.conversation_full["status"] = status
        self.conversation_full["final_text"] = answer
        if status == "completed":
            self.adapter.complete(
                artifact={"artifact_id": "final-answer", "kind": "answer", "media_type": "text/plain", "uri": "final.txt"}
            )
        else:
            self.adapter.fail()
        validate_event_stream(self.normalized)
        self._write()
        return tuple(RunEvent.from_mapping(event) for event in self.normalized)

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
                directory.mkdir(exist_ok=True)
                self._json(directory / f"{call_id}.json", {"message": message})
            if self.features.clear_tool_results:
                message["content"] = [{"type": "text", "text": "[tool result cleared from conversation context]"}]
        return conversation

    @staticmethod
    def _append(path: Path, value: dict[str, object]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(value, ensure_ascii=False) + "\n")

    @staticmethod
    def _json(path: Path, value: dict[str, Any]) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
