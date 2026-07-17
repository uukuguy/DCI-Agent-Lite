from __future__ import annotations

import hashlib
import json
import os
import socket
import stat
import subprocess
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

import fcntl

import asterion.dci.artifacts as artifacts
from asterion.dci.artifacts import (
    DciContextPolicyEvidence,
    DciContextTelemetry,
    DciConversationFeatures,
    DciRunLock,
    DciRunRecorder,
    _bounded_text_tail,
    atomic_write_json,
    bind_paper_benchmark_evidence,
)
from asterion.dci.config import resolve_dci_paths
from asterion.dci.context_profiles import resolve_context_profile
from asterion.dci.provenance import collect_pi_provenance, format_pi_revision_warning
from asterion.dci.run import DciRunRequest
from asterion.dci.verification import paper_benchmark_resource_digests
from asterion.runtime.protocol import validate_event_stream


def request(root: Path) -> DciRunRequest:
    return DciRunRequest(run_id="durable-run", question="question", cwd=root)


class AsterionDciArtifactTests(unittest.TestCase):
    def test_context_policy_evidence_is_closed_and_body_free(self) -> None:
        mapping = {
            "schema": "dci.context-telemetry/v2",
            "event": "session_compact",
            "profile": "level4",
            "contractVersion": "dci.context-profile/v1",
            "extensionVersion": "0.1.0",
            "accumulatedOriginalToolCharacters": 0,
            "truncatedResults": 2,
            "compactionCount": 1,
            "preservedTurns": 12,
            "compactionPending": False,
            "summaryAttempts": 1,
            "summarySuccesses": 1,
            "consecutiveSummaryFailures": 0,
            "summarySuppressed": False,
        }
        telemetry = DciContextTelemetry.from_mapping(mapping)
        profile = resolve_context_profile("level4")
        assert profile is not None
        evidence = DciContextPolicyEvidence(
            profile=profile,
            extension_version="0.1.0",
            extension_sha256="a" * 64,
            telemetry=(telemetry,),
        )

        self.assertEqual(
            evidence.public_summary(),
            {
                "schema": "dci.context-policy-evidence/v2",
                "profile": "level4",
                "contract_version": "dci.context-profile/v1",
                "extension_version": "0.1.0",
                "extension_sha256": "a" * 64,
                "truncated_results": 2,
                "compactions": 1,
                "preserved_turns": 12,
                "summary_attempts": 1,
                "summary_successes": 1,
                "summary_suppressed": False,
            },
        )
        for invalid in ({**mapping, "secret": "PRIVATE"}, {**mapping, "summaryAttempts": -1}):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                RuntimeError, "context policy evidence is invalid"
            ):
                DciContextTelemetry.from_mapping(invalid)

    @staticmethod
    def _lock_payload(*, pid: int, owner_token: str) -> dict[str, object]:
        return {
            "pid": pid,
            "hostname": socket.gethostname(),
            "created_at": "2026-07-14T00:00:00+00:00",
            "owner_token": owner_token,
        }

    def test_pi_provenance_is_revision_exact_and_credential_safe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repo = root / "pi"
            package_dir = repo / "packages/coding-agent"
            package_dir.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
            (package_dir / "marker.txt").write_text("clean\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            origin = (
                "https://sentinel-user:sentinel-pass@example.invalid/"
                "repo.git?token=sentinel-query#sentinel-fragment"
            )
            subprocess.run(["git", "remote", "add", "origin", origin], cwd=repo, check=True)
            lock_file = root / "pi-revision.txt"
            lock_file.write_text(f"{revision}\n", encoding="utf-8")

            clean = collect_pi_provenance(package_dir, lock_file, None)
            override = collect_pi_provenance(package_dir, lock_file, revision)
            (package_dir / "marker.txt").write_text("dirty\n", encoding="utf-8")
            dirty = collect_pi_provenance(package_dir, lock_file, None)

        self.assertEqual(clean["commit"], revision)
        self.assertTrue(clean["managed_git_checkout"])
        self.assertFalse(clean["dirty"])
        self.assertTrue(clean["lock_match"])
        self.assertTrue(clean["expected_match"])
        self.assertEqual(clean["origin"], {"host": "example.invalid", "path": "/repo.git"})
        self.assertEqual(override["expected_revision_source"], "DCI_PI_REVISION")
        self.assertTrue(dirty["dirty"])
        serialized = json.dumps([clean, override, dirty])
        for sentinel in (
            "sentinel-user",
            "sentinel-pass",
            "sentinel-query",
            "sentinel-fragment",
        ):
            self.assertNotIn(sentinel, serialized)

    def test_pi_provenance_handles_non_git_and_safe_mismatch_warning(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            package_dir = root / "not-git"
            package_dir.mkdir()
            lock_file = root / "pi-revision.txt"
            lock_revision = "1" * 40
            actual_revision = "2" * 40
            lock_file.write_text(f"{lock_revision}\n", encoding="utf-8")

            non_git = collect_pi_provenance(package_dir, lock_file, None)
            mismatch = {
                **non_git,
                "commit": actual_revision,
                "expected_revision": lock_revision,
                "expected_revision_source": "pi-revision.txt",
                "expected_match": False,
            }
            warning = format_pi_revision_warning(mismatch)

        self.assertFalse(non_git["managed_git_checkout"])
        self.assertIsNone(non_git["commit"])
        self.assertIsNone(non_git["dirty"])
        self.assertIsNone(non_git["origin"])
        self.assertIsNone(format_pi_revision_warning(non_git))
        self.assertIn(actual_revision, warning or "")
        self.assertIn(lock_revision, warning or "")
        self.assertNotIn(str(package_dir), warning or "")

    def test_pi_provenance_discards_non_revision_lock_and_override_values(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            package_dir = root / "not-git"
            package_dir.mkdir()
            lock_file = root / "pi-revision.txt"
            lock_file.write_text("sentinel-lock-credential\n", encoding="utf-8")

            provenance = collect_pi_provenance(
                package_dir,
                lock_file,
                "sentinel-override-credential",
            )

        serialized = json.dumps(provenance)
        self.assertIsNone(provenance["lock_revision"])
        self.assertIsNone(provenance["expected_revision"])
        self.assertIsNone(format_pi_revision_warning(provenance))
        self.assertNotIn("sentinel-lock-credential", serialized)
        self.assertNotIn("sentinel-override-credential", serialized)

    def test_pi_provenance_rejects_every_local_origin_form(self) -> None:
        local_origins = (
            "file:///sentinel-absolute/pi.git",
            "file://localhost/sentinel-localhost/pi.git",
            "file://example.invalid/sentinel-file-remotehost/pi.git",
            "file:sentinel-file-relative/pi.git",
            "/sentinel-root/pi.git",
            "../sentinel-relative/pi.git",
            r"C:\sentinel-windows\pi.git",
            "file:C:/sentinel-file-drive/pi.git",
            r"\\localhost\sentinel-unc\pi.git",
            "localhost:/sentinel-scp-local/pi.git",
            "sentinel-user@localhost:sentinel-scp-user/pi.git",
            "http://127.1/sentinel-loopback-short/pi.git",
            "ssh://127.0.1/sentinel-loopback-dotted/pi.git",
            "git://2130706433/sentinel-loopback-integer/pi.git",
            "http://0x7f000001/sentinel-loopback-hex/pi.git",
            "ssh://017700000001/sentinel-loopback-octal/pi.git",
            "127.1:sentinel-loopback-scp-short/pi.git",
            "git@2130706433:sentinel-loopback-scp-integer/pi.git",
            "http://0xfffffffff/sentinel-overflow-hex/pi.git",
            "http://4294967296/sentinel-overflow-decimal/pi.git",
            "http://0x100000000/sentinel-overflow-hex-boundary/pi.git",
            "http://1.2.3.4.5/sentinel-excess-components/pi.git",
            "http://256.1.1.1/sentinel-four-part-overflow/pi.git",
            "http://1.16777216/sentinel-two-part-overflow/pi.git",
            "http://1.2.65536/sentinel-three-part-overflow/pi.git",
            "http://0/sentinel-zero-single/pi.git",
            "ssh://0.0.0.0/sentinel-zero-dotted/pi.git",
            "git://00/sentinel-zero-octal/pi.git",
            "http://0x0/sentinel-zero-hex/pi.git",
            "ssh://[::]/sentinel-zero-ipv6/pi.git",
            "0:sentinel-zero-scp/pi.git",
            "git@0.0.0.0:sentinel-zero-scp-dotted/pi.git",
            "git@[::]:sentinel-zero-scp-ipv6/pi.git",
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repo = root / "pi"
            package_dir = repo / "packages/coding-agent"
            package_dir.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(
                ["git", "config", "user.email", "fixture@example.invalid"],
                cwd=repo,
                check=True,
            )
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
            (package_dir / "marker.txt").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            lock_file = root / "pi-revision.txt"
            lock_file.write_text(f"{revision}\n", encoding="utf-8")
            subprocess.run(
                ["git", "remote", "add", "origin", "https://example.invalid/repo.git"],
                cwd=repo,
                check=True,
            )

            for origin in local_origins:
                with self.subTest(origin=origin):
                    subprocess.run(
                        ["git", "remote", "set-url", "origin", origin],
                        cwd=repo,
                        check=True,
                    )
                    provenance = collect_pi_provenance(package_dir, lock_file, None)
                    serialized = json.dumps(provenance)
                    self.assertIsNone(provenance["origin"])
                    self.assertNotIn("sentinel", serialized.lower())
                    self.assertNotEqual(provenance["origin"], {"host": "file"})

    def test_pi_provenance_accepts_only_credential_free_remote_origin_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repo = root / "pi"
            package_dir = repo / "packages/coding-agent"
            package_dir.mkdir(parents=True)
            subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
            subprocess.run(
                ["git", "config", "user.email", "fixture@example.invalid"],
                cwd=repo,
                check=True,
            )
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=repo, check=True)
            (package_dir / "marker.txt").write_text("fixture\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
            revision = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=repo,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            lock_file = root / "pi-revision.txt"
            lock_file.write_text(f"{revision}\n", encoding="utf-8")
            subprocess.run(
                ["git", "remote", "add", "origin", "git@example.invalid:team/repo.git"],
                cwd=repo,
                check=True,
            )
            expected_origins = (
                (
                    "git@example.invalid:team/repo.git",
                    {"host": "example.invalid", "path": "/team/repo.git"},
                ),
                ("ssh://x/team/repo.git", {"host": "x", "path": "/team/repo.git"}),
                ("git@x:team/repo.git", {"host": "x", "path": "/team/repo.git"}),
                ("ssh://1x/team/repo.git", {"host": "1x", "path": "/team/repo.git"}),
                ("git@1x:team/repo.git", {"host": "1x", "path": "/team/repo.git"}),
                (
                    "ssh://1-host/team/repo.git",
                    {"host": "1-host", "path": "/team/repo.git"},
                ),
                (
                    "git@1-host:team/repo.git",
                    {"host": "1-host", "path": "/team/repo.git"},
                ),
                (
                    "ssh://123abc/team/repo.git",
                    {"host": "123abc", "path": "/team/repo.git"},
                ),
                (
                    "git@123abc:team/repo.git",
                    {"host": "123abc", "path": "/team/repo.git"},
                ),
                (
                    "ssh://deadbeef/team/repo.git",
                    {"host": "deadbeef", "path": "/team/repo.git"},
                ),
                (
                    "git@deadbeef:team/repo.git",
                    {"host": "deadbeef", "path": "/team/repo.git"},
                ),
                (
                    "http://0xffffffff/team/repo.git",
                    {"host": "0xffffffff", "path": "/team/repo.git"},
                ),
                (
                    "http://1.16777215/team/repo.git",
                    {"host": "1.16777215", "path": "/team/repo.git"},
                ),
                (
                    "http://1.2.65535/team/repo.git",
                    {"host": "1.2.65535", "path": "/team/repo.git"},
                ),
                (
                    "http://1.2.3.255/team/repo.git",
                    {"host": "1.2.3.255", "path": "/team/repo.git"},
                ),
            )

            for origin, expected in expected_origins:
                with self.subTest(origin=origin):
                    subprocess.run(
                        ["git", "remote", "set-url", "origin", origin],
                        cwd=repo,
                        check=True,
                    )
                    provenance = collect_pi_provenance(package_dir, lock_file, None)
                    self.assertEqual(provenance["origin"], expected)

    def test_stderr_tail_is_exactly_utf8_bounded_for_multibyte_text(self) -> None:
        cases = (
            ("ascii", "x" * 20_000, "x" * 16_384),
            ("two-byte", "¢" * 10_000 + "a", "¢" * 8_191 + "a"),
            ("euro", "€" * 10_000, "€" * 5_461),
            ("emoji", "🙂" * 10_000, "🙂" * 4_096),
            ("mixed", "€" * 6_000 + "🙂a", "€" * 5_459 + "🙂a"),
            ("surrogate", "\ud800" * 20_000, "?" * 16_384),
        )
        for name, stderr_text, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory)
                output_dir = root / "run"
                recorder = DciRunRecorder(
                    output_dir=output_dir,
                    request=request(root),
                    paths=resolve_dci_paths(root),
                )
                recorder.finalize(status="failed", stderr_text=stderr_text)

                persisted = (output_dir / "stderr.txt").read_text(encoding="utf-8")
                header, framed_body = persisted.split("\n", 1)
                body = framed_body.removesuffix("\n")
                self.assertEqual(header, "[attempt-0001 status=failed]")
                self.assertEqual(body, expected)
                self.assertEqual(_bounded_text_tail(stderr_text, 16_384), expected)
                self.assertLessEqual(len(body.encode("utf-8")), 16_384)

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


class PaperBenchmarkEvidenceBinderTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path, Path]:
        pi_dir = root / "pi-clean"
        pi_dir.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=pi_dir, check=True)
        subprocess.run(["git", "config", "user.email", "fixture@example.invalid"], cwd=pi_dir, check=True)
        subprocess.run(["git", "config", "user.name", "Fixture"], cwd=pi_dir, check=True)
        (pi_dir / "tracked.txt").write_text("runtime\n")
        subprocess.run(["git", "add", "tracked.txt"], cwd=pi_dir, check=True)
        subprocess.run(["git", "commit", "-qm", "fixture"], cwd=pi_dir, check=True)
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=pi_dir, check=True,
            text=True, capture_output=True,
        ).stdout.strip()

        output_root = root / "private-output"
        operations = []
        for operation_id, kind in (
            ("qa-agent", "agent"),
            ("qa-judge", "judge"),
            ("ir-agent", "agent"),
        ):
            directory = output_root / operation_id
            directory.mkdir(parents=True)
            if operation_id == "qa-judge":
                evaluation = output_root / "qa-agent/eval_result.json"
                evaluation.write_text(
                    json.dumps(
                        {
                            "is_correct": True,
                            "judge_model": "gpt-4.1",
                            "judge_api": "responses",
                            "judge_base_url": "https://api.openai.com/v1",
                            "judge_max_output_tokens": 1024,
                            "judge_json_mode": True,
                            "judge_strict_json_schema": False,
                            "judge_responses_store": False,
                            "judge_thinking": None,
                            "judge_request_fingerprint": "a" * 64,
                        }
                    )
                )
                evaluation.chmod(0o600)
                artifact = directory / "evaluation-evidence.json"
                artifact.write_text(
                    json.dumps(
                        {
                            "schema": "asterion.dci.paper-judge-evidence/v1",
                            "accepted": True,
                            "evaluation_sha256": hashlib.sha256(
                                evaluation.read_bytes()
                            ).hexdigest(),
                        }
                    )
                )
            else:
                artifact = directory / "state.json"
                artifact.write_text(f"private {operation_id}\n")
            artifact.chmod(0o600)
            operations.append(
                {
                    "operation_id": operation_id,
                    "kind": kind,
                    "accepted": True,
                    "artifact_digests": {
                        artifact.name: hashlib.sha256(artifact.read_bytes()).hexdigest()
                    },
                }
            )
        report = {
            "schema": "asterion.dci.paper-benchmark-acceptance/v1",
            "mode": "bounded-provider-backed",
            "provider": "fixture-provider",
            "model": "fixture-model",
            "judge_model": "gpt-4.1",
            "pi_revision": revision,
            "pi_tracked_status_sha256": hashlib.sha256(b"").hexdigest(),
            "agent_operations": 2,
            "judge_operations": 1,
            "external_operations": 3,
            "api_request_multiplicity": "externally ambiguous",
            "operation_order": ["qa-agent", "qa-judge", "ir-agent"],
            "full_dataset_ran": False,
            "resources": dict(paper_benchmark_resource_digests()),
            "operations": operations,
        }
        report_path = output_root / "paper-benchmark-acceptance.json"
        report_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
        report_path.chmod(0o600)

        state_dir = root / "climb"
        state_dir.mkdir()
        (state_dir / "hypotheses.yaml").write_text(
            "- id: AF-320-H-004\n"
            "  work_package_id: AF-320\n"
            "  status: pending\n"
            "  results: []\n"
        )
        return report_path, state_dir, pi_dir

    def test_binding_rehashes_private_artifacts_and_confirms_terminal_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            report, state_dir, pi_dir = self._fixture(Path(temp_dir))

            digest = bind_paper_benchmark_evidence(
                report, state_dir=state_dir, pi_dir=pi_dir
            )

            record = state_dir / "provider-evidence/af-320-h-004.json"
            self.assertEqual(hashlib.sha256(record.read_bytes()).hexdigest(), digest)
            hypothesis = (state_dir / "hypotheses.yaml").read_text()
            self.assertIn("status: confirmed", hypothesis)
            self.assertIn("verdict: confirmed 4/4", hypothesis)
            self.assertIn(f"sha256: {digest}", hypothesis)
            before = (record.read_bytes(), hypothesis)
            self.assertEqual(
                bind_paper_benchmark_evidence(report, state_dir=state_dir, pi_dir=pi_dir),
                digest,
            )
            self.assertEqual(before, (record.read_bytes(), (state_dir / "hypotheses.yaml").read_text()))

    def test_mutation_symlink_private_mode_dirty_runtime_and_conflict_fail_without_mutation(self) -> None:
        for case in (
            "artifact",
            "evaluation",
            "symlink",
            "mode",
            "dirty",
            "conflict",
        ):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp_dir:
                report, state_dir, pi_dir = self._fixture(Path(temp_dir))
                if case == "artifact":
                    (report.parent / "qa-agent/state.json").write_text("changed\n")
                    (report.parent / "qa-agent/state.json").chmod(0o600)
                elif case == "evaluation":
                    evaluation = report.parent / "qa-agent/eval_result.json"
                    value = json.loads(evaluation.read_text())
                    value["judge_model"] = "not-gpt-4.1"
                    evaluation.write_text(json.dumps(value))
                    evaluation.chmod(0o600)
                elif case == "symlink":
                    artifact = report.parent / "qa-agent/state.json"
                    target = report.parent / "private-target"
                    target.write_bytes(artifact.read_bytes())
                    target.chmod(0o600)
                    artifact.unlink()
                    artifact.symlink_to(target)
                elif case == "mode":
                    report.chmod(0o644)
                elif case == "dirty":
                    (pi_dir / "untracked.txt").write_text("dirty\n")
                else:
                    evidence = state_dir / "provider-evidence"
                    evidence.mkdir()
                    (evidence / "af-320-h-004.json").write_text("conflict\n")
                before = (state_dir / "hypotheses.yaml").read_bytes()

                with self.assertRaises((OSError, RuntimeError, ValueError)):
                    bind_paper_benchmark_evidence(
                        report, state_dir=state_dir, pi_dir=pi_dir
                    )

                self.assertEqual((state_dir / "hypotheses.yaml").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
