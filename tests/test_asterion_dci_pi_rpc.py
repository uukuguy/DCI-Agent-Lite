from __future__ import annotations

import io
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from asterion.dci.pi_rpc import (
    PiRpcClient,
    build_pi_command,
    expand_extra_args,
    resolve_node_bin,
    run_pi_terminal,
)


def make_client(
    *,
    show_tools: bool = False,
    keep_session: bool = False,
    node_max_old_space_size_mb: int | None = None,
    extra_args: tuple[str, ...] = ("--thinking high",),
    literal_extra_args: tuple[str, ...] = (),
) -> PiRpcClient:
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
        extra_args=extra_args,
        literal_extra_args=literal_extra_args,
        keep_session=keep_session,
        node_max_old_space_size_mb=node_max_old_space_size_mb,
    )


class PiRpcCommandTests(unittest.TestCase):
    def test_node_resolution_accepts_path_node_20_before_nvm(self) -> None:
        with (
            patch("asterion.dci.pi_rpc.shutil.which", return_value="/path/node"),
            patch(
                "asterion.dci.pi_rpc.subprocess.run",
                return_value=subprocess.CompletedProcess(
                    ["/path/node", "--version"], 0, stdout="v20.19.1\n", stderr=""
                ),
            ) as run,
        ):
            self.assertEqual(resolve_node_bin({"PATH": "/path"}), "/path/node")

        run.assert_called_once_with(
            ["/path/node", "--version"],
            env={"PATH": "/path"},
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )

    def test_node_resolution_falls_back_to_highest_valid_nvm_node(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            nvm = Path(temporary_directory)
            old = nvm / "versions" / "node" / "v18.20.0" / "bin" / "node"
            current = nvm / "versions" / "node" / "v22.3.0" / "bin" / "node"
            old.parent.mkdir(parents=True)
            current.parent.mkdir(parents=True)
            old.touch()
            current.touch()
            old.chmod(0o755)
            current.chmod(0o755)
            with (
                patch("asterion.dci.pi_rpc.shutil.which", return_value="/path/node"),
                patch(
                    "asterion.dci.pi_rpc.subprocess.run",
                    side_effect=(
                        subprocess.CompletedProcess(
                            ["/path/node", "--version"],
                            0,
                            stdout="v18.20.0\n",
                            stderr="",
                        ),
                        subprocess.CompletedProcess(
                            [str(current), "--version"],
                            0,
                            stdout="v22.3.0\n",
                            stderr="",
                        ),
                    ),
                ),
            ):
                self.assertEqual(
                    resolve_node_bin({"PATH": "/path", "NVM_DIR": str(nvm)}),
                    str(current),
                )

    def test_node_resolution_rejects_missing_low_or_broken_node(self) -> None:
        cases = (
            (None, None),
            (
                "/path/node",
                subprocess.CompletedProcess([], 0, stdout="v19.9.0", stderr=""),
            ),
            ("/path/node", OSError("sentinel-secret")),
        )
        for found, probe in cases:
            with self.subTest(found=found, probe=type(probe).__name__):
                effect = probe if isinstance(probe, BaseException) else None
                result = None if effect is not None else probe
                with (
                    patch("asterion.dci.pi_rpc.shutil.which", return_value=found),
                    patch(
                        "asterion.dci.pi_rpc.subprocess.run",
                        return_value=result,
                        side_effect=effect,
                    ),
                    patch.dict(os.environ, {"NVM_DIR": "/does-not-exist"}, clear=True),
                ):
                    with self.assertRaisesRegex(
                        RuntimeError, "compatible Node runtime is unavailable"
                    ) as caught:
                        resolve_node_bin(dict(os.environ))
                self.assertNotIn("sentinel-secret", str(caught.exception))

    def test_terminal_uses_literal_argv_inherited_heap_and_exit_status(self) -> None:
        stdin = Mock(isatty=Mock(return_value=True))
        stdout = Mock(isatty=Mock(return_value=True))
        with (
            patch("asterion.dci.pi_rpc.resolve_node_bin", return_value="/node20"),
            patch(
                "asterion.dci.pi_rpc.ensure_built_pi_cli",
                return_value=Path("/pi/dist/cli.js"),
            ),
            patch(
                "asterion.dci.pi_rpc.subprocess.run",
                return_value=subprocess.CompletedProcess([], 17),
            ) as run,
            patch.dict(
                os.environ,
                {"PATH": "/bin", "NODE_OPTIONS": "--trace-warnings"},
                clear=True,
            ),
        ):
            status = run_pi_terminal(
                package_dir=Path("/pi"),
                cwd=Path("/corpus"),
                agent_dir=Path("/agent"),
                provider="provider; touch /tmp/no",
                model="model --tools bash",
                tools="read,bash",
                system_prompt_file=Path("/prompt with spaces.txt"),
                append_system_prompt_file=Path("/append.txt"),
                thinking_level="high --model injected",
                extra_args=("--custom value", "--second 'two words'"),
                node_max_old_space_size_mb=4096,
                initial_question="question; echo nope",
                stdin=stdin,
                stdout=stdout,
            )

        self.assertEqual(status, 17)
        command = run.call_args.args[0]
        self.assertEqual(command[:2], ["/node20", "/pi/dist/cli.js"])
        self.assertNotIn("--mode", command)
        self.assertNotIn("--no-session", command)
        self.assertEqual(command.count("--model"), 1)
        self.assertIn("model --tools bash", command)
        self.assertEqual(command[command.index("--second") + 1], "two words")
        self.assertEqual(command[-1], "question; echo nope")
        self.assertEqual(run.call_args.kwargs["cwd"], Path("/corpus"))
        self.assertEqual(run.call_args.kwargs["env"]["PI_CODING_AGENT_DIR"], "/agent")
        self.assertEqual(
            run.call_args.kwargs["env"]["NODE_OPTIONS"],
            "--trace-warnings --max-old-space-size=4096",
        )
        self.assertFalse(run.call_args.kwargs["check"])

    def test_terminal_rejects_non_tty_before_node_or_pi(self) -> None:
        for stdin_tty, stdout_tty in ((False, True), (True, False)):
            with self.subTest(stdin=stdin_tty, stdout=stdout_tty):
                stdin = Mock(isatty=Mock(return_value=stdin_tty))
                stdout = Mock(isatty=Mock(return_value=stdout_tty))
                with (
                    patch("asterion.dci.pi_rpc.resolve_node_bin") as node,
                    patch("asterion.dci.pi_rpc.ensure_built_pi_cli") as built,
                    self.assertRaisesRegex(
                        RuntimeError, "interactive stdin/stdout TTY"
                    ),
                ):
                    run_pi_terminal(
                        package_dir=Path("/pi"),
                        cwd=Path("/corpus"),
                        agent_dir=Path("/agent"),
                        provider=None,
                        model=None,
                        tools="read",
                        system_prompt_file=None,
                        append_system_prompt_file=None,
                        thinking_level=None,
                        extra_args=(),
                        node_max_old_space_size_mb=None,
                        initial_question=None,
                        stdin=stdin,
                        stdout=stdout,
                    )
                node.assert_not_called()
                built.assert_not_called()

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

        self.assertEqual(
            command[1:3], ["/pi/packages/coding-agent/dist/cli.js", "--mode"]
        )
        self.assertEqual(command[3], "rpc")
        self.assertEqual(command[-3:], ["--no-session", "--thinking", "high"])

    def test_client_maps_context_thinking_and_session_to_pi(self) -> None:
        client = make_client(
            keep_session=True,
            extra_args=("--thinking high",),
        )
        with patch("asterion.dci.pi_rpc.ensure_built_pi_cli") as built:
            built.return_value = Path("/pi/packages/coding-agent/dist/cli.js")
            command = client._build_command()

        self.assertNotIn("--no-session", command)
        self.assertEqual(
            command[-2:],
            ["--thinking", "high"],
        )

    def test_heap_option_preserves_existing_node_options(self) -> None:
        client = make_client(node_max_old_space_size_mb=8192)
        with patch.dict(os.environ, {"NODE_OPTIONS": "--trace-warnings"}, clear=True):
            environment = client._child_environment()

        self.assertEqual(
            environment["NODE_OPTIONS"],
            "--trace-warnings --max-old-space-size=8192",
        )

    def test_literal_runtime_controls_cannot_add_pi_flags(self) -> None:
        client = make_client(
            extra_args=("--custom value",),
            literal_extra_args=(
                "--thinking",
                "high --model unexpected",
                "--context-management-level",
                "level3 --tools shell",
            ),
        )
        with patch("asterion.dci.pi_rpc.ensure_built_pi_cli") as built:
            built.return_value = Path("/pi/packages/coding-agent/dist/cli.js")
            command = client._build_command()

        self.assertEqual(
            command[-6:],
            [
                "--custom",
                "value",
                "--thinking",
                "high --model unexpected",
                "--context-management-level",
                "level3 --tools shell",
            ],
        )
        self.assertEqual(command.count("--model"), 1)
        self.assertEqual(command.count("--tools"), 1)


class PiRpcLifecycleTests(unittest.TestCase):
    def test_waits_for_acknowledgement_and_idle_agent_settled_state(self) -> None:
        client = make_client()
        stdout = io.StringIO()
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
            patch("sys.stdout", new=stdout),
        ):
            result = client.prompt_and_wait("question", timeout_seconds=30)

        self.assertEqual(result, "answer")
        self.assertEqual(stdout.getvalue(), "answer")
        send.assert_called_once_with(
            {"id": "py-1", "type": "prompt", "message": "question"}
        )

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
            patch.object(
                client, "_read_json_line", side_effect=RuntimeError("invalid JSONL")
            ),
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
