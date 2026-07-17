from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import tempfile
import threading
import unittest
from contextlib import redirect_stderr
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from asterion.dci.config import DciRuntimeOptions, resolve_dci_paths
from asterion.dci.artifacts import DciConversationFeatures
from asterion.dci.run import (
    DciRunError,
    DciRunRequest,
    _pi_extra_args,
    _validate_pi_context_session,
    request_from_runtime_options,
    resume_request_from_output_dir,
    run_pi_research,
    validate_dci_run_request,
)
from asterion.runtime.protocol import MAX_DEADLINE_MS, validate_event_stream


class FixturePiClient:
    last_kwargs: dict[str, object] = {}
    get_entries_calls = 0
    last_since: str | None = None
    events = [
        {"type": "response", "id": "py-1", "success": True},
        {
            "type": "message_update",
            "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
        },
        {"type": "agent_end"},
    ]

    def __init__(self, **kwargs: object) -> None:
        self.stderr_chunks = ["private stderr"]
        type(self).last_kwargs = dict(kwargs)
        type(self).get_entries_calls = 0

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def get_stderr(self) -> str:
        return "".join(self.stderr_chunks)

    def prompt_and_wait(self, _: str, *, on_event, **__: object) -> str:
        for event in self.events:
            on_event(event)
        return "answer"

    def probe_protocol(self, **_: object) -> dict[str, object]:
        agent_dir = self.last_kwargs["agent_dir"]
        assert isinstance(agent_dir, Path)
        session_file = agent_dir / "sessions/session-fixture.jsonl"
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.touch(exist_ok=True)
        return {
            "sessionFile": str(session_file),
            "sessionId": "session-fixture",
            "isStreaming": False,
            "isCompacting": False,
            "messageCount": 0,
            "pendingMessageCount": 0,
        }

    def get_entries(
        self, *, since: str | None = None
    ) -> tuple[dict[str, object], ...]:
        type(self).get_entries_calls += 1
        type(self).last_since = since
        profile = self.last_kwargs.get("context_profile")
        contract = self.last_kwargs.get("context_contract")
        state = {
            "accumulatedOriginalToolCharacters": 0,
            "truncatedResults": 0,
            "compactionCount": 0,
            "preservedTurns": None,
            "compactionPending": False,
            "summaryAttempts": 0,
            "summarySuccesses": 0,
            "consecutiveSummaryFailures": 0,
            "summarySuppressed": False,
        }
        return (
            {
                "id": "entry-1",
                "parentId": None,
                "timestamp": "2026-07-17T00:00:00.000Z",
                "type": "custom",
                "customType": "dci-context-telemetry",
                "data": {
                    "schema": "dci.context-telemetry/v2",
                    "event": "startup",
                    "profile": profile,
                    "contractVersion": contract,
                    "extensionVersion": "0.2.0",
                    **state,
                },
            },
            {
                "id": "entry-2",
                "parentId": "entry-1",
                "timestamp": "2026-07-17T00:00:00.001Z",
                "type": "custom",
                "customType": "dci-context-state",
                "data": {
                    "schema": "dci.context-state/v2",
                    "profile": profile,
                    "contractVersion": contract,
                    "state": state,
                },
            },
        )


class FailingPiClient(FixturePiClient):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.stderr_chunks = ["failure stderr"]

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
                            "content": [
                                {"type": "text", "text": f"SECRET-BODY-{index}"}
                            ],
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
            conversation = json.loads(
                (self.output_dir / "conversation_full.json").read_text()
            )
            if event["type"] == "message_start":
                assert conversation["pending_message"]["role"] == "assistant"
            if event["type"] == "message_update":
                assert conversation["pending_message"]["content"][0]["text"] == "answer"
        return "answer"


class AsterionDciRunTests(unittest.TestCase):
    def test_resume_rejects_relabelled_completed_or_mismatched_run_id_stream_without_mutation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            for case in ("completed-as-failed", "mismatched-run-id"):
                with self.subTest(case=case):
                    output = root / case
                    with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                        run_pi_research(paths, request, output_dir=output)
                    if case == "completed-as-failed":
                        for name in (
                            "state.json",
                            "conversation.json",
                            "conversation_full.json",
                            "latest_model_context.json",
                        ):
                            path = output / name
                            value = json.loads(path.read_text())
                            value["status"] = "failed"
                            if name == "state.json":
                                value["attempts"][-1]["status"] = "failed"
                            path.write_text(json.dumps(value), encoding="utf-8")
                    else:
                        state_path = output / "state.json"
                        state = json.loads(state_path.read_text())
                        state["status"] = "failed"
                        state["attempts"][-1]["status"] = "failed"
                        state_path.write_text(json.dumps(state), encoding="utf-8")
                        for name in (
                            "conversation.json",
                            "conversation_full.json",
                            "latest_model_context.json",
                        ):
                            path = output / name
                            value = json.loads(path.read_text())
                            value["status"] = "failed"
                            path.write_text(json.dumps(value), encoding="utf-8")
                        events_path = output / "protocol/attempt-0001.events.jsonl"
                        events = [
                            json.loads(line)
                            for line in events_path.read_text().splitlines()
                        ]
                        for event in events:
                            event["run_id"] = "different-attempt"
                        events[-1]["type"] = "run.failed"
                        events[-1]["payload"] = {
                            "code": "fixture",
                            "message": "fixture",
                        }
                        events_path.write_text(
                            "".join(json.dumps(event) + "\n" for event in events),
                            encoding="utf-8",
                        )
                    before = {
                        path.relative_to(output): path.read_bytes()
                        for path in output.rglob("*")
                        if path.is_file() and path.name != ".dci-run.lock"
                    }
                    with patch("asterion.dci.run.PiRpcClient") as client:
                        with self.assertRaisesRegex(
                            DciRunError, "resume validation failed"
                        ):
                            run_pi_research(
                                paths,
                                replace(request, resume=True),
                                output_dir=output,
                            )
                    client.assert_not_called()
                    self.assertEqual(
                        before,
                        {
                            path.relative_to(output): path.read_bytes()
                            for path in output.rglob("*")
                            if path.is_file() and path.name != ".dci-run.lock"
                        },
                    )

    def test_resume_reconstruction_directly_rejects_invalid_candidate_values(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output = root / "run"
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, request, output_dir=output)
            state_path = output / "state.json"
            baseline = json.loads(state_path.read_text())
            for field, value in (
                ("max_turns", -7),
                ("timeout_seconds", 7),
                ("keep_session", 1),
                ("thinking_level", "bogus"),
                ("cwd", "relative"),
                ("pi_package_dir", "relative"),
            ):
                with self.subTest(field=field):
                    state = dict(baseline)
                    state[field] = value
                    state_path.write_text(json.dumps(state), encoding="utf-8")
                    with self.assertRaisesRegex(
                        DciRunError, "resume validation failed"
                    ):
                        resume_request_from_output_dir(output)
            state_path.write_text(json.dumps(baseline), encoding="utf-8")

    def test_resume_rejects_prior_deadline_mismatch_without_mutation_or_client(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output = root / "run"
            request = DciRunRequest(
                run_id="run-1", question="question", cwd=root, timeout_seconds=12.5
            )
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, request, output_dir=output)
            protocol_path = output / "protocol/attempt-0001.request.json"
            protocol = json.loads(protocol_path.read_text())
            protocol["deadline_ms"] = 1
            protocol_path.write_text(json.dumps(protocol), encoding="utf-8")
            before = {
                p.relative_to(output): p.read_bytes()
                for p in output.rglob("*")
                if p.is_file() and p.name != ".dci-run.lock"
            }
            with patch("asterion.dci.run.PiRpcClient") as client:
                with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                    run_pi_research(
                        paths, replace(request, resume=True), output_dir=output
                    )
            client.assert_not_called()
            self.assertEqual(
                before,
                {
                    p.relative_to(output): p.read_bytes()
                    for p in output.rglob("*")
                    if p.is_file() and p.name != ".dci-run.lock"
                },
            )

    def test_resume_preflight_rejects_missing_and_orphan_evidence_without_mutation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            for missing in (
                "events.jsonl",
                "question.txt",
                "conversation.json",
                "protocol",
            ):
                with self.subTest(missing=missing):
                    output = root / f"missing-{missing.replace('.', '-')}"
                    with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                        with self.assertRaises(DciRunError):
                            run_pi_research(paths, request, output_dir=output)
                    target = output / missing
                    if target.is_dir():
                        import shutil

                        shutil.rmtree(target)
                    else:
                        target.unlink()
                    before = {
                        p.relative_to(output): p.read_bytes()
                        for p in output.rglob("*")
                        if p.is_file() and p.name != ".dci-run.lock"
                    }
                    with patch("asterion.dci.run.PiRpcClient") as client:
                        with self.assertRaisesRegex(
                            DciRunError, "resume validation failed"
                        ):
                            run_pi_research(
                                paths, replace(request, resume=True), output_dir=output
                            )
                    client.assert_not_called()
                    self.assertEqual(
                        before,
                        {
                            p.relative_to(output): p.read_bytes()
                            for p in output.rglob("*")
                            if p.is_file() and p.name != ".dci-run.lock"
                        },
                    )
                    self.assertFalse(target.exists())

            output = root / "orphan"
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, request, output_dir=output)
            orphan = output / "protocol/attempt-0002.events.jsonl"
            orphan.write_text("ORPHAN\n", encoding="utf-8")
            before = orphan.read_bytes()
            with patch("asterion.dci.run.PiRpcClient") as client:
                with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                    run_pi_research(
                        paths, replace(request, resume=True), output_dir=output
                    )
            client.assert_not_called()
            self.assertEqual(orphan.read_bytes(), before)

    def test_authoritative_request_validation_rejects_invalid_values_before_artifacts(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            base = DciRunRequest(run_id="run-1", question="question", cwd=root)
            invalid = (
                ("max_turns", 0),
                ("max_turns", -1),
                ("max_turns", True),
                ("timeout_seconds", -1.0),
                ("timeout_seconds", float("nan")),
                ("timeout_seconds", 1),
                ("node_max_old_space_size_mb", 0),
                ("keep_session", 1),
                ("show_tools", 0),
                ("stream_text", 1),
                ("resume", 0),
                ("tools", ""),
                ("provider", ""),
                ("thinking_level", "bogus"),
                ("cwd", Path("relative")),
                ("system_prompt_file", Path("relative")),
                ("extra_args", ["--x"]),
            )
            for index, (field, value) in enumerate(invalid):
                with self.subTest(field=field, value=value):
                    output = root / f"invalid-{index}"
                    with patch("asterion.dci.run.PiRpcClient") as client:
                        with self.assertRaises(DciRunError):
                            run_pi_research(
                                paths,
                                replace(base, **{field: value}),
                                output_dir=output,
                            )
                    client.assert_not_called()
                    self.assertFalse(output.exists())

    def test_resume_persists_latest_timeout_and_rejects_conflicting_feature_authorities(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output = root / "run"
            features = DciConversationFeatures(strip_usage=True)
            request = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                timeout_seconds=90.0,
                conversation_features=features,
            )
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, request, output_dir=output)
                with self.assertRaises(DciRunError):
                    run_pi_research(
                        paths,
                        replace(request, resume=True, timeout_seconds=12.5),
                        output_dir=output,
                    )
            state = json.loads((output / "state.json").read_text())
            self.assertEqual(state["timeout_seconds"], 12.5)
            self.assertEqual(state["attempts"][1]["timeout_seconds"], 12.5)
            self.assertEqual(
                resume_request_from_output_dir(output).timeout_seconds, 12.5
            )
            with patch("asterion.dci.run.PiRpcClient") as client:
                with self.assertRaises(DciRunError):
                    run_pi_research(
                        paths,
                        replace(request, resume=True),
                        output_dir=output,
                        conversation_features=DciConversationFeatures(
                            strip_thinking=True
                        ),
                    )
            client.assert_not_called()

    def test_directory_lock_is_held_until_client_stop_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output = root / "run"
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            stopping = threading.Event()
            release = threading.Event()

            class BlockingStopClient(FailingPiClient):
                def stop(self) -> None:
                    stopping.set()
                    release.wait(timeout=5)

            errors: list[Exception] = []

            def first() -> None:
                try:
                    run_pi_research(paths, request, output_dir=output)
                except Exception as exc:
                    errors.append(exc)

            with patch("asterion.dci.run.PiRpcClient", BlockingStopClient):
                thread = threading.Thread(target=first)
                thread.start()
                self.assertTrue(stopping.wait(timeout=5))
                with patch("asterion.dci.run.PiRpcClient") as client:
                    with self.assertRaisesRegex(
                        DciRunError, "resume validation failed"
                    ):
                        run_pi_research(
                            paths, replace(request, resume=True), output_dir=output
                        )
                client.assert_not_called()
                release.set()
                thread.join(timeout=5)
            self.assertEqual(len(errors), 1)

    def test_cancellation_finalizes_one_failed_attempt_and_drains_stop_before_unlock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output = root / "run"
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            cancel = threading.Event()
            entered = threading.Event()
            stopping = threading.Event()
            release_stop = threading.Event()

            class CancellableClient(FixturePiClient):
                def prompt_and_wait(self, _: str, *, cancel_event, **__: object) -> str:
                    entered.set()
                    self.assert_event = cancel_event
                    cancel_event.wait(timeout=5)
                    raise RuntimeError("cancelled private work")

                def stop(self) -> None:
                    stopping.set()
                    release_stop.wait(timeout=5)

            errors: list[Exception] = []

            def invoke() -> None:
                try:
                    run_pi_research(
                        paths, request, output_dir=output, _cancel_event=cancel
                    )
                except Exception as error:
                    errors.append(error)

            with patch("asterion.dci.run.PiRpcClient", CancellableClient):
                thread = threading.Thread(target=invoke)
                thread.start()
                self.assertTrue(entered.wait(timeout=5))
                cancel.set()
                self.assertTrue(stopping.wait(timeout=5))
                with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                    run_pi_research(
                        paths, replace(request, resume=True), output_dir=output
                    )
                release_stop.set()
                thread.join(timeout=5)

            self.assertFalse(thread.is_alive())
            self.assertEqual(len(errors), 1)
            state = json.loads((output / "state.json").read_text())
            self.assertEqual(state["status"], "failed")
            self.assertEqual(len(state["attempts"]), 1)
            self.assertEqual(state["attempts"][0]["status"], "failed")
            attempt_requests = tuple((output / "protocol").glob("attempt-*.request.json"))
            self.assertEqual(len(attempt_requests), 1)

    def test_resume_rejects_missing_state_without_creating_a_directory_or_client(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "missing"
            request = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                resume=True,
            )
            with patch("asterion.dci.run.PiRpcClient") as client:
                with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                    run_pi_research(paths, request, output_dir=output_dir)
            client.assert_not_called()
            self.assertFalse(output_dir.exists())

    def test_resume_rejects_each_changed_or_malformed_immutable_semantic_before_client(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            system_prompt = root / "system.txt"
            append_prompt = root / "append.txt"
            system_prompt.write_text("system", encoding="utf-8")
            append_prompt.write_text("append", encoding="utf-8")
            features = DciConversationFeatures(strip_thinking=True)
            original = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                provider="provider",
                model="model",
                tools="read,bash",
                max_turns=9,
                timeout_seconds=90.0,
                runtime_context_level="level3",
                thinking_level="high",
                node_max_old_space_size_mb=8192,
                keep_session=True,
                extra_args=("--secret value",),
                show_tools=True,
                system_prompt_file=system_prompt,
                append_system_prompt_file=append_prompt,
                stream_text=False,
            )
            baseline = root / "baseline"
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(
                        paths,
                        original,
                        output_dir=baseline,
                        conversation_features=features,
                    )

            mutations = {
                "run_id": "run-2",
                "question": "changed",
                "cwd": root / "changed",
                "provider": "changed-provider",
                "model": "changed-model",
                "tools": "read",
                "max_turns": 10,
                "runtime_context_level": "level2",
                "thinking_level": "low",
                "node_max_old_space_size_mb": 4096,
                "keep_session": False,
                "extra_args": ("--different",),
                "show_tools": False,
                "system_prompt_file": root / "different-system.txt",
                "append_system_prompt_file": root / "different-append.txt",
                "stream_text": True,
            }
            for field, value in mutations.items():
                with self.subTest(field=field):
                    request = replace(original, **{field: value}, resume=True)
                    with patch("asterion.dci.run.PiRpcClient") as client:
                        with self.assertRaisesRegex(
                            DciRunError, "resume validation failed"
                        ):
                            run_pi_research(
                                paths,
                                request,
                                output_dir=baseline,
                                conversation_features=features,
                            )
                    client.assert_not_called()

            for label, changed_paths in (
                (
                    "package_dir",
                    replace(
                        paths,
                        pi=replace(paths.pi, package_dir=root / "different-package"),
                    ),
                ),
                (
                    "agent_dir",
                    replace(
                        paths, pi=replace(paths.pi, agent_dir=root / "different-agent")
                    ),
                ),
            ):
                with self.subTest(field=label):
                    with patch("asterion.dci.run.PiRpcClient") as client:
                        with self.assertRaisesRegex(
                            DciRunError, "resume validation failed"
                        ):
                            run_pi_research(
                                changed_paths,
                                replace(original, resume=True),
                                output_dir=baseline,
                                conversation_features=features,
                            )
                    client.assert_not_called()

            with patch("asterion.dci.run.PiRpcClient") as client:
                with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                    run_pi_research(
                        paths,
                        replace(original, resume=True),
                        output_dir=baseline,
                        conversation_features=DciConversationFeatures(strip_usage=True),
                    )
            client.assert_not_called()

            state_path = baseline / "state.json"
            baseline_state = json.loads(state_path.read_text(encoding="utf-8"))
            malformed = {
                "run_id": 1,
                "question": None,
                "cwd": [],
                "provider": 1,
                "model": {},
                "tools": False,
                "max_turns": True,
                "timeout_seconds": "90",
                "runtime_context_level": 1,
                "thinking_level": [],
                "node_max_old_space_size_mb": 1.5,
                "keep_session": 1,
                "extra_args_count": True,
                "extra_args_fingerprint": None,
                "show_tools": 0,
                "system_prompt_file": [],
                "append_system_prompt_file": {},
                "stream_text": 1,
                "pi_package_dir": False,
                "pi_agent_dir": 7,
                "conversation_features": [],
            }
            for field, value in malformed.items():
                with self.subTest(malformed=field):
                    state = dict(baseline_state)
                    state[field] = value
                    state_path.write_text(json.dumps(state), encoding="utf-8")
                    with patch("asterion.dci.run.PiRpcClient") as client:
                        with self.assertRaisesRegex(
                            DciRunError, "resume validation failed"
                        ):
                            run_pi_research(
                                paths,
                                replace(original, resume=True),
                                output_dir=baseline,
                                conversation_features=features,
                            )
                    client.assert_not_called()
            for field in (
                "run_id",
                "question",
                "cwd",
                "provider",
                "model",
                "tools",
                "max_turns",
                "timeout_seconds",
                "runtime_context_level",
                "thinking_level",
                "node_max_old_space_size_mb",
                "keep_session",
                "extra_args_count",
                "extra_args_fingerprint",
                "show_tools",
                "system_prompt_file",
                "append_system_prompt_file",
                "stream_text",
                "pi_package_dir",
                "pi_agent_dir",
                "conversation_features",
            ):
                with self.subTest(missing=field):
                    state = dict(baseline_state)
                    state.pop(field)
                    state_path.write_text(json.dumps(state), encoding="utf-8")
                    with patch("asterion.dci.run.PiRpcClient") as client:
                        with self.assertRaisesRegex(
                            DciRunError, "resume validation failed"
                        ):
                            run_pi_research(
                                paths,
                                replace(original, resume=True),
                                output_dir=baseline,
                                conversation_features=features,
                            )
                    client.assert_not_called()
            state_path.write_text(json.dumps(baseline_state), encoding="utf-8")

    def test_resume_reconstruction_requires_matching_extra_args_and_allows_timeout_change(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "failed"
            original = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                timeout_seconds=90.0,
                extra_args=("--private value",),
            )
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, original, output_dir=output_dir)

            with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                resume_request_from_output_dir(output_dir)
            with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                resume_request_from_output_dir(output_dir, extra_args=("--wrong",))

            resumed = resume_request_from_output_dir(
                output_dir,
                extra_args=original.extra_args,
                timeout_seconds=12.5,
            )
            self.assertEqual(resumed.extra_args, original.extra_args)
            self.assertEqual(resumed.timeout_seconds, 12.5)
            self.assertEqual(resumed.pi_package_dir, paths.pi.package_dir)
            self.assertEqual(resumed.pi_agent_dir, paths.pi.agent_dir)
            with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                result = run_pi_research(paths, resumed, output_dir=output_dir)
            protocol = json.loads(
                (output_dir / "protocol/attempt-0002.request.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(result.status, "completed")
            self.assertEqual(protocol["deadline_ms"], 12_500)

    def test_running_state_resumes_only_after_the_os_directory_lock_is_acquired(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "running"
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            from asterion.dci.artifacts import DciRunRecorder

            recorder = DciRunRecorder(
                output_dir=output_dir, request=request, paths=paths
            )
            try:
                with patch("asterion.dci.run.PiRpcClient") as client:
                    with self.assertRaisesRegex(
                        DciRunError, "resume validation failed"
                    ):
                        run_pi_research(
                            paths,
                            replace(request, resume=True),
                            output_dir=output_dir,
                        )
                client.assert_not_called()
            finally:
                recorder.close()

            with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                result = run_pi_research(
                    paths,
                    replace(request, resume=True),
                    output_dir=output_dir,
                )
            self.assertEqual(result.status, "completed")
            self.assertTrue(
                (output_dir / "protocol/attempt-0002.request.json").is_file()
            )
            for number in (1, 2):
                events = [
                    json.loads(line)
                    for line in (
                        output_dir / f"protocol/attempt-{number:04d}.events.jsonl"
                    )
                    .read_text(encoding="utf-8")
                    .splitlines()
                ]
                validate_event_stream(events)
            state = json.loads((output_dir / "state.json").read_text())
            self.assertEqual(state["attempts"][0]["status"], "failed")

    def test_two_resume_contenders_construct_at_most_one_client(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "failed"
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, request, output_dir=output_dir)

            constructed = 0
            constructed_lock = threading.Lock()
            entered = threading.Event()
            release = threading.Event()

            class BlockingClient(FixturePiClient):
                def __init__(self, **kwargs: object) -> None:
                    nonlocal constructed
                    super().__init__(**kwargs)
                    with constructed_lock:
                        constructed += 1

                def prompt_and_wait(self, *_: object, **__: object) -> str:
                    entered.set()
                    release.wait(timeout=5)
                    return "answer"

            errors: list[Exception] = []

            def contend() -> None:
                try:
                    run_pi_research(
                        paths,
                        replace(request, resume=True),
                        output_dir=output_dir,
                    )
                except Exception as exc:  # noqa: BLE001 - assertion captures public boundary
                    errors.append(exc)

            with patch("asterion.dci.run.PiRpcClient", BlockingClient):
                first = threading.Thread(target=contend)
                first.start()
                self.assertTrue(entered.wait(timeout=5))
                second = threading.Thread(target=contend)
                second.start()
                second.join(timeout=5)
                release.set()
                first.join(timeout=5)

            self.assertEqual(constructed, 1)
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], DciRunError)

    def test_production_path_rejects_output_symlink_before_client_or_target_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            foreign = root / "foreign"
            foreign.mkdir()
            linked = root / "linked-run"
            linked.symlink_to(foreign, target_is_directory=True)
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)

            with patch("asterion.dci.run.PiRpcClient") as client:
                with self.assertRaisesRegex(RuntimeError, "symlink"):
                    run_pi_research(paths, request, output_dir=linked)

            client.assert_not_called()
            self.assertEqual(list(foreign.iterdir()), [])

    def test_protocol_request_preserves_bounded_deadline_ms(self) -> None:
        for name, timeout_seconds, expected in (
            ("normal", 12.5, 12_500),
            ("tiny", 0.0001, 1),
            ("over-limit", (MAX_DEADLINE_MS + 1) / 1000, None),
        ):
            with (
                self.subTest(name=name),
                tempfile.TemporaryDirectory() as temporary_directory,
            ):
                root = Path(temporary_directory)
                paths = resolve_dci_paths(root)
                request = DciRunRequest(
                    run_id="run-1",
                    question="question",
                    cwd=root,
                    timeout_seconds=timeout_seconds,
                )
                with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                    result = run_pi_research(paths, request)

                protocol_request = json.loads(
                    (
                        result.output_dir / "protocol/attempt-0001.request.json"
                    ).read_text()
                )
                if expected is None:
                    self.assertNotIn("deadline_ms", protocol_request)
                else:
                    self.assertEqual(protocol_request["deadline_ms"], expected)

    def test_malformed_persisted_features_fail_before_resume_client(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "run"
            failed_request = DciRunRequest(
                run_id="run-1", question="question", cwd=root
            )
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, failed_request, output_dir=output_dir)
            state_path = output_dir / "state.json"
            state = json.loads(state_path.read_text())
            state["conversation_features"]["strip_usage"] = 1
            state_path.write_text(json.dumps(state), encoding="utf-8")
            state_before_resume = state_path.read_text()
            protocol_before_resume = {
                path.name: path.read_text()
                for path in (output_dir / "protocol").iterdir()
            }
            resumed = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                resume=True,
            )

            with patch("asterion.dci.run.PiRpcClient") as client:
                with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                    run_pi_research(paths, resumed, output_dir=output_dir)

            client.assert_not_called()
            self.assertEqual(state_path.read_text(), state_before_resume)
            self.assertEqual(
                {
                    path.name: path.read_text()
                    for path in (output_dir / "protocol").iterdir()
                },
                protocol_before_resume,
            )

    def test_production_path_records_complete_conversation_and_latest_context(
        self,
    ) -> None:
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
                [
                    "system",
                    "toolResult",
                    "toolResult",
                    "toolResult",
                    "toolResult",
                    "assistant",
                ],
            )
            self.assertEqual(
                full["messages"][0]["sources"],
                {
                    "system_prompt_file": str(system_prompt),
                    "append_system_prompt_file": str(append_prompt),
                },
            )
            self.assertIsNone(full["pending_message"])

    def test_runtime_context_request_reserves_extension_transport_flags(
        self,
    ) -> None:
        request = DciRunRequest(
            run_id="run-1",
            question="question",
            cwd=Path("/work"),
            runtime_context_level="level3",
            thinking_level="high",
        )

        self.assertEqual(_pi_extra_args(request), ("--thinking", "high"))
        for value in (
            "--extension /tmp/foreign.ts",
            "--dci-context-profile level0",
            "--dci-context-contract=fake",
        ):
            with self.subTest(value=value), self.assertRaisesRegex(
                ValueError, "reserved context extension argument"
            ):
                validate_dci_run_request(replace(request, extra_args=(value,)))

    def test_runtime_context_request_resolves_the_canonical_profile(self) -> None:
        request = DciRunRequest(
            run_id="run-1",
            question="question",
            cwd=Path("/work"),
            runtime_context_level="level3",
        )

        self.assertTrue(hasattr(request, "context_profile"))
        self.assertEqual(request.context_profile.name, "level3")

    def test_runtime_context_request_loads_packaged_extension_and_reads_entries(
        self,
    ) -> None:
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
                run_pi_research(paths, request)

        kwargs = FixturePiClient.last_kwargs
        self.assertEqual(kwargs["context_profile"], "level3")
        self.assertEqual(kwargs["context_contract"], "dci.context-profile/v1")
        extension_path = kwargs["extension_path"]
        self.assertIsInstance(extension_path, Path)
        self.assertEqual(extension_path.name, "dci-context-extension.ts")
        self.assertEqual(FixturePiClient.get_entries_calls, 1)

    def test_context_session_path_may_materialize_only_after_first_prompt(self) -> None:
        class LazySessionClient(FixturePiClient):
            session_file: Path | None = None

            def probe_protocol(self, **_: object) -> dict[str, object]:
                agent_dir = self.last_kwargs["agent_dir"]
                assert isinstance(agent_dir, Path)
                type(self).session_file = agent_dir / "sessions/lazy-session.jsonl"
                type(self).session_file.parent.mkdir(parents=True, exist_ok=True)
                return {
                    "sessionFile": str(type(self).session_file),
                    "sessionId": "lazy-session",
                    "isStreaming": False,
                    "isCompacting": False,
                    "messageCount": 0,
                    "pendingMessageCount": 0,
                }

            def prompt_and_wait(self, message: str, *, on_event, **kwargs: object) -> str:
                assert type(self).session_file is not None
                self.assert_session_missing_before_prompt()
                type(self).session_file.touch()
                return super().prompt_and_wait(message, on_event=on_event, **kwargs)

            @classmethod
            def assert_session_missing_before_prompt(cls) -> None:
                assert cls.session_file is not None
                if cls.session_file.exists():
                    raise AssertionError("session file materialized before prompt")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            request = DciRunRequest(
                run_id="lazy-session-run",
                question="question",
                cwd=root,
                runtime_context_level="level3",
                keep_session=True,
            )
            with patch("asterion.dci.run.PiRpcClient", LazySessionClient):
                result = run_pi_research(paths, request)

            state = json.loads((result.output_dir / "state.json").read_text())
            self.assertEqual(state["pi_context_session"]["session_id"], "lazy-session")
            self.assertTrue(LazySessionClient.session_file.is_file())

    def test_context_session_validation_rechecks_file_after_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            agent_dir = Path(temporary_directory).resolve() / "agent"
            agent_dir.mkdir()
            paths = replace(
                resolve_dci_paths(agent_dir.parent),
                pi=replace(resolve_dci_paths(agent_dir.parent).pi, agent_dir=agent_dir),
            )
            session_file = agent_dir / "sessions/lazy.jsonl"
            session_file.parent.mkdir()
            state = {"sessionFile": str(session_file), "sessionId": "lazy"}

            self.assertEqual(
                _validate_pi_context_session(state, paths, require_file=False),
                (session_file, "lazy"),
            )
            with self.assertRaisesRegex(RuntimeError, "session identity"):
                _validate_pi_context_session(state, paths, require_file=True)
            session_file.touch()
            self.assertEqual(
                _validate_pi_context_session(state, paths, require_file=True),
                (session_file, "lazy"),
            )

    def test_bounded_prelude_questions_share_one_pi_process(self) -> None:
        class SequenceClient(FixturePiClient):
            prompts: list[str] = []

            def prompt_and_wait(self, message: str, *, on_event, **kwargs: object) -> str:
                type(self).prompts.append(message)
                return super().prompt_and_wait(message, on_event=on_event, **kwargs)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            request = DciRunRequest(
                run_id="prompt-sequence",
                question="pressure",
                cwd=root,
                prelude_questions=("prelude",) * 12,
                runtime_context_level="level3",
                keep_session=True,
            )
            with patch("asterion.dci.run.PiRpcClient", SequenceClient):
                result = run_pi_research(paths, request)

            self.assertEqual(SequenceClient.prompts, ["prelude"] * 12 + ["pressure"])
            state = json.loads((result.output_dir / "state.json").read_text())
            self.assertEqual(state["prelude_question_count"], 12)
            self.assertEqual(len(state["prelude_questions_fingerprint"]), 64)

    def test_cancellation_between_preludes_never_sends_the_next_prompt(self) -> None:
        cancelled = threading.Event()

        class CancellingSequenceClient(FixturePiClient):
            prompts: list[str] = []

            def prompt_and_wait(self, message: str, *, on_event, **kwargs: object) -> str:
                type(self).prompts.append(message)
                answer = super().prompt_and_wait(message, on_event=on_event, **kwargs)
                cancelled.set()
                return answer

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            request = DciRunRequest(
                run_id="cancel-prompt-sequence",
                question="pressure",
                cwd=root,
                prelude_questions=("first", "must-not-send"),
                runtime_context_level="level3",
                keep_session=True,
            )
            with (
                patch("asterion.dci.run.PiRpcClient", CancellingSequenceClient),
                self.assertRaisesRegex(DciRunError, "execution failed"),
            ):
                run_pi_research(
                    resolve_dci_paths(root), request, _cancel_event=cancelled
                )

        self.assertEqual(CancellingSequenceClient.prompts, ["first"])

    def test_runtime_context_request_rejects_unknown_profile(self) -> None:
        request = DciRunRequest(
            run_id="run-1",
            question="question",
            cwd=Path("/work"),
            runtime_context_level="level5",
        )

        with self.assertRaisesRegex(ValueError, "context profile"):
            validate_dci_run_request(request)

    def test_runtime_context_request_persists_effective_private_policy_evidence(
        self,
    ) -> None:
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
            policy_path = result.output_dir / "context-policy.json"
            policy = json.loads(policy_path.read_text())
            policy_mode = policy_path.stat().st_mode & 0o777

        control = state["runtime_context_control"]
        self.assertEqual(control["schema"], "dci.context-policy-identity/v1")
        self.assertEqual(control["status"], "effective")
        self.assertEqual(control["profile"], request.context_profile.identity_payload())
        self.assertRegex(control["extension_sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(control["extension_version"], "0.2.0")
        self.assertEqual(policy["schema"], "dci.context-policy-evidence/v2")
        self.assertEqual(policy["profile"], request.context_profile.identity_payload())
        self.assertEqual(policy["extension_sha256"], control["extension_sha256"])
        self.assertEqual(len(policy["attempts"]), 1)
        self.assertEqual(policy["attempts"][0]["attempt"], 1)
        self.assertEqual(policy["attempts"][0]["status"], "completed")
        self.assertEqual(len(policy["attempts"][0]["telemetry"]), 1)
        self.assertEqual(
            policy["attempts"][0]["latest_state"]["schema"],
            "dci.context-state/v2",
        )
        summary = state["context_policy"]["public_summary"]
        self.assertEqual(summary["profile"], "level3")
        self.assertEqual(summary["truncated_results"], 0)
        self.assertEqual(summary["compactions"], 0)
        self.assertEqual(policy_mode, 0o600)
        self.assertNotIn("question", json.dumps(policy))
        self.assertNotIn("answer", json.dumps(policy))

    def test_runtime_context_missing_entries_fails_before_success_finalization(
        self,
    ) -> None:
        class MissingEntriesClient(FixturePiClient):
            def get_entries(self) -> tuple[dict[str, object], ...]:
                return ()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            request = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                runtime_context_level="level3",
            )
            with patch("asterion.dci.run.PiRpcClient", MissingEntriesClient):
                with self.assertRaisesRegex(DciRunError, "Pi execution failed"):
                    run_pi_research(paths, request)
            state = json.loads((paths.output_root / "run-1/state.json").read_text())

        self.assertEqual(state["status"], "failed")
        self.assertEqual(state["context_policy"]["public_summary"], None)

    def test_resume_rejects_tampered_context_identity_before_client(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output = root / "run"
            request = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                runtime_context_level="level3",
                keep_session=True,
            )
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, request, output_dir=output)
            state_path = output / "state.json"
            state = json.loads(state_path.read_text())
            state["runtime_context_control"]["extension_sha256"] = "0" * 64
            state_path.write_text(json.dumps(state))
            resumed = replace(request, resume=True)

            with patch("asterion.dci.run.PiRpcClient") as client:
                with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                    run_pi_research(paths, resumed, output_dir=output)
            client.assert_not_called()

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

    def test_resume_reuses_failed_directory_and_creates_a_second_protocol_attempt(
        self,
    ) -> None:
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
            self.assertTrue(
                (output_dir / "protocol/attempt-0002.request.json").is_file()
            )
            self.assertEqual(
                json.loads((output_dir / "state.json").read_text())["resume_count"], 1
            )
            stderr_text = (output_dir / "stderr.txt").read_text(encoding="utf-8")
            self.assertIn("attempt-0001 status=failed", stderr_text)
            self.assertIn("attempt-0002 status=completed", stderr_text)
            self.assertIn("failure stderr", stderr_text)
            self.assertIn("private stderr", stderr_text)
            self.assertLess(
                stderr_text.index("failure stderr"), stderr_text.index("private stderr")
            )

    def test_resume_rejects_completed_or_changed_immutable_inputs_before_client_start(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "run"
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                run_pi_research(paths, request, output_dir=output_dir)

            completed = DciRunRequest(
                run_id="run-1", question="question", cwd=root, resume=True
            )
            with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                run_pi_research(paths, completed, output_dir=output_dir)

            failed_dir = root / "failed"
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, request, output_dir=failed_dir)
            changed = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                model="different",
                resume=True,
            )
            with patch("asterion.dci.run.PiRpcClient") as client:
                with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                    run_pi_research(paths, changed, output_dir=failed_dir)
            client.assert_not_called()

    def test_resume_reconstructs_and_validates_runtime_controls_before_client_start(
        self,
    ) -> None:
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

    def test_context_policy_resume_keeps_independent_attempt_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "failed"
            request = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                runtime_context_level="level4",
                keep_session=True,
            )
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, request, output_dir=output_dir)
            resumed = resume_request_from_output_dir(output_dir)
            self.assertEqual(resumed.pi_session_id, "session-fixture")
            self.assertEqual(
                resumed.pi_session_file,
                paths.pi.agent_dir / "sessions/session-fixture.jsonl",
            )
            with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                run_pi_research(paths, resumed, output_dir=output_dir)
            policy = json.loads((output_dir / "context-policy.json").read_text())

        self.assertEqual(
            [attempt["status"] for attempt in policy["attempts"]],
            ["failed", "completed"],
        )
        self.assertEqual(
            [attempt["attempt"] for attempt in policy["attempts"]], [1, 2]
        )
        self.assertTrue(
            all(attempt["latest_state"] is not None for attempt in policy["attempts"])
        )
        self.assertTrue(
            all(attempt["entries"] for attempt in policy["attempts"])
        )
        self.assertEqual(FixturePiClient.last_since, "entry-2")
        self.assertEqual(
            FixturePiClient.last_kwargs["session_file"],
            paths.pi.agent_dir / "sessions/session-fixture.jsonl",
        )

    def test_completed_run_writes_native_artifacts_and_protocol_projection(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                result = run_pi_research(paths, request)

            self.assertEqual(result.final_text, "answer")
            self.assertEqual(
                (result.output_dir / "question.txt").read_text(), "question\n"
            )
            self.assertTrue((result.output_dir / "events.jsonl").is_file())
            self.assertEqual((result.output_dir / "final.txt").read_text(), "answer\n")
            self.assertTrue((result.output_dir / "state.json").is_file())
            self.assertEqual(
                [event.type for event in result.events][-2:],
                ["artifact.created", "run.completed"],
            )
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
                    "timeout_seconds",
                    "runtime_context_level",
                    "thinking_level",
                    "node_max_old_space_size_mb",
                    "keep_session",
                    "extra_args_count",
                    "extra_args_fingerprint",
                    "show_tools",
                    "system_prompt_file",
                    "append_system_prompt_file",
                    "stream_text",
                    "conversation_features",
                    "pi_package_dir",
                    "pi_agent_dir",
                    "resume_count",
                }.issubset(state)
            )
            self.assertTrue(
                (result.output_dir / "protocol/attempt-0001.request.json").is_file()
            )
            self.assertTrue(
                (result.output_dir / "protocol/attempt-0001.events.jsonl").is_file()
            )
            protocol_events = [
                json.loads(line)
                for line in (result.output_dir / "protocol/attempt-0001.events.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            artifact = next(
                event["payload"]["artifact"]
                for event in protocol_events
                if event["type"] == "artifact.created"
            )
            self.assertEqual(
                artifact["sha256"],
                hashlib.sha256(
                    (result.output_dir / "final.txt").read_bytes()
                ).hexdigest(),
            )

    def test_attempt_provenance_warning_and_command_summary_never_store_credentials(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repo = root / "pi"
            package_dir = repo / "packages/coding-agent"
            package_dir.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(
                ["git", "config", "user.email", "fixture@example.invalid"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Fixture"], cwd=repo, check=True
            )
            (package_dir / "marker.txt").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
            actual_revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            sentinels = (
                "sentinel-user",
                "sentinel-pass",
                "sentinel-query",
                "sentinel-fragment",
                "sentinel-extra-value",
            )
            origin = (
                "https://sentinel-user:sentinel-pass@example.invalid/repo.git"
                "?token=sentinel-query#sentinel-fragment"
            )
            subprocess.run(
                ["git", "remote", "add", "origin", origin], cwd=repo, check=True
            )
            (root / "pi-revision.txt").write_text(f"{'f' * 40}\n", encoding="utf-8")
            paths = resolve_dci_paths(root)
            request = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                provider="provider",
                model="model",
                extra_args=("--custom sentinel-extra-value",),
            )
            warning_stream = io.StringIO()
            with patch.dict(os.environ, {"DCI_PI_REVISION": ""}, clear=False):
                with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                    with redirect_stderr(warning_stream):
                        result = run_pi_research(paths, request)

            state = json.loads((result.output_dir / "state.json").read_text())
            full = json.loads(
                (result.output_dir / "conversation_full.json").read_text()
            )
            latest = json.loads(
                (result.output_dir / "latest_model_context.json").read_text()
            )
            for artifact in (state, full, latest):
                self.assertEqual(
                    artifact["pi_source_attempts"][0]["commit"], actual_revision
                )
                self.assertFalse(artifact["pi_source_attempts"][0]["expected_match"])
            self.assertEqual(
                state["attempts"][0]["command_summary"],
                {
                    "executable": "node",
                    "mode": "rpc",
                    "option_names": [
                        "--mode",
                        "--provider",
                        "--model",
                        "--tools",
                        "--no-session",
                    ],
                    "configured_extra_argument_groups": 1,
                    "typed_extra_argument_count": 0,
                },
            )
            all_surfaces = warning_stream.getvalue()
            for path in result.output_dir.rglob("*"):
                if path.is_file():
                    all_surfaces += path.read_text(encoding="utf-8")
            for sentinel in sentinels:
                self.assertNotIn(sentinel, all_surfaces)
            self.assertIn("Pi source warning", warning_stream.getvalue())

    def test_local_origin_path_sentinels_are_absent_from_every_run_surface(
        self,
    ) -> None:
        local_origins = (
            "file:///sentinel-file-absolute/pi.git",
            "file://localhost/sentinel-file-localhost/pi.git",
            "/sentinel-local-absolute/pi.git",
            "../sentinel-local-relative/pi.git",
            r"C:\sentinel-local-windows\pi.git",
            "localhost:/sentinel-local-scp/pi.git",
            "http://127.1/sentinel-loopback-short/pi.git",
            "ssh://127.0.1/sentinel-loopback-dotted/pi.git",
            "git://2130706433/sentinel-loopback-integer/pi.git",
            "http://0x7f000001/sentinel-loopback-hex/pi.git",
            "ssh://017700000001/sentinel-loopback-octal/pi.git",
            "127.1:sentinel-loopback-scp-short/pi.git",
            "git@2130706433:sentinel-loopback-scp-integer/pi.git",
            "http://0xfffffffff/sentinel-overflow-hex/pi.git",
            "http://4294967296/sentinel-overflow-decimal/pi.git",
            "http://0x100000000/sentinel-overflow-hex-boundary/pi.git",
            "http://1.2.3.4.5/sentinel-excess-components/pi.git",
            "http://256.1.1.1/sentinel-four-part-overflow/pi.git",
            "http://1.16777216/sentinel-two-part-overflow/pi.git",
            "http://1.2.65536/sentinel-three-part-overflow/pi.git",
            "http://0/sentinel-zero-single/pi.git",
            "ssh://0.0.0.0/sentinel-zero-dotted/pi.git",
            "git://00/sentinel-zero-octal/pi.git",
            "http://0x0/sentinel-zero-hex/pi.git",
            "ssh://[::]/sentinel-zero-ipv6/pi.git",
            "0:sentinel-zero-scp/pi.git",
            "git@0.0.0.0:sentinel-zero-scp-dotted/pi.git",
            "git@[::]:sentinel-zero-scp-ipv6/pi.git",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repo = root / "pi"
            package_dir = repo / "packages/coding-agent"
            package_dir.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(
                ["git", "config", "user.email", "fixture@example.invalid"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Fixture"], cwd=repo, check=True
            )
            (package_dir / "marker.txt").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            (root / "pi-revision.txt").write_text(f"{revision}\n", encoding="utf-8")
            subprocess.run(
                ["git", "remote", "add", "origin", "https://example.invalid/repo.git"],
                cwd=repo,
                check=True,
            )
            paths = resolve_dci_paths(root)

            for index, origin in enumerate(local_origins):
                with self.subTest(origin=origin):
                    subprocess.run(
                        ["git", "remote", "set-url", "origin", origin],
                        cwd=repo,
                        check=True,
                    )
                    warning_stream = io.StringIO()
                    with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                        with redirect_stderr(warning_stream):
                            result = run_pi_research(
                                paths,
                                DciRunRequest(
                                    run_id=f"local-origin-{index}",
                                    question="question",
                                    cwd=root,
                                ),
                            )
                    surfaces = warning_stream.getvalue()
                    for artifact_path in result.output_dir.rglob("*"):
                        if artifact_path.is_file():
                            surfaces += artifact_path.read_text(encoding="utf-8")
                    self.assertNotIn("sentinel", surfaces.lower())
                    state = json.loads((result.output_dir / "state.json").read_text())
                    self.assertIsNone(state["pi_source_attempts"][0]["origin"])

    def test_rejects_a_nonempty_output_and_keeps_failure_detail_out_of_error(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            output_dir = root / "existing"
            output_dir.mkdir()
            (output_dir / "old.txt").write_text("old")
            with self.assertRaisesRegex(DciRunError, "output directory is not empty"):
                run_pi_research(paths, request, output_dir=output_dir)

            failing_request = DciRunRequest(
                run_id="run-2", question="question", cwd=root
            )
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaisesRegex(
                    DciRunError, "DCI Pi execution failed"
                ) as caught:
                    run_pi_research(paths, failing_request)

        self.assertNotIn("provider response", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
