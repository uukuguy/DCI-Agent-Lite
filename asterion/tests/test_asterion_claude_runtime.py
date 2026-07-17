from __future__ import annotations

import subprocess
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from asterion.runtime.host import RunRequest
from asterion.runtime.protocol import validate_event_stream
from asterion.runtime.protocol import ProtocolError
from asterion.runtimes.claude_code import ClaudeCodeRuntimeClient


FIXTURE = Path(__file__).parent / "fixtures/claude_code/valid-success.jsonl"


class Cancelled:
    cancelled = True


class ClaudeCodeRuntimeClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_persistent_evidence_is_private_and_resolvable_after_completion(self) -> None:
        process = Mock(
            return_value=subprocess.CompletedProcess([], 0, FIXTURE.read_text(), "")
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "private"
            runtime = ClaudeCodeRuntimeClient(
                executable="claude",
                cwd=Path(directory),
                environment={},
                evidence_root=root,
                run_process=process,
            )

            events = [
                event
                async for event in runtime.run(RunRequest("persistent-run", "question"))
            ]
            run_dir = runtime.completed_run_dir("persistent-run")

            self.assertIsNotNone(run_dir)
            assert run_dir is not None
            self.assertEqual(stat.S_IMODE(run_dir.stat().st_mode), 0o700)
            self.assertEqual((run_dir / "final.txt").read_text(), "OK\n")
            self.assertTrue(all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in run_dir.iterdir()))
            self.assertEqual(events[-1].type, "run.completed")

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
        self.assertEqual(
            runtime.manifest.capabilities,
            ("claude.tool.glob", "claude.tool.grep", "filesystem.read"),
        )
        command = process.call_args.args[0]
        self.assertIn("Read,Grep,Glob", command)
        self.assertNotIn("Bash", command)
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

    async def test_deadline_failure_is_redacted(self) -> None:
        process = Mock(side_effect=subprocess.TimeoutExpired(["claude"], 0.001))
        runtime = ClaudeCodeRuntimeClient(
            executable="claude",
            cwd=Path.cwd(),
            environment={},
            run_process=process,
        )

        with self.assertRaises(ProtocolError) as caught:
            await anext(
                runtime.run(
                    RunRequest(
                        "deadline-run", "SECRET-DEADLINE-INPUT", deadline_ms=1
                    )
                )
            )

        self.assertNotIn("SECRET", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
