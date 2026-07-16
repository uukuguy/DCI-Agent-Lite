from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock

from asterion.runtime.host import RunRequest
from asterion.runtime.protocol import validate_event_stream
from asterion.runtimes.claude_code import ClaudeCodeRuntimeClient


FIXTURE = Path(__file__).parent / "fixtures/claude_code/valid-success.jsonl"


class Cancelled:
    cancelled = True


class ClaudeCodeRuntimeClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_projects_fixture_events_without_retaining_secret_environment(self) -> None:
        process = Mock(
            return_value=subprocess.CompletedProcess([], 0, FIXTURE.read_text(), "")
        )
        runtime = ClaudeCodeRuntimeClient(
            executable="claude",
            cwd=Path.cwd(),
            environment={"ANTHROPIC_AUTH_TOKEN": "SECRET"},
            run_process=process,
        )

        events = [
            event
            async for event in runtime.run(RunRequest("runtime-run", "SECRET-PROMPT"))
        ]

        self.assertEqual(runtime.manifest.runtime_id, "claude-code.reference")
        self.assertEqual(runtime.manifest.capabilities, ("filesystem.read", "shell"))
        self.assertEqual(process.call_args.kwargs["env"]["ANTHROPIC_AUTH_TOKEN"], "SECRET")
        self.assertNotIn("SECRET", repr(events))
        self.assertTrue(all(event.run_id == "runtime-run" for event in events))
        validate_event_stream([event.to_mapping() for event in events])

    async def test_pre_cancel_fails_before_starting_fixture_process(self) -> None:
        process = Mock()
        runtime = ClaudeCodeRuntimeClient(
            executable="claude",
            cwd=Path.cwd(),
            environment={},
            run_process=process,
        )

        with self.assertRaises(ValueError):
            await anext(runtime.run(RunRequest("runtime-run", "input"), signal=Cancelled()))
        process.assert_not_called()


if __name__ == "__main__":
    unittest.main()
