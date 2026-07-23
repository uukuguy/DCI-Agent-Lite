from __future__ import annotations

import re
import shlex
import subprocess
import unittest
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
REQUIRED_ASSETS = (
    ".env.template",
    ".gitignore",
    "LICENSE",
    "Makefile",
    "README.md",
    "pi-revision.txt",
    "uv.lock",
)
LIFECYCLE_TARGETS = (
    "help",
    "sync",
    "build",
    "test",
    "lint",
    "docs-check",
    "check",
    "promotion-check",
)
FRAMEWORK_TARGETS = (
    "asterion-list",
    "asterion-describe",
    "asterion-verify-preflight",
    "asterion-verify-basic",
    "asterion-verify-acceptance",
    "asterion-verify-complete",
    "asterion-run",
)
DCI_TARGETS = (
    "dci-system-prompt",
    "dci-run",
    "dci-terminal",
    "dci-resume",
    "dci-evaluate",
    "dci-benchmark",
    "dci-export",
    "dci-ablation",
    "dci-paper",
)
CROSS_LANGUAGE_TARGETS = ("test-typescript", "test-rust", "check-rust")


def dry_run(target: str, *assignments: str) -> tuple[str, ...]:
    completed = subprocess.run(
        ["make", "-n", target, *assignments],
        cwd=PROJECT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return tuple(shlex.split(completed.stdout.replace("\\\n", " ")))


class StandaloneRepositoryTests(unittest.TestCase):
    def _makefile_text(self) -> str:
        path = PROJECT / "Makefile"
        self.assertTrue(path.is_file(), "standalone Makefile is missing")
        return path.read_text(encoding="utf-8") if path.is_file() else ""

    def test_required_repository_assets_exist(self) -> None:
        missing = [name for name in REQUIRED_ASSETS if not (PROJECT / name).is_file()]
        self.assertEqual(missing, [])

    def test_environment_template_has_no_credentials_or_parent_defaults(self) -> None:
        path = PROJECT / ".env.template"
        self.assertTrue(path.is_file(), "standalone environment template is missing")
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        self.assertNotRegex(text, r"(?m)^[A-Z0-9_]*(?:KEY|TOKEN|SECRET)=.+$")
        self.assertNotIn("../", text)
        self.assertNotIn("pi-mono", text)

    def test_makefile_exposes_complete_explicit_command_surface(self) -> None:
        text = self._makefile_text()
        phony = {
            token
            for line in text.splitlines()
            if line.startswith(".PHONY:")
            for token in line.removeprefix(".PHONY:").split()
        }
        expected = set(
            LIFECYCLE_TARGETS
            + FRAMEWORK_TARGETS
            + DCI_TARGETS
            + CROSS_LANGUAGE_TARGETS
        )
        self.assertTrue(expected.issubset(phony), sorted(expected - phony))
        self.assertIsNone(re.search(r"(?m)^asterion-verify:\s*$", text))
        self.assertNotIn("eval ", text)

    def test_make_help_labels_cost_boundaries(self) -> None:
        completed = subprocess.run(
            ["make", "help"],
            cwd=PROJECT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("provider-free", completed.stdout)
        self.assertIn("bounded provider-backed", completed.stdout)
        self.assertIn(
            "full execution requires separate authorization", completed.stdout
        )

    def test_framework_targets_render_exact_commands(self) -> None:
        expected = {
            "asterion-list": ("uv", "run", "asterion", "list"),
            "asterion-describe": (
                "uv",
                "run",
                "asterion",
                "describe",
                "--provider",
                "dci-agent-lite",
            ),
            "asterion-verify-preflight": (
                "uv",
                "run",
                "asterion",
                "verify",
                "--provider",
                "dci-agent-lite",
                "--level",
                "preflight",
            ),
            "asterion-verify-basic": (
                "uv",
                "run",
                "asterion",
                "verify",
                "--provider",
                "dci-agent-lite",
                "--level",
                "basic",
            ),
            "asterion-verify-acceptance": (
                "uv",
                "run",
                "asterion",
                "verify",
                "--provider",
                "dci-agent-lite",
                "--level",
                "acceptance",
            ),
            "asterion-verify-complete": (
                "uv",
                "run",
                "asterion",
                "verify",
                "--provider",
                "dci-agent-lite",
                "--level",
                "complete",
            ),
            "asterion-run": ("uv", "run", "asterion", "run"),
        }
        for target, command in expected.items():
            with self.subTest(target=target):
                self.assertEqual(dry_run(target), command)

    def test_dci_targets_render_exact_commands(self) -> None:
        commands = {
            "dci-system-prompt": "system-prompt",
            "dci-run": "run",
            "dci-terminal": "terminal",
            "dci-resume": "resume",
            "dci-evaluate": "evaluate",
            "dci-benchmark": "benchmark",
            "dci-export": "export",
            "dci-ablation": "ablation",
            "dci-paper": "paper",
        }
        for target, command in commands.items():
            with self.subTest(target=target):
                self.assertEqual(
                    dry_run(target), ("uv", "run", "asterion-dci", command)
                )

    def test_make_passthrough_arguments_are_not_shell_evaluated(self) -> None:
        self.assertEqual(
            dry_run("asterion-run", "ASTERION_ARGS=--help"),
            ("uv", "run", "asterion", "run", "--help"),
        )
        self.assertEqual(
            dry_run("dci-run", "DCI_ARGS=--help"),
            ("uv", "run", "asterion-dci", "run", "--help"),
        )

    def test_lifecycle_and_cross_language_recipes_use_native_gates(self) -> None:
        text = self._makefile_text()
        for command in (
            "$(UV_BIN) sync --frozen",
            "$(UV_BIN) build .",
            "python -m unittest discover -s tests -v",
            "python -m compileall -q src tests tools",
            "ruff check src tests tools",
            "python tools/check_docs.py",
            "python tools/check_promotion.py",
            "npm ci --prefix packages/typescript/asterion-runtime",
            "npm test --prefix packages/typescript/asterion-runtime",
            "npm test --prefix packages/typescript/dci-context-extension",
            "cargo test --manifest-path packages/rust/controlled-executor/Cargo.toml",
            "cargo fmt --manifest-path packages/rust/controlled-executor/Cargo.toml -- --check",
            "cargo clippy --manifest-path packages/rust/controlled-executor/Cargo.toml -- -D warnings",
        ):
            with self.subTest(command=command):
                self.assertIn(command, text)


if __name__ == "__main__":
    unittest.main()
