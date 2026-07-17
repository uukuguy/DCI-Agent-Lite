from __future__ import annotations

import json
import subprocess
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401
from dci.framework.protocol import validate_event_stream, validate_run_request
from dci.framework.runtimes.claude_code import build_claude_command, run_claude_code


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "asterion/tests/fixtures/claude_code/valid-success.jsonl"


class ClaudeCodeRuntimeTests(unittest.TestCase):
    def test_command_is_nonpersistent_restricted_and_never_bypasses_permissions(self) -> None:
        command = build_claude_command(
            executable="claude",
            tools=["Read", "Grep", "Glob"],
        )

        self.assertIn("--no-session-persistence", command)
        self.assertIn("--output-format", command)
        self.assertIn("stream-json", command)
        self.assertIn("--verbose", command)
        self.assertIn("--allowedTools", command)
        self.assertIn("dontAsk", command)
        self.assertIn("--strict-mcp-config", command)
        self.assertIn("--disable-slash-commands", command)
        self.assertNotIn("Bash", command)
        settings = json.loads(command[command.index("--settings") + 1])
        self.assertTrue(settings["sandbox"]["enabled"])
        self.assertTrue(settings["sandbox"]["failIfUnavailable"])
        self.assertFalse(settings["sandbox"]["allowUnsandboxedCommands"])
        self.assertEqual(settings["sandbox"]["filesystem"]["denyRead"], ["~/"])
        self.assertEqual(settings["sandbox"]["filesystem"]["allowRead"], ["."])
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
            policy = json.loads((output_dir / "runtime-policy.json").read_text())
            modes = [stat.S_IMODE(path.stat().st_mode) for path in output_dir.iterdir()]

        validate_run_request(request)
        validate_event_stream(events)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["final_text"], "OK")
        self.assertEqual(policy["permission_mode"], "dontAsk")
        self.assertTrue(all(mode == 0o600 for mode in modes))
        self.assertEqual(process.call_args.kwargs["input"], "Reply exactly OK.")

    def test_runtime_passes_anthropic_gateway_environment_without_persisting_it(
        self,
    ) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=FIXTURE.read_text(),
            stderr="",
        )
        process = Mock(return_value=completed)
        environment = {
            "PATH": "/test/bin",
            "ANTHROPIC_BASE_URL": "https://gateway.invalid",
            "ANTHROPIC_AUTH_TOKEN": "test-secret-token",
            "ANTHROPIC_MODEL": "gateway-model",
            "AWS_REGION": "us-test-1",
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run"
            result = run_claude_code(
                prompt="Reply exactly OK.",
                output_dir=output_dir,
                cwd=Path(temp_dir),
                tools=[],
                timeout_seconds=30,
                environment=environment,
                run_process=process,
            )
            persisted = "\n".join(
                path.read_text()
                for path in output_dir.iterdir()
                if path.is_file()
            )

        self.assertEqual(process.call_args.kwargs["env"], environment)
        self.assertNotIn("test-secret-token", persisted)
        self.assertNotIn("https://gateway.invalid", persisted)
        self.assertNotIn("gateway-model", persisted)
        self.assertNotIn("test-secret-token", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
