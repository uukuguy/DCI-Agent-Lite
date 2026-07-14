from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.dci.config import DciRuntimeOptions, resolve_dci_paths
from asterion.dci.artifacts import DciConversationFeatures
from asterion.dci.run import (
    DciRunError,
    DciRunRequest,
    _pi_extra_args,
    request_from_runtime_options,
    resume_request_from_output_dir,
    run_pi_research,
)
from asterion.runtime.protocol import validate_event_stream


class FixturePiClient:
    events = [
        {"type": "response", "id": "py-1", "success": True},
        {
            "type": "message_update",
            "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
        },
        {"type": "agent_end"},
    ]

    def __init__(self, **_: object) -> None:
        self.stderr_chunks = ["private stderr"]

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def prompt_and_wait(self, _: str, *, on_event, **__: object) -> str:
        for event in self.events:
            on_event(event)
        return "answer"


class FailingPiClient(FixturePiClient):
    def prompt_and_wait(self, _: str, **__: object) -> str:
        raise RuntimeError("provider response and private stderr")


class LifecyclePiClient(FixturePiClient):
    output_dir: Path

    def prompt_and_wait(self, _: str, *, on_event, **__: object) -> str:
        tool_ids = ("../escape", "..\\escape", "call-3", "call-4")
        events: list[dict[str, object]] = [
            {"type": "response", "id": "py-1", "success": True},
            {
                "type": "message_start",
                "message": {"role": "assistant", "content": []},
            },
            {
                "type": "message_update",
                "assistantMessageEvent": {
                    "type": "text_delta",
                    "delta": "answer",
                    "partial": {
                        "role": "assistant",
                        "content": [{"type": "text", "text": "answer"}],
                    },
                },
            },
        ]
        for index, call_id in enumerate(tool_ids, 1):
            events.extend(
                [
                    {
                        "type": "tool_execution_start",
                        "toolCallId": call_id,
                        "toolName": "read",
                        "args": {"path": f"item-{index}"},
                    },
                    {
                        "type": "tool_execution_end",
                        "toolCallId": call_id,
                        "toolName": "read",
                        "isError": False,
                        "result": f"body-{index}",
                    },
                    {
                        "type": "message_end",
                        "message": {
                            "role": "toolResult",
                            "toolCallId": call_id,
                            "toolName": "read",
                            "content": [{"type": "text", "text": f"SECRET-BODY-{index}"}],
                        },
                    },
                ]
            )
        events.extend(
            [
                {
                    "type": "provider_request_context",
                    "requestIndex": 1,
                    "model": "provider/model-old",
                    "messages": [{"role": "user", "content": "old"}],
                    "payload": {"private": "old-payload"},
                    "runtimeContextManagement": {"level": "level2"},
                },
                {
                    "type": "provider_request_context",
                    "requestIndex": 2,
                    "model": "provider/model-latest",
                    "messages": [{"role": "user", "content": "latest"}],
                    "payload": {"private": "latest-payload"},
                    "runtimeContextManagement": {"level": "level3"},
                },
                {
                    "type": "message_end",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "thinking", "thinking": "PRIVATE-THINKING"},
                            {"type": "text", "text": "answer"},
                        ],
                        "usage": {"input": 10, "output": 2},
                    },
                },
                {"type": "agent_end"},
                {"type": "agent_settled"},
            ]
        )
        for event in events:
            on_event(event)
            state = json.loads((self.output_dir / "state.json").read_text())
            assert state["status"] == "running"
            conversation = json.loads((self.output_dir / "conversation_full.json").read_text())
            if event["type"] == "message_start":
                assert conversation["pending_message"]["role"] == "assistant"
            if event["type"] == "message_update":
                assert conversation["pending_message"]["content"][0]["text"] == "answer"
        return "answer"


class AsterionDciRunTests(unittest.TestCase):
    def test_production_path_records_complete_conversation_and_latest_context(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "run"
            LifecyclePiClient.output_dir = output_dir
            system_prompt = root / "system.txt"
            append_prompt = root / "append.txt"
            system_prompt.write_text("system base", encoding="utf-8")
            append_prompt.write_text("system append", encoding="utf-8")
            request = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                system_prompt_file=system_prompt,
                append_system_prompt_file=append_prompt,
            )
            features = DciConversationFeatures(
                externalize_tool_results=True,
                clear_tool_results=True,
                clear_tool_results_keep_last=2,
                strip_thinking=True,
                strip_usage=True,
            )
            with patch("asterion.dci.run.PiRpcClient", LifecyclePiClient):
                result = run_pi_research(
                    paths,
                    request,
                    output_dir=output_dir,
                    conversation_features=features,
                )

            state = json.loads((output_dir / "state.json").read_text())
            full = json.loads((output_dir / "conversation_full.json").read_text())
            latest = json.loads((output_dir / "latest_model_context.json").read_text())
            self.assertEqual(result.status, "completed")
            self.assertEqual(state["status"], "completed")
            self.assertEqual(state["event_count"], 20)
            self.assertEqual(state["assistant_text"], "answer")
            self.assertEqual(len(state["tool_calls"]), 8)
            self.assertTrue(
                all(
                    entry["started_at"] is not None
                    and entry["finished_at"] is not None
                    and entry["duration_seconds"] >= 0
                    for entry in state["tool_calls"]
                    if entry["event"] == "tool_execution_end"
                )
            )
            self.assertEqual(latest["request_count"], 2)
            self.assertEqual(latest["latest"]["model"], "provider/model-latest")
            self.assertEqual(latest["latest"]["payload"], {"private": "latest-payload"})
            self.assertEqual(latest["runtime_context_management"], {"level": "level3"})
            self.assertEqual(full["messages"][0]["role"], "system")
            self.assertEqual(
                [message["role"] for message in full["messages"]],
                ["system", "toolResult", "toolResult", "toolResult", "toolResult", "assistant"],
            )
            self.assertEqual(
                full["messages"][0]["sources"],
                {
                    "system_prompt_file": str(system_prompt),
                    "append_system_prompt_file": str(append_prompt),
                },
            )
            self.assertIsNone(full["pending_message"])
    def test_runtime_context_request_is_recorded_without_fabricating_a_pi_flag(self) -> None:
        request = DciRunRequest(
            run_id="run-1",
            question="question",
            cwd=Path("/work"),
            runtime_context_level="level3",
            thinking_level="high",
        )

        self.assertEqual(_pi_extra_args(request), ("--thinking", "high"))

    def test_runtime_context_request_records_current_pi_capability_diagnostic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            request = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                runtime_context_level="level3",
            )
            with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                result = run_pi_research(paths, request)

            state = json.loads((result.output_dir / "state.json").read_text())

        self.assertEqual(
            state["runtime_context_control"],
            {
                "effective_pi_control": None,
                "requested_level": "level3",
                "status": "unsupported",
            },
        )

    def test_runtime_options_map_to_native_pi_request(self) -> None:
        options = DciRuntimeOptions(
            provider="provider",
            model="model",
            tools="read,bash",
            timeout_seconds=90.0,
            runtime_context_level="level3",
            thinking_level="high",
            node_max_old_space_size_mb=8192,
            keep_session=True,
            extra_args=("--custom option",),
        )

        request = request_from_runtime_options(
            options, run_id="run-1", question="question", cwd=Path("/work")
        )

        self.assertEqual(request.provider, "provider")
        self.assertEqual(request.model, "model")
        self.assertEqual(request.runtime_context_level, "level3")
        self.assertEqual(request.thinking_level, "high")
        self.assertEqual(request.node_max_old_space_size_mb, 8192)
        self.assertTrue(request.keep_session)
        self.assertEqual(request.extra_args, ("--custom option",))

    def test_resume_reuses_failed_directory_and_creates_a_second_protocol_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "run"
            first = DciRunRequest(run_id="run-1", question="question", cwd=root)
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, first, output_dir=output_dir)
            resumed = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                resume=True,
            )
            with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                result = run_pi_research(paths, resumed, output_dir=output_dir)

            self.assertEqual(result.status, "completed")
            self.assertTrue((output_dir / "protocol/attempt-0002.request.json").is_file())
            self.assertEqual(json.loads((output_dir / "state.json").read_text())["resume_count"], 1)

    def test_resume_rejects_completed_or_changed_immutable_inputs_before_client_start(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "run"
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                run_pi_research(paths, request, output_dir=output_dir)

            completed = DciRunRequest(run_id="run-1", question="question", cwd=root, resume=True)
            with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                run_pi_research(paths, completed, output_dir=output_dir)

            failed_dir = root / "failed"
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, request, output_dir=failed_dir)
            changed = DciRunRequest(
                run_id="run-1", question="question", cwd=root, model="different", resume=True
            )
            with patch("asterion.dci.run.PiRpcClient") as client:
                with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                    run_pi_research(paths, changed, output_dir=failed_dir)
            client.assert_not_called()

    def test_resume_reconstructs_and_validates_runtime_controls_before_client_start(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "failed"
            request = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                runtime_context_level="level3",
                thinking_level="high",
                node_max_old_space_size_mb=8192,
                keep_session=True,
            )
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, request, output_dir=output_dir)

            resumed = resume_request_from_output_dir(output_dir)
            self.assertEqual(resumed.runtime_context_level, "level3")
            self.assertEqual(resumed.thinking_level, "high")
            self.assertEqual(resumed.node_max_old_space_size_mb, 8192)
            self.assertTrue(resumed.keep_session)

            changed = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                runtime_context_level="level2",
                thinking_level="high",
                node_max_old_space_size_mb=8192,
                keep_session=True,
                resume=True,
            )
            with patch("asterion.dci.run.PiRpcClient") as client:
                with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                    run_pi_research(paths, changed, output_dir=output_dir)
            client.assert_not_called()

    def test_completed_run_writes_native_artifacts_and_protocol_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                result = run_pi_research(paths, request)

            self.assertEqual(result.final_text, "answer")
            self.assertEqual((result.output_dir / "question.txt").read_text(), "question\n")
            self.assertTrue((result.output_dir / "events.jsonl").is_file())
            self.assertEqual((result.output_dir / "final.txt").read_text(), "answer\n")
            self.assertTrue((result.output_dir / "state.json").is_file())
            self.assertEqual([event.type for event in result.events][-2:], ["artifact.created", "run.completed"])
            validate_event_stream([event.to_mapping() for event in result.events])
            state = json.loads((result.output_dir / "state.json").read_text())
            self.assertTrue(
                {
                    "run_id",
                    "status",
                    "question_path",
                    "final_path",
                    "events_path",
                    "stderr_path",
                    "question",
                    "cwd",
                    "provider",
                    "model",
                    "tools",
                    "max_turns",
                    "runtime_context_level",
                    "thinking_level",
                    "node_max_old_space_size_mb",
                    "keep_session",
                    "resume_count",
                }.issubset(state)
            )
            self.assertTrue((result.output_dir / "protocol/attempt-0001.request.json").is_file())
            self.assertTrue((result.output_dir / "protocol/attempt-0001.events.jsonl").is_file())

    def test_rejects_a_nonempty_output_and_keeps_failure_detail_out_of_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            output_dir = root / "existing"
            output_dir.mkdir()
            (output_dir / "old.txt").write_text("old")
            with self.assertRaisesRegex(DciRunError, "output directory is not empty"):
                run_pi_research(paths, request, output_dir=output_dir)

            failing_request = DciRunRequest(run_id="run-2", question="question", cwd=root)
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaisesRegex(DciRunError, "DCI Pi execution failed") as caught:
                    run_pi_research(paths, failing_request)

        self.assertNotIn("provider response", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
