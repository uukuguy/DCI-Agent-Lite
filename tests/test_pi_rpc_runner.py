from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import dci.benchmark.pi_rpc_runner as rpc_runner
from dci.benchmark.pi_rpc_runner import PiRpcClient, parse_args


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


class PiRpcLifecycleTests(unittest.TestCase):
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

    def test_rpc_timeout_defaults_from_environment(self) -> None:
        with (
            patch.dict("os.environ", {"DCI_RPC_TIMEOUT_SECONDS": "42"}, clear=True),
            patch("sys.argv", ["dci-agent-lite"]),
        ):
            args = parse_args()

        self.assertEqual(args.rpc_timeout_seconds, 42.0)


if __name__ == "__main__":
    unittest.main()
