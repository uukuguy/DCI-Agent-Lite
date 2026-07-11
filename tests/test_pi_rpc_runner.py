from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

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
            patch("sys.stdout", new=io.StringIO()),
        ):
            result = client.prompt_and_wait("question", timeout_seconds=30)

        self.assertEqual(result, "final")
        send.assert_called_once_with({"id": "py-1", "type": "prompt", "message": "question"})

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
