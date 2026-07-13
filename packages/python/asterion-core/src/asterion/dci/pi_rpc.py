"""Asterion-owned transport for one Pi JSONL-RPC research run."""

from __future__ import annotations

import json
import os
import queue
import shlex
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


_STDOUT_EOF = object()


def _node_bin() -> str:
    """Return the normal Node command; callers always use direct argv."""

    return "node"


def _node_env(base: Mapping[str, str]) -> dict[str, str]:
    """Copy the inherited environment for a direct Node child process."""

    return dict(base)


def ensure_built_pi_cli(package_dir: Path) -> Path:
    """Return Pi's built CLI, building its checkout only when required."""

    dist_cli = Path(package_dir) / "dist" / "cli.js"
    if dist_cli.exists():
        return dist_cli
    pi_repo_root = Path(package_dir).parents[1]
    subprocess.run(
        ["npm", "run", "build"],
        cwd=pi_repo_root,
        env=_node_env(os.environ),
        check=True,
    )
    if not dist_cli.exists():
        raise RuntimeError("Pi CLI build did not produce dist/cli.js")
    return dist_cli


def expand_extra_args(values: tuple[str, ...]) -> list[str]:
    """Split repeatable CLI arguments without ever involving a shell."""

    return [part for value in values for part in shlex.split(value)]


def build_pi_command(
    *,
    package_dir: Path,
    mode: str | None,
    provider: str | None,
    model: str | None,
    tools: str | None,
    no_session: bool,
    system_prompt_file: Path | None,
    append_system_prompt_file: Path | None,
    extra_args: list[str],
    messages: list[str] | None = None,
) -> list[str]:
    """Build the Pi command as a literal argv list."""

    command = [_node_bin(), str(ensure_built_pi_cli(package_dir))]
    if mode:
        command.extend(["--mode", mode])
    if provider:
        command.extend(["--provider", provider])
    if model:
        command.extend(["--model", model])
    if tools:
        command.extend(["--tools", tools])
    if system_prompt_file:
        command.extend(["--system-prompt", str(system_prompt_file)])
    if append_system_prompt_file:
        command.extend(["--append-system-prompt", str(append_system_prompt_file)])
    if no_session:
        command.append("--no-session")
    command.extend(extra_args)
    if messages:
        command.extend(messages)
    return command


class PiRpcClient:
    """Synchronous Pi JSONL-RPC lifecycle copied into the Asterion product boundary."""

    def __init__(
        self,
        *,
        package_dir: Path,
        cwd: Path,
        agent_dir: Path,
        provider: str | None,
        model: str | None,
        tools: str | None,
        show_tools: bool,
        system_prompt_file: Path | None,
        append_system_prompt_file: Path | None,
        extra_args: tuple[str, ...],
    ) -> None:
        self.package_dir = Path(package_dir)
        self.cwd = Path(cwd)
        self.agent_dir = Path(agent_dir)
        self.provider = provider
        self.model = model
        self.tools = tools
        self.show_tools = show_tools
        self.system_prompt_file = system_prompt_file
        self.append_system_prompt_file = append_system_prompt_file
        self.extra_args = tuple(extra_args)
        self.proc: subprocess.Popen[bytes] | None = None
        self.command: list[str] | None = None
        self.stderr_chunks: list[str] = []
        self._stdout_queue: queue.Queue[object] = queue.Queue()
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._request_id = 0

    def _build_command(self) -> list[str]:
        return build_pi_command(
            package_dir=self.package_dir,
            mode="rpc",
            provider=self.provider,
            model=self.model,
            tools=self.tools,
            no_session=True,
            system_prompt_file=self.system_prompt_file,
            append_system_prompt_file=self.append_system_prompt_file,
            extra_args=expand_extra_args(self.extra_args),
        )

    def start(self) -> None:
        if self.proc is not None:
            raise RuntimeError("RPC client already started")
        environment = _node_env(os.environ)
        environment["PI_CODING_AGENT_DIR"] = str(self.agent_dir)
        self.command = self._build_command()
        self.proc = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=environment,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._stdout_queue = queue.Queue()
        self._stdout_thread = threading.Thread(target=self._drain_stdout, daemon=True)
        self._stdout_thread.start()
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()

    def _drain_stdout(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        try:
            for raw in self.proc.stdout:
                try:
                    payload = json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    self._stdout_queue.put(RuntimeError("Pi RPC emitted invalid JSONL"))
                    return
                if not isinstance(payload, dict):
                    self._stdout_queue.put(RuntimeError("Pi RPC emitted a non-object JSON value"))
                    return
                self._stdout_queue.put(payload)
        finally:
            self._stdout_queue.put(_STDOUT_EOF)

    def _drain_stderr(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        for raw in self.proc.stderr:
            self.stderr_chunks.append(raw.decode("utf-8", errors="replace"))

    def stop(self) -> None:
        if self.proc is None:
            return
        process = self.proc
        try:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        finally:
            for thread in (self._stdout_thread, self._stderr_thread):
                if thread is not None:
                    thread.join(timeout=1)
            self._stdout_thread = None
            self._stderr_thread = None
            self.proc = None

    def _next_id(self) -> str:
        self._request_id += 1
        return f"py-{self._request_id}"

    def _send(self, payload: dict[str, Any]) -> None:
        if self.proc is None or self.proc.stdin is None:
            raise RuntimeError("RPC client is not running")
        self.proc.stdin.write((json.dumps(payload, separators=(",", ":")) + "\n").encode())
        self.proc.stdin.flush()

    def _read_json_line(self, *, timeout_seconds: float | None = None) -> dict[str, Any]:
        try:
            item = self._stdout_queue.get(timeout=timeout_seconds)
        except queue.Empty as error:
            raise TimeoutError("Timed out waiting for an RPC event") from error
        if item is _STDOUT_EOF:
            raise RuntimeError("Pi RPC process exited unexpectedly")
        if isinstance(item, BaseException):
            raise item
        if not isinstance(item, dict):
            raise RuntimeError("Pi RPC queue returned an invalid event")
        return item

    def probe_protocol(self, *, timeout_seconds: float = 10.0) -> dict[str, Any]:
        request_id = self._next_id()
        self._send({"id": request_id, "type": "get_state"})
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise RuntimeError("Pi RPC protocol probe timed out")
            response = self._read_json_line(timeout_seconds=remaining)
            if response.get("type") != "response" or response.get("id") != request_id:
                continue
            state = response.get("data")
            if response.get("success") is not True or not isinstance(state, dict):
                raise RuntimeError("Pi RPC get_state failed")
            for field, expected in {
                "isStreaming": bool,
                "isCompacting": bool,
                "messageCount": int,
                "pendingMessageCount": int,
            }.items():
                value = state.get(field)
                if not isinstance(value, expected) or (expected is int and isinstance(value, bool)):
                    raise RuntimeError("Pi RPC get_state shape is invalid")
            return state

    def prompt_and_wait(
        self,
        message: str,
        *,
        max_turns: int | None = None,
        timeout_seconds: float | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> str:
        request_id = self._next_id()
        self._send({"id": request_id, "type": "prompt", "message": message})
        text_parts: list[str] = []
        prompt_ack = False
        turns = 0
        sent_abort = False
        settled = False
        deadline = time.monotonic() + timeout_seconds if timeout_seconds and timeout_seconds > 0 else None
        while True:
            try:
                remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
                event = self._read_json_line(timeout_seconds=remaining)
            except TimeoutError as error:
                try:
                    self._send({"id": self._next_id(), "type": "abort"})
                except (BrokenPipeError, RuntimeError):
                    pass
                raise RuntimeError(f"RPC prompt timed out after {timeout_seconds:g} seconds") from error
            if on_event is not None:
                on_event(event)
            event_type = event.get("type")
            if event_type == "response":
                if event.get("id") == request_id:
                    if event.get("success") is not True:
                        raise RuntimeError("RPC prompt failed")
                    prompt_ack = True
                continue
            if event_type == "agent_start":
                text_parts = []
                continue
            if event_type == "turn_start":
                turns += 1
                if max_turns is not None and turns > max_turns and not sent_abort:
                    self._send({"id": self._next_id(), "type": "abort"})
                    sent_abort = True
                    print(f"[runner] Reached max_turns={max_turns}; sent RPC abort.", file=sys.stderr)
                continue
            if event_type == "message_update":
                assistant_event = event.get("assistantMessageEvent", {})
                if isinstance(assistant_event, Mapping) and assistant_event.get("type") == "text_delta":
                    delta = assistant_event.get("delta")
                    if isinstance(delta, str):
                        text_parts.append(delta)
                        print(delta, end="", file=sys.stdout, flush=True)
                continue
            if event_type == "tool_execution_start" and self.show_tools:
                print(f"[tool:start] {event.get('toolName', 'unknown')}", file=sys.stderr)
                continue
            if event_type == "tool_execution_end" and self.show_tools:
                error_state = "yes" if event.get("isError") else "no"
                print(f"[tool:end] {event.get('toolName', 'unknown')} error={error_state}", file=sys.stderr)
                continue
            if event_type == "agent_end":
                if not prompt_ack:
                    raise RuntimeError("Received agent_end before prompt acknowledgement")
                if "willRetry" not in event:
                    break
                continue
            if event_type == "agent_settled":
                if not prompt_ack:
                    raise RuntimeError("Received agent_settled before prompt acknowledgement")
                settled = True
                break
        if settled:
            state = self.probe_protocol(timeout_seconds=10.0)
            if state["isStreaming"] or state["isCompacting"] or state["pendingMessageCount"] != 0:
                raise RuntimeError("Pi RPC agent_settled postcondition failed: session is not idle")
        return "".join(text_parts)

    def get_stderr(self) -> str:
        return "".join(self.stderr_chunks)
