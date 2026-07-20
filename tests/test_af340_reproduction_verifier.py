from __future__ import annotations

import io
import json
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import verify_af340_reproduction


class Af340ReproductionVerifierTests(unittest.TestCase):
    def test_local_matrix_uses_literal_source_and_asterion_commands(self) -> None:
        calls: list[tuple[tuple[str, ...], Path]] = []

        def execute(
            argv: tuple[str, ...], *, cwd: Path
        ) -> subprocess.CompletedProcess[str]:
            calls.append((argv, cwd))
            return subprocess.CompletedProcess(argv, 0, "ok", "")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            result = verify_af340_reproduction.verify_local(
                repo_root=root,
                output_root=root / "private-local",
                executor=execute,
            )

        self.assertTrue(result.passed)
        self.assertEqual(
            [argv for argv, _cwd in calls],
            [spec.argv for spec in verify_af340_reproduction.LOCAL_MATRIX],
        )
        self.assertTrue(all(cwd == root for _argv, cwd in calls))
        rendered = "\n".join(" ".join(argv) for argv, _cwd in calls)
        self.assertIn("tools/verify_original_readme.py --level local", rendered)
        self.assertIn("tests.test_config", rendered)
        self.assertIn("tests.test_asterion_dci_config", rendered)
        self.assertIn("tests.test_distribution_boundaries", rendered)

    def test_local_mode_performs_zero_provider_operations(self) -> None:
        calls: list[tuple[str, ...]] = []

        def execute(
            argv: tuple[str, ...], *, cwd: Path
        ) -> subprocess.CompletedProcess[str]:
            del cwd
            calls.append(argv)
            return subprocess.CompletedProcess(argv, 0, "ok", "")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = verify_af340_reproduction.main(
                [
                    "local",
                    "--repo-root",
                    str(root),
                    "--output-root",
                    str(root / "private-local"),
                ],
                executor=execute,
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(code, 0, stderr.getvalue())
        self.assertEqual(len(calls), len(verify_af340_reproduction.LOCAL_MATRIX))
        self.assertIn("PASS", stdout.getvalue())
        self.assertIn("Agent operations: 0", stdout.getvalue())
        self.assertIn("Judge operations: 0", stdout.getvalue())
        self.assertIn("Full dataset ran: no", stdout.getvalue())

    def test_public_report_excludes_secrets_bodies_and_private_paths(self) -> None:
        sentinel = "sentinel-secret-answer-body"

        def execute(
            argv: tuple[str, ...], *, cwd: Path
        ) -> subprocess.CompletedProcess[str]:
            del cwd
            return subprocess.CompletedProcess(argv, 0, sentinel, sentinel)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_root = root / "sentinel-private-output"
            result = verify_af340_reproduction.verify_local(
                repo_root=root,
                output_root=output_root,
                executor=execute,
            )
            public = json.dumps(result.public_report(), sort_keys=True)
            private = result.evidence_path.read_text(encoding="utf-8")

            self.assertEqual(stat.S_IMODE(output_root.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(result.evidence_path.stat().st_mode), 0o600)

        for rendered in (public, private):
            self.assertNotIn(sentinel, rendered)
            self.assertNotIn(str(root), rendered)
            self.assertNotIn("answer", rendered)
            self.assertNotIn("api_key", rendered)
        self.assertRegex(
            result.public_report()["evidence_sha256"], r"^[0-9a-f]{64}$"
        )


if __name__ == "__main__":
    unittest.main()
