from __future__ import annotations

import json
import unittest
from pathlib import Path

from tests import SOURCE_ROOT as _SOURCE_ROOT  # noqa: F401
from dci.framework.adapters.claude_code import ClaudeCodeProtocolAdapter
from dci.framework.protocol import validate_event_stream


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "asterion/tests/fixtures/claude_code"


def load_fixture(name: str) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in (FIXTURES / name).read_text().splitlines()
        if line.strip()
    ]


class ClaudeCodeProtocolAdapterTests(unittest.TestCase):
    def translate(self, name: str) -> list[dict[str, object]]:
        events: list[dict[str, object]] = []
        adapter = ClaudeCodeProtocolAdapter(run_id=f"claude-{name}", emit=events.append)
        for raw_event in load_fixture(name):
            adapter.consume(raw_event)
        validate_event_stream(events)
        return events

    def test_success_fixture_maps_text_usage_and_omits_thinking(self) -> None:
        events = self.translate("valid-success.jsonl")

        self.assertEqual(
            [event["type"] for event in events],
            [
                "run.started",
                "text.delta",
                "usage.reported",
                "artifact.created",
                "run.completed",
            ],
        )
        self.assertNotIn("hidden", json.dumps(events))

    def test_tool_fixture_maps_declared_capabilities_and_pairs_tools(self) -> None:
        events = self.translate("valid-tool.jsonl")

        self.assertEqual(
            events[0]["payload"],
            {"capabilities": ["filesystem.read", "shell"]},
        )
        self.assertEqual(
            [event["type"] for event in events].count("tool.call"), 1
        )
        self.assertEqual(
            [event["type"] for event in events].count("tool.result"), 1
        )

    def test_authentication_error_maps_to_safe_failure(self) -> None:
        events = self.translate("error-auth.jsonl")

        self.assertEqual(events[-1]["type"], "run.failed")
        serialized = json.dumps(events)
        self.assertNotIn("Not logged in", serialized)
        self.assertNotIn("authentication_failed", serialized)


if __name__ == "__main__":
    unittest.main()
