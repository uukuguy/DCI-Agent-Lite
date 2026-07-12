from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from dci.framework.protocol import validate_event_stream, validate_run_request
from dci.framework.runtimes.claude_code import build_claude_command, run_claude_code


FIXTURE = Path(__file__).resolve().parent / "fixtures/claude_code/valid-success.jsonl"


class ClaudeCodeRuntimeTests(unittest.TestCase):
    def test_command_is_nonpersistent_restricted_and_never_bypasses_permissions(self) -> None:
        command = build_claude_command(
            executable="claude",
            tools=["Read", "Bash"],
        )

        self.assertIn("--no-session-persistence", command)
        self.assertIn("--output-format", command)
        self.assertIn("stream-json", command)
        self.assertIn("--verbose", command)
        self.assertIn("--allowedTools", command)
        self.assertNotIn("--dangerously-skip-permissions", command)

    def test_runtime_persists_raw_and_conformant_normalized_artifacts(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=FIXTURE.read_text(),
            stderr="",
        )
        process = Mock(return_value=completed)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run"
            result = run_claude_code(
                prompt="Reply exactly OK.",
                output_dir=output_dir,
                cwd=Path(temp_dir),
                tools=[],
                timeout_seconds=30,
                run_process=process,
            )
            request = json.loads((output_dir / "request.json").read_text())
            events = [
                json.loads(line)
                for line in (output_dir / "events.jsonl").read_text().splitlines()
            ]

        validate_run_request(request)
        validate_event_stream(events)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["final_text"], "OK")
        self.assertEqual(process.call_args.kwargs["input"], "Reply exactly OK.")


if __name__ == "__main__":
    unittest.main()
