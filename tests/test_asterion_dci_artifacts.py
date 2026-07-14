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

import asterion.dci.artifacts as artifacts
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
    @staticmethod
    def _lock_payload(*, pid: int, owner_token: str) -> dict[str, object]:
        return {
            "pid": pid,
            "hostname": socket.gethostname(),
            "created_at": "2026-07-14T00:00:00+00:00",
            "owner_token": owner_token,
        }

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

    def test_release_does_not_unlink_a_replacement_raced_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            owner = DciRunLock.acquire(output_dir)
            lock_path = output_dir / DciRunLock.LOCK_NAME
            original_reader = artifacts._lock_payload
            replacement = self._lock_payload(pid=os.getpid(), owner_token="replacement-owner")

            def replace_after_read(path: Path) -> dict[str, object]:
                payload = original_reader(path)
                replacement_path = output_dir / ".replacement"
                replacement_path.write_text(json.dumps(replacement), encoding="utf-8")
                os.replace(replacement_path, lock_path)
                return payload

            with patch("asterion.dci.artifacts._lock_payload", side_effect=replace_after_read):
                owner.release()

            self.assertTrue(lock_path.is_file(), "release deleted the raced replacement lock")
            self.assertEqual(json.loads(lock_path.read_text(encoding="utf-8")), replacement)

    def test_stale_reclaim_does_not_unlink_a_replacement_raced_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            output_dir.mkdir(mode=0o700)
            lock_path = output_dir / DciRunLock.LOCK_NAME
            lock_path.write_text(
                json.dumps(self._lock_payload(pid=999_999_999, owner_token="dead-owner")),
                encoding="utf-8",
            )
            original_reader = artifacts._lock_payload
            replacement = self._lock_payload(pid=os.getpid(), owner_token="replacement-owner")
            read_count = 0

            def replace_on_removal_read(path: Path) -> dict[str, object]:
                nonlocal read_count
                payload = original_reader(path)
                read_count += 1
                if read_count == 2:
                    replacement_path = output_dir / ".replacement"
                    replacement_path.write_text(json.dumps(replacement), encoding="utf-8")
                    os.replace(replacement_path, lock_path)
                return payload

            with patch(
                "asterion.dci.artifacts._lock_payload",
                side_effect=replace_on_removal_read,
            ):
                with self.assertRaises(RuntimeError):
                    DciRunLock.acquire(output_dir)

            self.assertEqual(json.loads(lock_path.read_text(encoding="utf-8")), replacement)

    def test_acquisition_error_cleanup_preserves_a_changed_owner_token(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            real_dump = json.dump

            def change_token_then_fail(payload, handle, **kwargs) -> None:
                changed = dict(payload)
                changed["owner_token"] = "replacement-owner"
                real_dump(changed, handle, **kwargs)
                handle.flush()
                raise OSError("injected lock write failure")

            with patch("asterion.dci.artifacts.json.dump", side_effect=change_token_then_fail):
                with self.assertRaisesRegex(OSError, "injected lock write failure"):
                    DciRunLock.acquire(output_dir)

            lock_path = output_dir / DciRunLock.LOCK_NAME
            self.assertTrue(lock_path.is_file(), "cleanup deleted the changed-owner lock")
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

    def test_atomic_json_does_not_chmod_a_symlink_swapped_after_replace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            destination = root / "state.json"
            external = root / "external.txt"
            external.write_text("external", encoding="utf-8")
            os.chmod(external, 0o644)
            real_replace = os.replace

            def swap_after_replace(source: Path, target: Path) -> None:
                real_replace(source, target)
                Path(target).unlink()
                Path(target).symlink_to(external)

            with patch("asterion.dci.artifacts.os.replace", side_effect=swap_after_replace):
                atomic_write_json(destination, {"status": "new"})

            self.assertEqual(stat.S_IMODE(external.stat().st_mode), 0o644)

    def test_private_text_sets_mode_without_path_based_chmod(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "event.jsonl"

            with patch(
                "asterion.dci.artifacts.os.chmod",
                side_effect=AssertionError("path chmod is unsafe"),
            ):
                artifacts._write_private_text(destination, "{}\n")

            self.assertEqual(stat.S_IMODE(destination.stat().st_mode), 0o600)

    def test_record_event_failure_releases_the_recorder_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "run"
            recorder = DciRunRecorder(
                output_dir=output_dir,
                request=request(root),
                paths=resolve_dci_paths(root),
            )

            with patch(
                "asterion.dci.artifacts.atomic_write_json",
                side_effect=OSError("injected record failure"),
            ):
                with self.assertRaisesRegex(OSError, "injected record failure"):
                    recorder.record_event({"type": "agent_start"})

            try:
                next_owner = DciRunLock.acquire(output_dir)
            except RuntimeError as exc:
                self.fail(f"record_event failure stranded the recorder lock: {exc}")
            next_owner.release()

    def test_recorder_context_exit_and_close_release_idempotently(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "run"

            self.assertTrue(hasattr(DciRunRecorder, "__enter__"))
            self.assertTrue(hasattr(DciRunRecorder, "__exit__"))
            self.assertTrue(hasattr(DciRunRecorder, "close"))
            with self.assertRaisesRegex(ValueError, "boom"):
                with DciRunRecorder(
                    output_dir=output_dir,
                    request=request(root),
                    paths=resolve_dci_paths(root),
                ) as recorder:
                    raise ValueError("boom")
            recorder.close()

            next_owner = DciRunLock.acquire(output_dir)
            next_owner.release()

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
