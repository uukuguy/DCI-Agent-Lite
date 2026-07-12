from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SETUP_PI_SOURCE = REPO_ROOT / "scripts/setup_pi.sh"


class PiSetupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.project = self.root / "project"
        self.source = self.root / "source-pi"
        self.pi_dir = self.project / "pi"
        (self.project / "scripts").mkdir(parents=True)
        self.source.mkdir()
        self.git("init", "-b", "main", cwd=self.source)
        self.git("config", "user.name", "DCI Test", cwd=self.source)
        self.git("config", "user.email", "dci-test@example.invalid", cwd=self.source)

        for package in ("tui", "ai", "agent", "coding-agent"):
            package_dir = self.source / "packages" / package
            package_dir.mkdir(parents=True)
            (package_dir / ".keep").write_text("\n")
        cli_path = self.source / "packages/coding-agent/dist/cli.js"
        cli_path.parent.mkdir()
        cli_path.write_text("commit-a\n")
        self.git("add", ".", cwd=self.source)
        self.git("commit", "-m", "commit a", cwd=self.source)
        self.commit_a = self.git("rev-parse", "HEAD", cwd=self.source)

        cli_path.write_text("commit-b\n")
        self.git("add", ".", cwd=self.source)
        self.git("commit", "-m", "commit b", cwd=self.source)
        self.commit_b = self.git("rev-parse", "HEAD", cwd=self.source)
        (self.project / "pi-revision.txt").write_text(f"{self.commit_a}\n")

        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.npm_log = self.root / "npm.log"
        fake_npm = self.bin_dir / "npm"
        fake_npm.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' \"$*\" >> {self.npm_log!s}\n"
        )
        fake_npm.chmod(fake_npm.stat().st_mode | stat.S_IXUSR)

    def git(self, *args: str, cwd: Path) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=True,
        )
        return result.stdout.strip()

    def install_script_under_test(self) -> Path:
        target = self.project / "scripts/setup_pi.sh"
        if SETUP_PI_SOURCE.exists():
            shutil.copy2(SETUP_PI_SOURCE, target)
        return target

    def run_setup(
        self, *, revision: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "DCI_PI_DIR": str(self.pi_dir),
                "DCI_PI_REPO_URL": str(self.source),
                "PATH": f"{self.bin_dir}{os.pathsep}{env['PATH']}",
            }
        )
        if revision is None:
            env.pop("DCI_PI_REVISION", None)
        else:
            env["DCI_PI_REVISION"] = revision
        return subprocess.run(
            ["bash", str(self.install_script_under_test())],
            cwd=self.project,
            env=env,
            text=True,
            capture_output=True,
        )

    def clone_at(self, revision: str) -> None:
        self.git("clone", str(self.source), str(self.pi_dir), cwd=self.root)
        self.git("checkout", "--detach", revision, cwd=self.pi_dir)

    def test_new_checkout_uses_locked_commit(self) -> None:
        result = self.run_setup()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.pi_dir), self.commit_a)

    def test_built_checkout_at_pin_is_unchanged(self) -> None:
        self.clone_at(self.commit_a)
        before = self.git("status", "--porcelain", cwd=self.pi_dir)

        result = self.run_setup()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("status", "--porcelain", cwd=self.pi_dir), before)
        self.assertFalse(self.npm_log.exists())

    def test_clean_mismatched_checkout_moves_to_pin(self) -> None:
        self.clone_at(self.commit_b)

        result = self.run_setup()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.pi_dir), self.commit_a)
        self.assertTrue(self.npm_log.exists())

    def test_dirty_mismatched_checkout_fails_without_mutation(self) -> None:
        self.clone_at(self.commit_b)
        marker = self.pi_dir / "local-change.txt"
        marker.write_text("keep me\n")
        before_head = self.git("rev-parse", "HEAD", cwd=self.pi_dir)

        result = self.run_setup()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dirty", result.stderr.lower())
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.pi_dir), before_head)
        self.assertEqual(marker.read_text(), "keep me\n")
        self.assertFalse(self.npm_log.exists())

    def test_revision_override_selects_exact_commit(self) -> None:
        result = self.run_setup(revision=self.commit_b)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD", cwd=self.pi_dir), self.commit_b)

    def test_malformed_default_lock_fails_before_clone(self) -> None:
        (self.project / "pi-revision.txt").write_text("main\n")

        result = self.run_setup()

        self.assertEqual(result.returncode, 2)
        self.assertIn("40-character", result.stderr)
        self.assertFalse(self.pi_dir.exists())


if __name__ == "__main__":
    unittest.main()
