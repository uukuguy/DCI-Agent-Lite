from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from asterion.dci.artifacts import DciConversationFeatures, DciRunRecorder
from asterion.dci.config import resolve_dci_paths
from asterion.dci.run import DciRunRequest
from asterion.runtime.protocol import validate_event_stream


def request(root: Path) -> DciRunRequest:
    return DciRunRequest(run_id="durable-run", question="question", cwd=root)


class AsterionDciArtifactTests(unittest.TestCase):
    def test_recorder_writes_original_durable_artifact_set(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "run"
            recorder = DciRunRecorder(
                output_dir=output_dir,
                request=request(root),
                paths=resolve_dci_paths(root),
            )
            recorder.record_event(
                {
                    "type": "message_update",
                    "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
                }
            )
            events = recorder.finalize(status="completed", final_text="answer")

            self.assertTrue((output_dir / "conversation_full.json").is_file())
            self.assertTrue((output_dir / "conversation.json").is_file())
            self.assertTrue((output_dir / "latest_model_context.json").is_file())
            self.assertEqual((output_dir / "final.txt").read_text(), "answer\n")
            self.assertEqual(json.loads((output_dir / "state.json").read_text())["status"], "completed")
            validate_event_stream([event.to_mapping() for event in events])

    def test_processed_conversation_externalizes_and_clears_tool_result_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "run"
            recorder = DciRunRecorder(
                output_dir=output_dir,
                request=request(root),
                paths=resolve_dci_paths(root),
                features=DciConversationFeatures(
                    externalize_tool_results=True,
                    clear_tool_results=True,
                ),
            )
            recorder.record_event(
                {
                    "type": "message_end",
                    "message": {
                        "role": "toolResult",
                        "toolCallId": "call-1",
                        "content": [{"type": "text", "text": "SECRET-TOOL-BODY"}],
                    },
                }
            )
            recorder.finalize(status="failed")

            self.assertTrue((output_dir / "tool_results/call-1.json").is_file())
            self.assertNotIn(
                "SECRET-TOOL-BODY",
                (output_dir / "conversation.json").read_text(),
            )
            self.assertIn(
                "SECRET-TOOL-BODY",
                (output_dir / "conversation_full.json").read_text(),
            )


if __name__ == "__main__":
    unittest.main()
