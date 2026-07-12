"""Restricted non-interactive Claude Code protocol runtime."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
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
    command = [
        executable,
        "-p",
        "--safe-mode",
        "--no-session-persistence",
        "--output-format",
        "stream-json",
        "--include-partial-messages",
        "--verbose",
    ]
    if tools:
        joined = ",".join(tools)
        command.extend(["--tools", joined, "--allowedTools", joined])
    else:
        command.extend(["--tools", ""])
    return command


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def run_claude_code(
    *,
    prompt: str,
    output_dir: Path,
    cwd: Path,
    tools: list[str],
    timeout_seconds: float,
    executable: str = "claude",
    run_process: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> dict[str, Any]:
    """Run one Claude Code prompt and persist raw plus normalized artifacts."""

    output_dir.mkdir(parents=True, exist_ok=True)
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

    completed = run_process(
        build_claude_command(executable=executable, tools=tools),
        cwd=cwd,
        input=prompt,
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    (output_dir / "raw-events.jsonl").write_text(completed.stdout)
    (output_dir / "stderr.txt").write_text(completed.stderr)

    events: list[dict[str, object]] = []
    events_path = output_dir / "events.jsonl"

    def emit(event: dict[str, object]) -> None:
        events.append(event)
        with events_path.open("a") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    events_path.write_text("")
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
        (output_dir / "final.txt").write_text(final_text + ("\n" if final_text else ""))
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
