from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.dci.config import resolve_dci_paths
from asterion.dci.run import DciRunError, DciRunRequest, run_pi_research
from asterion.runtime.protocol import validate_event_stream


class FixturePiClient:
    events = [
        {"type": "response", "id": "py-1", "success": True},
        {
            "type": "message_update",
            "assistantMessageEvent": {"type": "text_delta", "delta": "answer"},
        },
        {"type": "agent_end"},
    ]

    def __init__(self, **_: object) -> None:
        self.stderr_chunks = ["private stderr"]

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def prompt_and_wait(self, _: str, *, on_event, **__: object) -> str:
        for event in self.events:
            on_event(event)
        return "answer"


class FailingPiClient(FixturePiClient):
    def prompt_and_wait(self, _: str, **__: object) -> str:
        raise RuntimeError("provider response and private stderr")


class AsterionDciRunTests(unittest.TestCase):
    def test_resume_reuses_failed_directory_and_creates_a_second_protocol_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "run"
            first = DciRunRequest(run_id="run-1", question="question", cwd=root)
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, first, output_dir=output_dir)
            resumed = DciRunRequest(
                run_id="run-1",
                question="question",
                cwd=root,
                resume=True,
            )
            with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                result = run_pi_research(paths, resumed, output_dir=output_dir)

            self.assertEqual(result.status, "completed")
            self.assertTrue((output_dir / "protocol/attempt-0002.request.json").is_file())
            self.assertEqual(json.loads((output_dir / "state.json").read_text())["resume_count"], 1)

    def test_resume_rejects_completed_or_changed_immutable_inputs_before_client_start(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            output_dir = root / "run"
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                run_pi_research(paths, request, output_dir=output_dir)

            completed = DciRunRequest(run_id="run-1", question="question", cwd=root, resume=True)
            with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                run_pi_research(paths, completed, output_dir=output_dir)

            failed_dir = root / "failed"
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaises(DciRunError):
                    run_pi_research(paths, request, output_dir=failed_dir)
            changed = DciRunRequest(
                run_id="run-1", question="question", cwd=root, model="different", resume=True
            )
            with patch("asterion.dci.run.PiRpcClient") as client:
                with self.assertRaisesRegex(DciRunError, "resume validation failed"):
                    run_pi_research(paths, changed, output_dir=failed_dir)
            client.assert_not_called()

    def test_completed_run_writes_native_artifacts_and_protocol_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            with patch("asterion.dci.run.PiRpcClient", FixturePiClient):
                result = run_pi_research(paths, request)

            self.assertEqual(result.final_text, "answer")
            self.assertEqual((result.output_dir / "question.txt").read_text(), "question\n")
            self.assertTrue((result.output_dir / "events.jsonl").is_file())
            self.assertEqual((result.output_dir / "final.txt").read_text(), "answer\n")
            self.assertTrue((result.output_dir / "state.json").is_file())
            self.assertEqual([event.type for event in result.events][-2:], ["artifact.created", "run.completed"])
            validate_event_stream([event.to_mapping() for event in result.events])
            state = json.loads((result.output_dir / "state.json").read_text())
            self.assertTrue(
                {
                    "run_id",
                    "status",
                    "question_path",
                    "final_path",
                    "events_path",
                    "stderr_path",
                    "question",
                    "cwd",
                    "provider",
                    "model",
                    "tools",
                    "max_turns",
                    "resume_count",
                }.issubset(state)
            )
            self.assertTrue((result.output_dir / "protocol/attempt-0001.request.json").is_file())
            self.assertTrue((result.output_dir / "protocol/attempt-0001.events.jsonl").is_file())

    def test_rejects_a_nonempty_output_and_keeps_failure_detail_out_of_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = resolve_dci_paths(root)
            request = DciRunRequest(run_id="run-1", question="question", cwd=root)
            output_dir = root / "existing"
            output_dir.mkdir()
            (output_dir / "old.txt").write_text("old")
            with self.assertRaisesRegex(DciRunError, "output directory is not empty"):
                run_pi_research(paths, request, output_dir=output_dir)

            failing_request = DciRunRequest(run_id="run-2", question="question", cwd=root)
            with patch("asterion.dci.run.PiRpcClient", FailingPiClient):
                with self.assertRaisesRegex(DciRunError, "DCI Pi execution failed") as caught:
                    run_pi_research(paths, failing_request)

        self.assertNotIn("provider response", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
