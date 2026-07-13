from __future__ import annotations

import io
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.dci.pi_rpc import PiRpcClient, build_pi_command, expand_extra_args


def make_client(*, show_tools: bool = False) -> PiRpcClient:
    return PiRpcClient(
        package_dir=Path("pi/packages/coding-agent"),
        cwd=Path("."),
        agent_dir=Path("pi/.pi/agent"),
        provider="test-provider",
        model="test-model",
        tools="read,bash",
        show_tools=show_tools,
        system_prompt_file=None,
        append_system_prompt_file=None,
        extra_args=("--thinking high",),
    )


class PiRpcCommandTests(unittest.TestCase):
    def test_builds_direct_rpc_argv_and_expands_extra_args(self) -> None:
        with patch("asterion.dci.pi_rpc.ensure_built_pi_cli") as built:
            built.return_value = Path("/pi/packages/coding-agent/dist/cli.js")
            command = build_pi_command(
                package_dir=Path("/pi/packages/coding-agent"),
                mode="rpc",
                provider="provider",
                model="model",
                tools="read,bash",
                no_session=True,
                system_prompt_file=None,
                append_system_prompt_file=None,
                extra_args=expand_extra_args(("--thinking high",)),
            )

        self.assertEqual(command[1:3], ["/pi/packages/coding-agent/dist/cli.js", "--mode"])
        self.assertEqual(command[3], "rpc")
        self.assertEqual(command[-3:], ["--no-session", "--thinking", "high"])


class PiRpcLifecycleTests(unittest.TestCase):
    def test_waits_for_acknowledgement_and_idle_agent_settled_state(self) -> None:
        client = make_client()
        events = [
            {"type": "response", "id": "py-1", "success": True},
            {"type": "agent_start"},
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
            },
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
            patch("sys.stdout", new=io.StringIO()),
        ):
            result = client.prompt_and_wait("question", timeout_seconds=30)

        self.assertEqual(result, "answer")
        send.assert_called_once_with({"id": "py-1", "type": "prompt", "message": "question"})

    def test_retry_discards_partial_text_and_turn_limit_aborts_then_waits(self) -> None:
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
            {"type": "turn_start"},
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
            },
            {"type": "agent_end"},
        ]
        with (
            patch.object(client, "_send") as send,
            patch.object(client, "_read_json_line", side_effect=events),
            patch("sys.stdout", new=io.StringIO()),
            patch("sys.stderr", new=io.StringIO()),
        ):
            result = client.prompt_and_wait("question", max_turns=0, timeout_seconds=30)

        self.assertEqual(result, "answer")
        self.assertEqual(send.call_args_list[1].args[0]["type"], "abort")

    def test_timeout_sends_abort_and_malformed_jsonl_is_safe(self) -> None:
        client = make_client()
        with (
            patch.object(client, "_send") as send,
            patch.object(client, "_read_json_line", side_effect=TimeoutError),
        ):
            with self.assertRaisesRegex(RuntimeError, "timed out"):
                client.prompt_and_wait("question", timeout_seconds=0.001)
        self.assertEqual(send.call_args_list[-1].args[0]["type"], "abort")

        with (
            patch.object(client, "_send"),
            patch.object(client, "_read_json_line", side_effect=RuntimeError("invalid JSONL")),
        ):
            with self.assertRaisesRegex(RuntimeError, "invalid JSONL"):
                client.prompt_and_wait("question")

    def test_tool_boundaries_are_only_printed_to_stderr(self) -> None:
        client = make_client(show_tools=True)
        stdout = io.StringIO()
        stderr = io.StringIO()
        events = [
            {"type": "response", "id": "py-1", "success": True},
            {"type": "tool_execution_start", "toolName": "bash"},
            {"type": "tool_execution_end", "toolName": "bash", "isError": False},
            {"type": "agent_end"},
        ]
        with (
            patch.object(client, "_send"),
            patch.object(client, "_read_json_line", side_effect=events),
            patch("sys.stdout", new=stdout),
            patch("sys.stderr", new=stderr),
        ):
            client.prompt_and_wait("question")

        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("[tool:start] bash", stderr.getvalue())
        self.assertIn("[tool:end] bash error=no", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
