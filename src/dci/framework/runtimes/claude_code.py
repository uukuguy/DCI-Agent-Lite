"""Restricted non-interactive Claude Code protocol runtime."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from dci.framework.adapters.claude_code import (
    ClaudeCodeProtocolAdapter,
    map_claude_capabilities,
)
from dci.framework.protocol import (
    MAX_DEADLINE_MS,
    PROTOCOL_VERSION,
    validate_event_stream,
    validate_run_request,
)


def build_claude_command(*, executable: str, tools: list[str]) -> list[str]:
    settings = _restricted_settings()
    command = [
        executable,
        "-p",
        "--safe-mode",
        "--no-session-persistence",
        "--output-format",
        "stream-json",
        "--include-partial-messages",
        "--verbose",
        "--permission-mode",
        "dontAsk",
        "--strict-mcp-config",
        "--mcp-config",
        '{"mcpServers":{}}',
        "--disable-slash-commands",
        "--no-chrome",
        "--max-turns",
        "4",
        "--settings",
        json.dumps(settings, sort_keys=True, separators=(",", ":")),
    ]
    if tools:
        joined = ",".join(tools)
        command.extend(["--tools", joined, "--allowedTools", joined])
    else:
        command.extend(["--tools", ""])
    return command


def _restricted_settings() -> dict[str, object]:
    return {
        "permissions": {
            "defaultMode": "dontAsk",
            "deny": ["Read(/**)", "Grep(/**)", "Glob(/**)"],
        },
        "sandbox": {
            "enabled": True,
            "failIfUnavailable": True,
            "allowUnsandboxedCommands": False,
            "filesystem": {"denyRead": ["~/"], "allowRead": ["."]},
        },
    }


def _write_private(path: Path, value: str) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.write(descriptor, value.encode())
    finally:
        os.close(descriptor)
    path.chmod(0o600)


def _write_json(path: Path, payload: object) -> None:
    _write_private(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def run_claude_code(
    *,
    prompt: str,
    output_dir: Path,
    cwd: Path,
    tools: list[str],
    timeout_seconds: float,
    executable: str = "claude",
    environment: Mapping[str, str] | None = None,
    run_process: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Run one Claude Code prompt and persist raw plus normalized artifacts.

    Claude Code authentication, gateway, cloud-provider, and proxy settings stay
    on the subprocess environment boundary. They are never copied into the
    protocol request, normalized events, or returned status.
    """

    output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    output_dir.chmod(0o700)
    run_id = f"claude-{output_dir.name or 'run'}"
    request: dict[str, object] = {
        "protocol": PROTOCOL_VERSION,
        "run_id": run_id,
        "input": {"text": prompt},
        "requested_capabilities": map_claude_capabilities(tools),
    }
    if 0 < timeout_seconds * 1000 <= MAX_DEADLINE_MS:
        request["deadline_ms"] = max(1, int(round(timeout_seconds * 1000)))
    validate_run_request(request)
    _write_json(output_dir / "request.json", request)
    _write_json(
        output_dir / "runtime-policy.json",
        {
            "schema": "asterion.claude-code.restricted-policy/v1",
            "tools": tools,
            "allowed_tools": tools,
            "max_turns": 4,
            "permission_mode": "dontAsk",
            "strict_mcp": True,
            "mcp_servers": {},
            "safe_mode": True,
            "no_session_persistence": True,
            "settings": _restricted_settings(),
        },
    )

    process_environment = dict(os.environ if environment is None else environment)
    completed = run_process(
        build_claude_command(executable=executable, tools=tools),
        cwd=cwd,
        env=process_environment,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    _write_private(output_dir / "raw-events.jsonl", completed.stdout)
    _write_private(output_dir / "stderr.txt", completed.stderr)

    events: list[dict[str, object]] = []
    events_path = output_dir / "events.jsonl"

    def emit(event: dict[str, object]) -> None:
        events.append(event)
        descriptor = os.open(events_path, os.O_WRONLY | os.O_APPEND)
        try:
            os.write(descriptor, (json.dumps(event, ensure_ascii=False) + "\n").encode())
        finally:
            os.close(descriptor)

    _write_private(events_path, "")
    adapter = ClaudeCodeProtocolAdapter(run_id=run_id, emit=emit)
    final_text = ""
    try:
        for line_number, line in enumerate(completed.stdout.splitlines(), start=1):
            if not line.strip():
                continue
            raw_event = json.loads(line)
            if not isinstance(raw_event, dict):
                raise ValueError(f"stream line {line_number} is not an object")
            if raw_event.get("type") == "result" and isinstance(
                raw_event.get("result"), str
            ):
                final_text = raw_event["result"]
            adapter.consume(raw_event)
        if not adapter.started:
            adapter.consume({"type": "system", "subtype": "init", "tools": tools})
        if not adapter.terminal:
            adapter.fail()
    except (json.JSONDecodeError, ValueError):
        if not adapter.started:
            adapter.consume({"type": "system", "subtype": "init", "tools": tools})
        if not adapter.terminal:
            adapter.fail()

    validate_event_stream(events)
    if events[-1]["type"] == "run.completed":
        _write_private(output_dir / "final.txt", final_text + ("\n" if final_text else ""))
        status = "completed"
    else:
        final_text = ""
        status = "failed"
    return {
        "status": status,
        "returncode": completed.returncode,
        "final_text": final_text,
        "output_dir": str(output_dir),
    }
