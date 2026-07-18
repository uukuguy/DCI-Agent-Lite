from __future__ import annotations

import io
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401
import dci.benchmark.pi_rpc_runner as rpc_runner
from dci.benchmark.pi_rpc_runner import PiRpcClient, parse_args
from dci.config import ConfigLayers
from dci.framework.protocol import validate_event_stream, validate_run_request
import scripts.bcplus_eval.run_bcplus_eval as bcplus_runner


def make_client() -> PiRpcClient:
    return PiRpcClient(
        package_dir=Path("pi/packages/coding-agent"),
        cwd=Path("."),
        agent_dir=Path("pi/.pi/agent"),
        provider="test-provider",
        model="test-model",
        tools="read,bash",
        no_session=True,
        show_tools=False,
        system_prompt_file=None,
        append_system_prompt_file=None,
        extra_args=[],
    )


def make_recorder(output_dir: Path, *, resume: bool = False) -> rpc_runner.RunRecorder:
    features = rpc_runner.ConversationFeatures(
        clear_tool_results=False,
        clear_tool_results_keep_last=3,
        externalize_tool_results=False,
        strip_thinking=False,
        strip_usage=False,
    )
    return rpc_runner.RunRecorder(
        output_dir=output_dir,
        question="question",
        package_dir=Path("pi/packages/coding-agent"),
        agent_dir=Path("pi/.pi/agent"),
        cwd=Path("."),
        provider="provider",
        model="model",
        tools="read,bash",
        max_turns=2,
        rpc_timeout_seconds=30,
        system_prompt_file=None,
        append_system_prompt_file=None,
        conversation_features=features,
        keep_session=False,
        resume=resume,
    )


class PiRpcLifecycleTests(unittest.TestCase):
    def test_run_recorder_writes_a_conformant_protocol_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run"
            with patch.object(
                rpc_runner,
                "collect_pi_source_provenance",
                return_value={"commit": "abc123", "dirty": False},
            ):
                recorder = make_recorder(output_dir)

            recorder.record_event(
                {
                    "type": "message_update",
                    "assistantMessageEvent": {
                        "type": "text_delta",
                        "delta": "answer",
                    },
                }
            )
            recorder.finalize(status="completed", final_text="answer")

            request_path = output_dir / "protocol/attempt-0001.request.json"
            events_path = output_dir / "protocol/attempt-0001.events.jsonl"
            request = json.loads(request_path.read_text())
            events = [json.loads(line) for line in events_path.read_text().splitlines()]

        validate_run_request(request)
        validate_event_stream(events)
        self.assertEqual(events[-2]["type"], "artifact.created")
        self.assertEqual(events[-1]["type"], "run.completed")
        self.assertEqual(recorder.state["protocol"]["events_jsonl"], str(events_path))

    def test_run_recorder_isolates_protocol_attempts_on_resume(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run"
            with patch.object(
                rpc_runner,
                "collect_pi_source_provenance",
                return_value={"commit": "abc123", "dirty": False},
            ):
                first = make_recorder(output_dir)
                first.finalize(status="failed", error="provider detail")
                second = make_recorder(output_dir, resume=True)
                second.finalize(status="failed", error="another detail")

            first_events_path = output_dir / "protocol/attempt-0001.events.jsonl"
            second_events_path = output_dir / "protocol/attempt-0002.events.jsonl"
            first_events = [
                json.loads(line) for line in first_events_path.read_text().splitlines()
            ]
            second_events = [
                json.loads(line) for line in second_events_path.read_text().splitlines()
            ]

        validate_event_stream(first_events)
        validate_event_stream(second_events)
        self.assertNotEqual(first_events[0]["run_id"], second_events[0]["run_id"])
        self.assertEqual(first_events[-1]["type"], "run.failed")
        self.assertEqual(second_events[-1]["type"], "run.failed")
        self.assertNotIn("provider detail", json.dumps(first_events))

    def test_pi_source_warning_reports_expected_revision_mismatch(self) -> None:
        formatter = getattr(rpc_runner, "format_pi_source_warning", None)
        self.assertIsNotNone(formatter)

        warning = formatter(
            {
                "commit": "actual",
                "expected_revision": "expected",
                "expected_revision_source": "pi-revision.txt",
                "expected_match": False,
            }
        )

        self.assertIn("actual", warning)
        self.assertIn("expected", warning)
        self.assertIsNone(formatter({"expected_match": True}))

    def test_pi_source_warning_is_emitted_and_added_to_run_notes(self) -> None:
        emitter = getattr(rpc_runner, "emit_pi_source_warning", None)
        self.assertIsNotNone(emitter)
        recorder = MagicMock()
        recorder.pi_source = {
            "commit": "actual",
            "expected_revision": "expected",
            "expected_revision_source": "pi-revision.txt",
            "expected_match": False,
        }
        stream = io.StringIO()

        warning = emitter(recorder, stream=stream)

        recorder.add_note.assert_called_once_with(warning)
        self.assertIn("WARNING", stream.getvalue())
    def test_run_artifacts_include_pi_source_provenance(self) -> None:
        provenance = {"commit": "abc123", "dirty": True, "lock_match": False}
        features = rpc_runner.ConversationFeatures(
            clear_tool_results=False,
            clear_tool_results_keep_last=3,
            externalize_tool_results=False,
            strip_thinking=False,
            strip_usage=False,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run"
            with patch.object(
                rpc_runner,
                "collect_pi_source_provenance",
                return_value=provenance,
            ):
                recorder = rpc_runner.RunRecorder(
                    output_dir=output_dir,
                    question="question",
                    package_dir=Path("pi/packages/coding-agent"),
                    agent_dir=Path("pi/.pi/agent"),
                    cwd=Path("."),
                    provider="provider",
                    model="model",
                    tools="read,bash",
                    max_turns=2,
                    rpc_timeout_seconds=30,
                    system_prompt_file=None,
                    append_system_prompt_file=None,
                    conversation_features=features,
                    keep_session=False,
                    resume=False,
                )

            self.assertEqual(recorder.state.get("pi_source"), provenance)
            self.assertEqual(
                recorder.conversation_full.get("pi_source"), provenance
            )
            self.assertEqual(
                recorder.latest_model_context.get("pi_source"), provenance
            )

    def test_pi_source_provenance_is_documented(self) -> None:
        artifacts_doc = Path("assets/docs/artifacts.md").read_text()

        self.assertIn("pi_source", artifacts_doc)
        self.assertIn("lock_match", artifacts_doc)
        self.assertIn("expected_revision", artifacts_doc)

    def test_pi_source_provenance_records_commit_lock_and_dirty_state(self) -> None:
        collect = getattr(rpc_runner, "collect_pi_source_provenance", None)
        self.assertIsNotNone(collect)
        with tempfile.TemporaryDirectory() as temp_dir:
            repo = Path(temp_dir) / "pi"
            package_dir = repo / "packages/coding-agent"
            package_dir.mkdir(parents=True)
            subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True)
            subprocess.run(
                ["git", "config", "user.name", "DCI Test"], cwd=repo, check=True
            )
            subprocess.run(
                ["git", "config", "user.email", "dci-test@example.invalid"],
                cwd=repo,
                check=True,
            )
            marker = package_dir / "marker.txt"
            marker.write_text("clean\n")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True)
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            lock_file = Path(temp_dir) / "pi-revision.txt"
            lock_file.write_text(f"{revision}\n")

            clean = collect(package_dir=package_dir, lock_file=lock_file)
            override = collect(
                package_dir=package_dir,
                lock_file=lock_file,
                revision_override=revision,
            )
            marker.write_text("dirty\n")
            dirty = collect(package_dir=package_dir, lock_file=lock_file)

        self.assertEqual(clean["commit"], revision)
        self.assertTrue(clean["lock_match"])
        self.assertFalse(clean["dirty"])
        self.assertTrue(override["expected_match"])
        self.assertEqual(override["expected_revision_source"], "DCI_PI_REVISION")
        self.assertTrue(dirty["dirty"])

    def test_protocol_probe_script_exposes_model_free_check(self) -> None:
        script = Path("scripts/check_pi_rpc.py")
        self.assertTrue(script.exists())

        result = subprocess.run(
            [sys.executable, str(script), "--help"],
            text=True,
            capture_output=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("model-free Pi RPC", result.stdout)

    def test_protocol_probe_is_documented_as_make_target(self) -> None:
        makefile = Path("Makefile").read_text()
        setup_doc = Path("assets/docs/setup.md").read_text()

        self.assertIn("check-pi-rpc:", makefile)
        self.assertIn("make check-pi-rpc", setup_doc)

    def test_protocol_probe_validates_get_state_shape(self) -> None:
        client = make_client()
        probe = getattr(client, "probe_protocol", None)
        self.assertIsNotNone(probe)
        state_response = {
            "type": "response",
            "id": "py-1",
            "command": "get_state",
            "success": True,
            "data": {
                "model": None,
                "isStreaming": False,
                "isCompacting": False,
                "messageCount": 0,
                "pendingMessageCount": 0,
            },
        }

        with (
            patch.object(client, "_send") as send,
            patch.object(client, "_read_json_line", return_value=state_response),
        ):
            state = probe(timeout_seconds=1)

        send.assert_called_once_with({"id": "py-1", "type": "get_state"})
        self.assertEqual(state["messageCount"], 0)
        self.assertFalse(state["isStreaming"])

    def test_waits_for_agent_settled(self) -> None:
        client = make_client()
        events = [
            {"type": "response", "id": "py-1", "success": True},
            {"type": "agent_start"},
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "first"},
            },
            {"type": "agent_end", "willRetry": False},
            {"type": "agent_start"},
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "final"},
            },
            {"type": "agent_end", "willRetry": False},
            {"type": "agent_settled"},
        ]

        with (
            patch.object(client, "_send") as send,
            patch.object(client, "_read_json_line", side_effect=events),
            patch.object(
                client,
                "probe_protocol",
                return_value={
                    "isStreaming": False,
                    "isCompacting": False,
                    "messageCount": 2,
                    "pendingMessageCount": 0,
                },
            ),
            patch("sys.stdout", new=io.StringIO()),
        ):
            result = client.prompt_and_wait("question", timeout_seconds=30)

        self.assertEqual(result, "final")
        send.assert_called_once_with({"id": "py-1", "type": "prompt", "message": "question"})

    def test_agent_settled_requires_an_idle_state_postcondition(self) -> None:
        client = make_client()
        events = [
            {"type": "response", "id": "py-1", "success": True},
            {"type": "agent_settled"},
        ]
        idle_state = {
            "isStreaming": False,
            "isCompacting": False,
            "messageCount": 1,
            "pendingMessageCount": 0,
        }

        with (
            patch.object(client, "_send"),
            patch.object(client, "_read_json_line", side_effect=events),
            patch.object(client, "probe_protocol", return_value=idle_state) as probe,
        ):
            client.prompt_and_wait("question", timeout_seconds=30)

        probe.assert_called_once()

    def test_agent_settled_rejects_non_idle_state(self) -> None:
        client = make_client()
        events = [
            {"type": "response", "id": "py-1", "success": True},
            {"type": "agent_settled"},
        ]
        active_state = {
            "isStreaming": False,
            "isCompacting": False,
            "messageCount": 1,
            "pendingMessageCount": 1,
        }

        with (
            patch.object(client, "_send"),
            patch.object(client, "_read_json_line", side_effect=events),
            patch.object(client, "probe_protocol", return_value=active_state),
        ):
            with self.assertRaisesRegex(RuntimeError, "not idle"):
                client.prompt_and_wait("question", timeout_seconds=30)

    def test_retry_discards_failed_run_text(self) -> None:
        client = make_client()
        events = [
            {"type": "response", "id": "py-1", "success": True},
            {"type": "agent_start"},
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "partial"},
            },
            {"type": "agent_end", "willRetry": True},
            {"type": "agent_start"},
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
            },
            {"type": "agent_end", "willRetry": False},
            {"type": "agent_settled"},
        ]

        with (
            patch.object(client, "_send"),
            patch.object(client, "_read_json_line", side_effect=events),
            patch.object(
                client,
                "probe_protocol",
                return_value={
                    "isStreaming": False,
                    "isCompacting": False,
                    "messageCount": 2,
                    "pendingMessageCount": 0,
                },
            ),
            patch("sys.stdout", new=io.StringIO()),
        ):
            result = client.prompt_and_wait("question", timeout_seconds=30)

        self.assertEqual(result, "answer")

    def test_legacy_agent_end_without_will_retry_is_supported(self) -> None:
        client = make_client()
        events = [
            {"type": "response", "id": "py-1", "success": True},
            {"type": "agent_start"},
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "legacy"},
            },
            {"type": "agent_end"},
        ]

        with (
            patch.object(client, "_send"),
            patch.object(client, "_read_json_line", side_effect=events),
            patch("sys.stdout", new=io.StringIO()),
        ):
            result = client.prompt_and_wait("question", timeout_seconds=30)

        self.assertEqual(result, "legacy")

    def test_timeout_sends_abort_and_raises(self) -> None:
        client = make_client()

        with (
            patch.object(client, "_send") as send,
            patch.object(client, "_read_json_line", side_effect=TimeoutError("timed out")),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out after 0.01 seconds"):
                client.prompt_and_wait("question", timeout_seconds=0.01)

        self.assertEqual(
            send.call_args_list,
            [
                call({"id": "py-1", "type": "prompt", "message": "question"}),
                call({"id": "py-2", "type": "abort"}),
            ],
        )

    def test_turn_limit_sends_abort_and_waits_until_settled(self) -> None:
        client = make_client()
        events = [
            {"type": "response", "id": "py-1", "success": True},
            {"type": "agent_start"},
            {"type": "turn_start"},
            {"type": "turn_start"},
            {"type": "agent_end", "willRetry": False},
            {"type": "agent_settled"},
        ]

        with (
            patch.object(client, "_send") as send,
            patch.object(client, "_read_json_line", side_effect=events),
            patch.object(
                client,
                "probe_protocol",
                return_value={
                    "isStreaming": False,
                    "isCompacting": False,
                    "messageCount": 1,
                    "pendingMessageCount": 0,
                },
            ),
            patch("sys.stderr", new=io.StringIO()),
        ):
            client.prompt_and_wait("question", max_turns=1, timeout_seconds=30)

        self.assertEqual(
            send.call_args_list,
            [
                call({"id": "py-1", "type": "prompt", "message": "question"}),
                call({"id": "py-2", "type": "abort"}),
            ],
        )

    def test_malformed_stdout_is_reported_as_protocol_error(self) -> None:
        client = make_client()
        client.proc = MagicMock()
        client.proc.stdout = io.BytesIO(b"not-json\n")

        client._drain_stdout()

        with self.assertRaisesRegex(RuntimeError, "Invalid JSONL from RPC process"):
            client._read_json_line(timeout_seconds=0)

    def test_child_exit_reports_return_code_and_stderr(self) -> None:
        client = make_client()
        client.proc = MagicMock()
        client.proc.stdout = io.BytesIO(b"")
        client.proc.poll.return_value = 17
        client.stderr_chunks.append("provider failed\n")

        client._drain_stdout()

        with self.assertRaisesRegex(
            RuntimeError,
            r"(?s)returncode=17.*provider failed",
        ):
            client._read_json_line(timeout_seconds=0)

    def test_layered_agent_values_remain_unresolved_until_runtime_resolution(self) -> None:
        environment = {
            "DCI_TOOLS": "read,grep",
            "DCI_MAX_TURNS": "7",
            "DCI_RPC_TIMEOUT_SECONDS": "42",
        }
        with (
            patch.dict("os.environ", environment, clear=True),
            patch("sys.argv", ["dci-agent-lite"]),
        ):
            args = parse_args()
        self.assertIsNone(args.tools)
        self.assertIsNone(args.max_turns)
        self.assertIsNone(args.rpc_timeout_seconds)

        resolved = rpc_runner.resolve_runtime_args(
            args, ConfigLayers(process=environment, dotenv={})
        )

        self.assertEqual(resolved.tools, "read,grep")
        self.assertEqual(resolved.max_turns, 7)
        self.assertEqual(resolved.timeout_seconds, 42.0)
        self.assertEqual(resolved.sources["agent.tools"], "environment")
        self.assertEqual(resolved.sources["agent.max_turns"], "environment")
        self.assertEqual(resolved.sources["agent.timeout_seconds"], "environment")

    def test_batch_parser_preserves_layered_agent_omission(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {
                    "DCI_TOOLS": "read,grep",
                    "DCI_MAX_TURNS": "7",
                    "DCI_RPC_TIMEOUT_SECONDS": "42",
                },
                clear=True,
            ),
            patch("sys.argv", ["run_bcplus_eval.py"]),
        ):
            args = bcplus_runner.parse_args()

        self.assertIsNone(args.tools)
        self.assertIsNone(args.max_turns)
        self.assertIsNone(args.rpc_timeout_seconds)

    def test_parser_leaves_layered_runtime_values_unresolved(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {"DCI_PROVIDER": "environment-provider", "DCI_MODEL": "environment-model"},
                clear=True,
            ),
            patch("sys.argv", ["dci-agent-lite", "--runtime", "pi"]),
        ):
            args = parse_args()

        self.assertEqual(args.runtime, "pi")
        self.assertIsNone(args.provider)
        self.assertIsNone(args.model)

    def test_runtime_defaults_do_not_make_terminal_flags_explicit(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("sys.argv", ["dci-agent-lite", "--terminal"]),
        ):
            args = parse_args()
        resolved = rpc_runner.resolve_runtime_args(args, ConfigLayers({}, {}))

        with (
            patch("sys.stdin.isatty", return_value=True),
            patch("sys.stdout.isatty", return_value=True),
        ):
            error = rpc_runner.validate_terminal_mode_args(args)

        self.assertIsNone(error)
        self.assertEqual(resolved.sources["agent.tools"], "runtime-default")
        self.assertEqual(resolved.sources["agent.max_turns"], "runtime-default")
        self.assertEqual(resolved.sources["agent.timeout_seconds"], "runtime-default")

    def test_runner_effective_config_rejects_sensitive_judge_endpoint(self) -> None:
        runtime = rpc_runner.resolve_original_runtime({}, ConfigLayers({}, {}))
        args = Namespace(cwd=Path("corpus"))
        judge = SimpleNamespace(
            endpoint="https://user:secret@judge.example/v1/chat/completions",
            api="chat-completions",
            model="judge-model",
            effective_thinking=None,
            json_mode=True,
        )

        with self.assertRaisesRegex(ValueError, "unsafe judge endpoint"):
            rpc_runner.effective_config_for_run(
                runtime=runtime, args=args, judge_config=judge
            )

    def test_batch_effective_config_rejects_sensitive_judge_endpoint(self) -> None:
        runtime = rpc_runner.resolve_original_runtime({}, ConfigLayers({}, {}))
        args = Namespace(
            dataset=Path("dataset.jsonl"),
            limit=1,
            corpus_dir=Path("corpus"),
            enable_ir=False,
        )
        judge = SimpleNamespace(
            endpoint="https://judge.example/v1/chat/completions?api_key=secret",
            api="chat-completions",
            model="judge-model",
            effective_thinking=None,
            json_mode=True,
        )

        with self.assertRaisesRegex(ValueError, "unsafe judge endpoint"):
            bcplus_runner.effective_config_for_batch(
                runtime=runtime, args=args, judge_config=judge
            )


if __name__ == "__main__":
    unittest.main()
