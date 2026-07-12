from __future__ import annotations

import json
import unittest
from pathlib import Path

from dci.framework.protocol import (
    PROTOCOL_VERSION,
    ProtocolError,
    validate_event_stream,
    validate_run_request,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/agent_runtime/v1"


def load_jsonl(name: str) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (FIXTURE_DIR / name).read_text().splitlines()
        if line.strip()
    ]


class AgentRuntimeProtocolTests(unittest.TestCase):
    def test_valid_run_request_conforms(self) -> None:
        request = {
            "protocol": PROTOCOL_VERSION,
            "run_id": "run-123",
            "input": {"text": "Investigate the corpus"},
            "requested_capabilities": ["shell", "filesystem.read"],
            "deadline_ms": 300_000,
        }

        validate_run_request(request)

    def test_invalid_run_requests_are_rejected(self) -> None:
        valid = {
            "protocol": "dci.agent-runtime/v1",
            "run_id": "run-123",
            "input": {"text": "Investigate the corpus"},
        }
        invalid_requests = (
            {**valid, "protocol": "dci.agent-runtime/v2"},
            {**valid, "run_id": ""},
            {**valid, "input": {"text": ""}},
            {**valid, "requested_capabilities": ["shell", "shell"]},
            {**valid, "deadline_ms": 0},
            {**valid, "unknown": True},
        )

        for request in invalid_requests:
            with self.subTest(request=request), self.assertRaises(ProtocolError):
                validate_run_request(request)

    def test_valid_fixtures_conform(self) -> None:
        fixture_names = (
            "valid-research.jsonl",
            "valid-cancelled.jsonl",
            "valid-artifact.jsonl",
        )

        for fixture_name in fixture_names:
            with self.subTest(fixture=fixture_name):
                validate_event_stream(load_jsonl(fixture_name))

    def test_invalid_fixtures_are_rejected(self) -> None:
        fixture_names = (
            "invalid-sequence-gap.jsonl",
            "invalid-unmatched-tool-result.jsonl",
            "invalid-post-terminal.jsonl",
        )

        for fixture_name in fixture_names:
            with self.subTest(fixture=fixture_name), self.assertRaises(ProtocolError):
                validate_event_stream(load_jsonl(fixture_name))

    def test_stream_requires_started_and_one_terminal_event(self) -> None:
        no_started = [
            {
                "protocol": PROTOCOL_VERSION,
                "run_id": "run-1",
                "sequence": 1,
                "type": "run.completed",
                "payload": {"status": "completed"},
            }
        ]
        no_terminal = [
            {
                "protocol": PROTOCOL_VERSION,
                "run_id": "run-1",
                "sequence": 1,
                "type": "run.started",
                "payload": {"capabilities": []},
            }
        ]

        with self.assertRaises(ProtocolError):
            validate_event_stream(no_started)
        with self.assertRaises(ProtocolError):
            validate_event_stream(no_terminal)


if __name__ == "__main__":
    unittest.main()
