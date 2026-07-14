from __future__ import annotations

import json
import os
import socket
import stat
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from asterion.dci.artifacts import (
    DciConversationFeatures,
    DciRunLock,
    DciRunRecorder,
    atomic_write_json,
)
from asterion.dci.config import resolve_dci_paths
from asterion.dci.run import DciRunRequest
from asterion.runtime.protocol import validate_event_stream


def request(root: Path) -> DciRunRequest:
    return DciRunRequest(run_id="durable-run", question="question", cwd=root)


class AsterionDciArtifactTests(unittest.TestCase):
    def test_recorder_creates_private_run_directory_and_json_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "run"
            recorder = DciRunRecorder(
                output_dir=output_dir,
                request=request(root),
                paths=resolve_dci_paths(root),
            )
            recorder.finalize(status="failed")

            if os.name == "posix":
                self.assertEqual(stat.S_IMODE(output_dir.stat().st_mode), 0o700)
                self.assertEqual(stat.S_IMODE((output_dir / "state.json").stat().st_mode), 0o600)
                self.assertEqual(
                    stat.S_IMODE((output_dir / "conversation.json").stat().st_mode),
                    0o600,
                )

    def test_lock_rejects_output_directory_and_lock_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            real_output = root / "real"
            real_output.mkdir()
            linked_output = root / "linked"
            linked_output.symlink_to(real_output, target_is_directory=True)

            with self.assertRaises(RuntimeError):
                DciRunLock.acquire(linked_output)

            output_dir = root / "run"
            output_dir.mkdir()
            foreign = root / "foreign-lock"
            foreign.write_text("do not replace", encoding="utf-8")
            (output_dir / DciRunLock.LOCK_NAME).symlink_to(foreign)

            with self.assertRaises(RuntimeError):
                DciRunLock.acquire(output_dir)
            self.assertEqual(foreign.read_text(encoding="utf-8"), "do not replace")

    def test_two_concurrent_lock_acquisitions_allow_exactly_one_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            start = threading.Barrier(2)

            def contend() -> DciRunLock | None:
                start.wait()
                try:
                    return DciRunLock.acquire(output_dir)
                except RuntimeError:
                    return None

            with ThreadPoolExecutor(max_workers=2) as executor:
                owners = list(executor.map(lambda _: contend(), range(2)))

            acquired = [owner for owner in owners if owner is not None]
            self.assertEqual(len(acquired), 1)
            acquired[0].release()

    def test_same_host_dead_pid_lock_is_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            output_dir.mkdir(mode=0o700)
            lock_path = output_dir / DciRunLock.LOCK_NAME
            lock_path.write_text(
                json.dumps(
                    {
                        "pid": 999_999_999,
                        "hostname": socket.gethostname(),
                        "created_at": "2026-07-14T00:00:00+00:00",
                        "owner_token": "dead-owner",
                    }
                ),
                encoding="utf-8",
            )

            owner = DciRunLock.acquire(output_dir)
            self.addCleanup(owner.release)

            payload = json.loads(lock_path.read_text(encoding="utf-8"))
            self.assertNotEqual(payload["owner_token"], "dead-owner")
            self.assertEqual(payload["pid"], os.getpid())

    def test_foreign_and_malformed_locks_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for name, payload in (
                (
                    "foreign",
                    {
                        "pid": 999_999_999,
                        "hostname": "different.example",
                        "created_at": "2026-07-14T00:00:00+00:00",
                        "owner_token": "foreign-owner",
                    },
                ),
                ("malformed", {"pid": 999_999_999}),
            ):
                with self.subTest(name=name):
                    output_dir = root / name
                    output_dir.mkdir(mode=0o700)
                    lock_path = output_dir / DciRunLock.LOCK_NAME
                    original = json.dumps(payload)
                    lock_path.write_text(original, encoding="utf-8")

                    with self.assertRaises(RuntimeError):
                        DciRunLock.acquire(output_dir)
                    self.assertEqual(lock_path.read_text(encoding="utf-8"), original)

    def test_release_removes_only_the_matching_owner_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            owner = DciRunLock.acquire(output_dir)
            lock_path = output_dir / DciRunLock.LOCK_NAME
            replacement = json.loads(lock_path.read_text(encoding="utf-8"))
            replacement["owner_token"] = "replacement-owner"
            lock_path.write_text(json.dumps(replacement), encoding="utf-8")

            owner.release()

            self.assertTrue(lock_path.is_file())
            self.assertEqual(
                json.loads(lock_path.read_text(encoding="utf-8"))["owner_token"],
                "replacement-owner",
            )

    def test_atomic_json_failure_before_replace_preserves_previous_document(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "state.json"
            atomic_write_json(path, {"status": "previous"})

            with patch("asterion.dci.artifacts.os.replace", side_effect=OSError("fault")):
                with self.assertRaises(OSError):
                    atomic_write_json(path, {"status": "replacement"})

            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"status": "previous"})

    def test_resume_preserves_raw_events_and_creates_a_new_protocol_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "run"
            first = DciRunRecorder(
                output_dir=output_dir,
                request=request(root),
                paths=resolve_dci_paths(root),
            )
            first.record_event({"type": "agent_start"})
            first.finalize(status="failed")
            prior_events = (output_dir / "events.jsonl").read_text(encoding="utf-8")

            resumed = DciRunRecorder(
                output_dir=output_dir,
                request=request(root),
                paths=resolve_dci_paths(root),
                resume=True,
            )
            resumed.record_event({"type": "agent_end"})
            resumed.finalize(status="failed")

            events = (output_dir / "events.jsonl").read_text(encoding="utf-8")
            self.assertTrue(events.startswith(prior_events))
            self.assertTrue((output_dir / "protocol/attempt-0002.request.json").is_file())
            self.assertEqual(json.loads((output_dir / "state.json").read_text())["resume_count"], 1)

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
