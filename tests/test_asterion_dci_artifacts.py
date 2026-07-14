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

import fcntl

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

    def test_conversation_features_validate_and_round_trip(self) -> None:
        features = DciConversationFeatures(
            clear_tool_results=True,
            clear_tool_results_keep_last=2,
            externalize_tool_results=True,
            strip_thinking=True,
            strip_usage=True,
        )

        self.assertEqual(
            DciConversationFeatures.from_mapping(features.to_mapping()),
            features,
        )
        with self.assertRaisesRegex(ValueError, "keep_last must be >= 0"):
            DciConversationFeatures(clear_tool_results_keep_last=-1)

        for field, invalid in (
            ("clear_tool_results", "false"),
            ("externalize_tool_results", 1),
            ("strip_thinking", []),
            ("strip_usage", {}),
        ):
            with self.subTest(field=field, invalid=invalid):
                payload = features.to_mapping()
                payload[field] = invalid
                with self.assertRaisesRegex(ValueError, "boolean"):
                    DciConversationFeatures.from_mapping(payload)
                with self.assertRaisesRegex(ValueError, "boolean"):
                    DciConversationFeatures(**payload)

        malformed_keep_last = features.to_mapping()
        malformed_keep_last["clear_tool_results_keep_last"] = True
        with self.assertRaisesRegex(ValueError, "keep_last must be >= 0"):
            DciConversationFeatures.from_mapping(malformed_keep_last)
        with self.assertRaisesRegex(ValueError, "unknown"):
            DciConversationFeatures.from_mapping({**features.to_mapping(), "extra": False})

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

    def test_dead_metadata_swap_cannot_admit_b_while_a_holds_directory_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            owner_a = DciRunLock.acquire(output_dir)
            lock_path = output_dir / DciRunLock.LOCK_NAME
            replacement = self._lock_payload(pid=999_999_999, owner_token="replacement-owner")
            replacement_path = output_dir / ".replacement"
            replacement_path.write_text(json.dumps(replacement), encoding="utf-8")
            os.replace(replacement_path, lock_path)

            with self.assertRaises(RuntimeError):
                DciRunLock.acquire(output_dir)
            owner_a.release()

            self.assertEqual(json.loads(lock_path.read_text(encoding="utf-8")), replacement)

    def test_release_never_unlinks_metadata_by_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            owner = DciRunLock.acquire(output_dir)

            with patch.object(
                Path,
                "unlink",
                side_effect=AssertionError("release must not name-delete metadata"),
            ):
                owner.release()

            self.assertTrue((output_dir / DciRunLock.LOCK_NAME).is_file())

    def test_directory_lock_is_held_during_delayed_metadata_reconciliation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            output_dir.mkdir(mode=0o700)
            lock_path = output_dir / DciRunLock.LOCK_NAME
            lock_path.write_text(
                json.dumps(self._lock_payload(pid=999_999_999, owner_token="stale-owner")),
                encoding="utf-8",
            )
            original_reader = artifacts._lock_payload_at
            metadata_read_started = threading.Event()
            continue_metadata_read = threading.Event()

            def delay_b_metadata(directory_fd: int, name: str) -> dict[str, object]:
                if threading.current_thread().name == "owner-b":
                    metadata_read_started.set()
                    continue_metadata_read.wait(timeout=5)
                return original_reader(directory_fd, name)

            result: list[DciRunLock | BaseException] = []

            def acquire_b() -> None:
                try:
                    result.append(DciRunLock.acquire(output_dir))
                except BaseException as exc:
                    result.append(exc)

            with patch("asterion.dci.artifacts._lock_payload_at", side_effect=delay_b_metadata):
                owner_b_thread = threading.Thread(target=acquire_b, name="owner-b")
                owner_b_thread.start()
                self.assertTrue(metadata_read_started.wait(timeout=5))
                contender_fd = os.open(output_dir, os.O_RDONLY)
                try:
                    with self.assertRaises(BlockingIOError):
                        fcntl.flock(contender_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                finally:
                    os.close(contender_fd)
                    continue_metadata_read.set()
                    owner_b_thread.join(timeout=5)

            self.assertEqual(len(result), 1)
            self.assertIsInstance(result[0], DciRunLock)
            owner_b = result[0]
            assert isinstance(owner_b, DciRunLock)
            with self.assertRaises(RuntimeError):
                DciRunLock.acquire(output_dir)
            owner_b.release()

    def test_closing_the_owned_directory_fd_permits_the_next_owner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            owner_a = DciRunLock.acquire(output_dir)
            self.assertTrue(hasattr(owner_a, "_directory_fd"))
            os.close(owner_a._directory_fd)
            owner_a._released = True

            owner_b = DciRunLock.acquire(output_dir)
            owner_b.release()

    def test_locking_fails_closed_when_os_advisory_locking_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"

            with patch("asterion.dci.artifacts.fcntl", None):
                with self.assertRaisesRegex(RuntimeError, "locking is unavailable"):
                    DciRunLock.acquire(output_dir)

            self.assertFalse(output_dir.exists())

    def test_post_flock_metadata_setup_faults_release_fd_without_publishing(self) -> None:
        fault_targets = (
            ("absolute", "asterion.dci.artifacts.Path.absolute"),
            ("token", "asterion.dci.artifacts.secrets.token_hex"),
            ("hostname", "asterion.dci.artifacts.socket.gethostname"),
        )
        for name, target in fault_targets:
            with self.subTest(fault=name), tempfile.TemporaryDirectory() as temporary_directory:
                output_dir = Path(temporary_directory) / "run"
                with patch(target, side_effect=OSError(f"{name} fault")):
                    with self.assertRaisesRegex(OSError, f"{name} fault"):
                        DciRunLock.acquire(output_dir)

                self.assertTrue(output_dir.is_dir())
                self.assertEqual(list(output_dir.iterdir()), [])
                try:
                    next_owner = DciRunLock.acquire(output_dir)
                except RuntimeError as exc:
                    self.fail(f"{name} fault leaked the directory lock: {exc}")
                next_owner.release()

    def test_recorder_writes_remain_rooted_to_locked_inode_after_path_rebinding(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "run"
            moved_output = root / "moved-original-run"
            recorder_a = DciRunRecorder(
                output_dir=output_dir,
                request=request(root),
                paths=resolve_dci_paths(root),
            )
            output_dir.rename(moved_output)
            recorder_b = DciRunRecorder(
                output_dir=output_dir,
                request=DciRunRequest(run_id="run-b", question="question-b", cwd=root),
                paths=resolve_dci_paths(root),
            )
            try:
                inode_a = os.fstat(recorder_a.lock._directory_fd).st_ino
                inode_b = os.fstat(recorder_b.lock._directory_fd).st_ino
                before_b_events = (output_dir / "events.jsonl").read_text(encoding="utf-8")

                recorder_a.record_event({"type": "agent_start"})

                self.assertNotEqual(inode_a, inode_b)
                self.assertEqual(
                    (output_dir / "events.jsonl").read_text(encoding="utf-8"),
                    before_b_events,
                )
                self.assertIn(
                    '"type": "agent_start"',
                    (moved_output / "events.jsonl").read_text(encoding="utf-8"),
                )
                self.assertEqual(
                    json.loads((output_dir / "state.json").read_text(encoding="utf-8"))["run_id"],
                    "run-b",
                )
                self.assertEqual(
                    json.loads((moved_output / "state.json").read_text(encoding="utf-8"))["run_id"],
                    "durable-run",
                )
            finally:
                recorder_a.close()
                recorder_b.close()

    def test_recorder_rejects_nested_protocol_and_tool_result_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            external = root / "external"
            external.mkdir()
            protocol_output = root / "protocol-run"
            protocol_output.mkdir()
            (protocol_output / "protocol").symlink_to(external, target_is_directory=True)

            with self.assertRaises(RuntimeError):
                DciRunRecorder(
                    output_dir=protocol_output,
                    request=request(root),
                    paths=resolve_dci_paths(root),
                )

            tool_output = root / "tool-run"
            recorder = DciRunRecorder(
                output_dir=tool_output,
                request=request(root),
                paths=resolve_dci_paths(root),
                features=DciConversationFeatures(externalize_tool_results=True),
            )
            (tool_output / "tool_results").symlink_to(external, target_is_directory=True)
            with self.assertRaises(RuntimeError):
                recorder.record_event(
                    {
                        "type": "message_end",
                        "message": {
                            "role": "toolResult",
                            "toolCallId": "call-1",
                            "content": [{"type": "text", "text": "body"}],
                        },
                    }
                )
            self.assertEqual(list(external.iterdir()), [])

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

    def test_release_leaves_replacement_metadata_untouched(self) -> None:
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
            replacement = self._lock_payload(pid=os.getpid(), owner_token="replacement-owner")
            replacement_path = output_dir / ".replacement"
            replacement_path.write_text(json.dumps(replacement), encoding="utf-8")
            os.replace(replacement_path, lock_path)

            with patch(
                "asterion.dci.artifacts._lock_payload",
                side_effect=AssertionError("release must not read metadata authority"),
            ):
                owner.release()

            self.assertTrue(lock_path.is_file(), "release deleted the raced replacement lock")
            self.assertEqual(json.loads(lock_path.read_text(encoding="utf-8")), replacement)

    def test_metadata_write_failure_releases_directory_lock_and_preserves_existing_metadata(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory) / "run"
            output_dir.mkdir(mode=0o700)
            lock_path = output_dir / DciRunLock.LOCK_NAME
            existing = self._lock_payload(pid=os.getpid(), owner_token="existing-owner")
            lock_path.write_text(json.dumps(existing), encoding="utf-8")
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

            self.assertEqual(json.loads(lock_path.read_text(encoding="utf-8")), existing)
            next_owner = DciRunLock.acquire(output_dir)
            next_owner.release()

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

            def swap_after_replace(source: str, target: str, **kwargs) -> None:
                real_replace(source, target, **kwargs)
                destination_fd = kwargs["dst_dir_fd"]
                os.unlink(target, dir_fd=destination_fd)
                os.symlink(external, target, dir_fd=destination_fd)

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
                "asterion.dci.artifacts._atomic_write_json_at",
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

    def test_resume_rebuilds_pending_tool_timing_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "run"
            first = DciRunRecorder(
                output_dir=output_dir,
                request=request(root),
                paths=resolve_dci_paths(root),
            )
            first.record_event(
                {
                    "type": "tool_execution_start",
                    "toolCallId": "call-completed",
                    "toolName": "read",
                    "args": {"path": "done"},
                }
            )
            first.record_event(
                {
                    "type": "tool_execution_end",
                    "toolCallId": "call-completed",
                    "toolName": "read",
                    "isError": False,
                    "result": "done",
                }
            )
            first.record_event(
                {
                    "type": "message_end",
                    "message": {
                        "role": "toolResult",
                        "toolCallId": "call-completed",
                        "toolName": "read",
                        "content": [{"type": "text", "text": "done"}],
                    },
                }
            )
            first.record_event(
                {
                    "type": "tool_execution_start",
                    "toolCallId": "call-resume",
                    "toolName": "read",
                    "args": {"path": "item"},
                }
            )
            first.finalize(status="failed")

            resumed = DciRunRecorder(
                output_dir=output_dir,
                request=request(root),
                paths=resolve_dci_paths(root),
                resume=True,
            )
            self.assertIn("call-resume", resumed._pending_tool_starts)
            self.assertIn("call-completed", resumed._completed_tool_timings)
            resumed.finalize(status="failed")

            conversation = json.loads((output_dir / "conversation_full.json").read_text())
            timing = conversation["messages"][-1]["tool_execution"]
            self.assertEqual(timing["status"], "completed")
            self.assertEqual(timing["tool_call_id"], "call-completed")
            self.assertGreaterEqual(timing["duration_ms"], 0)

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
                    clear_tool_results_keep_last=0,
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

    def test_processed_view_keeps_full_evidence_private_and_uses_safe_collision_names(self) -> None:
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
                    clear_tool_results_keep_last=2,
                    strip_thinking=True,
                    strip_usage=True,
                ),
            )
            call_ids = ("../escape", "..\\escape", "call-3", "call-4")
            for index, call_id in enumerate(call_ids, 1):
                recorder.record_event(
                    {
                        "type": "tool_execution_start",
                        "toolCallId": call_id,
                        "toolName": "read",
                        "args": {"path": f"secret-{index}"},
                    }
                )
                recorder.record_event(
                    {
                        "type": "tool_execution_end",
                        "toolCallId": call_id,
                        "toolName": "read",
                        "isError": False,
                        "result": f"body-{index}",
                    }
                )
                recorder.record_event(
                    {
                        "type": "message_end",
                        "message": {
                            "role": "toolResult",
                            "toolCallId": call_id,
                            "toolName": "read",
                            "content": [{"type": "text", "text": f"SECRET-BODY-{index}"}],
                        },
                    }
                )
            recorder.record_event(
                {
                    "type": "message_end",
                    "message": {
                        "role": "assistant",
                        "content": [
                            {"type": "thinking", "thinking": "PRIVATE-THINKING"},
                            {"type": "text", "text": "answer"},
                        ],
                        "usage": {"input": 10, "output": 2},
                    },
                }
            )
            recorder.finalize(status="completed", final_text="answer")

            full = json.loads((output_dir / "conversation_full.json").read_text())
            processed = json.loads((output_dir / "conversation.json").read_text())
            full_text = json.dumps(full)
            processed_text = json.dumps(processed)
            self.assertIn("PRIVATE-THINKING", full_text)
            self.assertIn('"usage"', full_text)
            self.assertNotIn("PRIVATE-THINKING", processed_text)
            self.assertNotIn('"usage"', processed_text)
            full_tools = [m for m in full["messages"] if m.get("role") == "toolResult"]
            processed_tools = [m for m in processed["messages"] if m.get("role") == "toolResult"]
            self.assertEqual(len(full_tools), 4)
            self.assertTrue(all("SECRET-BODY" in json.dumps(message) for message in full_tools))
            self.assertTrue(all("tool_execution" in message for message in full_tools))
            self.assertTrue(all("externalized" in m["context_management"]["tool_result"] for m in processed_tools))
            self.assertTrue(all(m["context_management"]["tool_result"].get("status") == "cleared" for m in processed_tools[:2]))
            self.assertTrue(all("SECRET-BODY" not in json.dumps(message) for message in processed_tools[:2]))
            self.assertTrue(all("SECRET-BODY" in json.dumps(message) for message in processed_tools[2:]))

            relative_paths = [
                m["context_management"]["tool_result"]["externalized"]["path"]
                for m in processed_tools
            ]
            self.assertEqual(len(relative_paths), len(set(relative_paths)))
            for relative in relative_paths:
                path = Path(relative)
                self.assertFalse(path.is_absolute())
                self.assertNotIn("..", path.parts)
                self.assertEqual((output_dir / path).resolve().parent, (output_dir / "tool_results").resolve())
                self.assertLessEqual(len(path.name), 96)
                self.assertTrue((output_dir / path).is_file())

    def test_tool_result_names_reserve_complete_casefolded_candidates(self) -> None:
        messages = [
            {"toolCallId": call_id}
            for call_id in ("call", "CALL", "call-2", "call", "CALL-2")
        ]

        names = DciRunRecorder._tool_result_names(messages)

        self.assertEqual(
            names,
            ["call.json", "CALL-2.json", "call-2-2.json", "call-3.json", "CALL-2-3.json"],
        )
        self.assertEqual(len({name.casefold() for name in names}), len(names))

    def test_valid_tool_ids_with_suffix_collisions_keep_distinct_externalized_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "run"
            recorder = DciRunRecorder(
                output_dir=output_dir,
                request=request(root),
                paths=resolve_dci_paths(root),
                features=DciConversationFeatures(externalize_tool_results=True),
            )
            for index, call_id in enumerate(("call", "CALL", "call-2"), 1):
                recorder.record_event(
                    {
                        "type": "tool_execution_start",
                        "toolCallId": call_id,
                        "toolName": "read",
                        "args": {"path": str(index)},
                    }
                )
                recorder.record_event(
                    {
                        "type": "tool_execution_end",
                        "toolCallId": call_id,
                        "toolName": "read",
                        "isError": False,
                        "result": f"body-{index}",
                    }
                )
                recorder.record_event(
                    {
                        "type": "message_end",
                        "message": {
                            "role": "toolResult",
                            "toolCallId": call_id,
                            "content": [{"type": "text", "text": f"body-{index}"}],
                        },
                    }
                )
            recorder.finalize(status="failed")

            processed = json.loads((output_dir / "conversation.json").read_text())
            pointers = [
                message["context_management"]["tool_result"]["externalized"]["path"]
                for message in processed["messages"]
            ]
            self.assertEqual(len({pointer.casefold() for pointer in pointers}), 3)
            bodies = [
                json.loads((output_dir / pointer).read_text())["message"]["content"][0]["text"]
                for pointer in pointers
            ]
            self.assertEqual(bodies, ["body-1", "body-2", "body-3"])


if __name__ == "__main__":
    unittest.main()
