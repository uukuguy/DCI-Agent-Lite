from __future__ import annotations

import unittest

from dci.framework.adapters.pi import PiProtocolAdapter, map_pi_capabilities
from dci.framework.protocol import ProtocolError, validate_event_stream


class PiProtocolAdapterTests(unittest.TestCase):
    def test_pi_capabilities_map_conservatively_and_deduplicate(self) -> None:
        self.assertEqual(
            map_pi_capabilities("read,bash,edit,write,custom,read"),
            [
                "filesystem.read",
                "shell",
                "filesystem.write",
                "pi.tool.custom",
            ],
        )
        self.assertEqual(map_pi_capabilities(None), [])

    def test_stable_pi_events_map_to_a_conformant_stream(self) -> None:
        events: list[dict[str, object]] = []
        adapter = PiProtocolAdapter(
            run_id="pi-run-1",
            capabilities=["shell"],
            emit=events.append,
        )

        adapter.start()
        adapter.consume(
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "thinking_delta", "delta": "hidden"},
            }
        )
        adapter.consume(
            {
                "type": "message_update",
                "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
            }
        )
        adapter.consume(
            {
                "type": "tool_execution_start",
                "toolCallId": "call-1",
                "toolName": "bash",
                "args": {"command": "rg evidence corpus"},
            }
        )
        adapter.consume(
            {
                "type": "tool_execution_end",
                "toolCallId": "call-1",
                "result": "corpus/doc.txt:42:evidence",
                "isError": False,
            }
        )
        adapter.consume(
            {
                "type": "message_end",
                "message": {
                    "role": "assistant",
                    "usage": {"input": 100, "output": 20, "totalTokens": 120},
                },
            }
        )
        adapter.complete(
            artifact={
                "artifact_id": "final-answer",
                "kind": "answer",
                "media_type": "text/plain",
                "uri": "final.txt",
            }
        )

        validate_event_stream(events)
        self.assertEqual(
            [event["type"] for event in events],
            [
                "run.started",
                "text.delta",
                "tool.call",
                "tool.result",
                "usage.reported",
                "artifact.created",
                "run.completed",
            ],
        )
        self.assertEqual(
            [event["sequence"] for event in events],
            list(range(1, len(events) + 1)),
        )
        self.assertNotIn("hidden", repr(events))

    def test_failure_is_terminal_and_uses_safe_message(self) -> None:
        events: list[dict[str, object]] = []
        adapter = PiProtocolAdapter(
            run_id="pi-run-failed",
            capabilities=[],
            emit=events.append,
        )

        adapter.start()
        adapter.fail()

        validate_event_stream(events)
        self.assertEqual(events[-1]["type"], "run.failed")
        self.assertEqual(
            events[-1]["payload"],
            {
                "code": "pi_runtime_failed",
                "message": "Pi runtime failed; see the run stderr artifact.",
            },
        )

    def test_missing_tool_identity_is_protocol_drift(self) -> None:
        adapter = PiProtocolAdapter(
            run_id="pi-run-drift",
            capabilities=["shell"],
            emit=lambda event: None,
        )
        adapter.start()

        with self.assertRaises(ProtocolError):
            adapter.consume(
                {
                    "type": "tool_execution_start",
                    "toolCallId": "",
                    "toolName": "bash",
                    "args": {},
                }
            )

    def test_unmatched_tool_result_is_protocol_drift(self) -> None:
        adapter = PiProtocolAdapter(
            run_id="pi-run-unmatched",
            capabilities=["shell"],
            emit=lambda event: None,
        )
        adapter.start()

        with self.assertRaises(ProtocolError):
            adapter.consume(
                {
                    "type": "tool_execution_end",
                    "toolCallId": "missing-call",
                    "result": "none",
                    "isError": False,
                }
            )


if __name__ == "__main__":
    unittest.main()
