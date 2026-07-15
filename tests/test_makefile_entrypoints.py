from __future__ import annotations

import re
import shlex
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (
    "asterion-describe",
    "asterion-verify-preflight",
    "asterion-verify-basic",
    "asterion-verify-acceptance",
    "asterion-verify-complete",
)


def dry_run(target: str, *assignments: str) -> tuple[str, ...]:
    completed = subprocess.run(
        ["make", "-n", target, *assignments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return tuple(shlex.split(completed.stdout.replace("\\\n", " ")))


class MakefileEntryPointTests(unittest.TestCase):
    def test_targets_are_explicit_phony_and_have_no_ambiguous_alias(self) -> None:
        text = (ROOT / "Makefile").read_text()
        phony = {
            token
            for line in text.splitlines()
            if line.startswith(".PHONY:")
            for token in line.removeprefix(".PHONY:").split()
        }

        self.assertTrue(set(TARGETS).issubset(phony))
        self.assertIsNone(re.search(r"(?m)^asterion-verify:\s*$", text))
        self.assertNotIn("LEVEL", text)

    def test_default_targets_render_exact_asterion_commands(self) -> None:
        common = ("uv", "run", "asterion")
        provider = ("--provider", "dci-agent-lite")
        corpus = str(ROOT / "corpus")
        output = str(ROOT / "outputs/asterion-verification")

        self.assertEqual(
            dry_run("asterion-describe"),
            (*common, "describe", *provider),
        )
        self.assertEqual(
            dry_run("asterion-verify-preflight"),
            (
                *common,
                "verify",
                *provider,
                "--level",
                "preflight",
                "--env-file",
                ".env",
                "--corpus-root",
                corpus,
            ),
        )
        self.assertEqual(
            dry_run("asterion-verify-basic"),
            (
                *common,
                "verify",
                *provider,
                "--level",
                "basic",
                "--env-file",
                ".env",
                "--corpus-root",
                corpus,
                "--output-root",
                output,
            ),
        )
        self.assertEqual(
            dry_run("asterion-verify-acceptance"),
            (*common, "verify", *provider, "--level", "acceptance"),
        )
        self.assertEqual(
            dry_run("asterion-verify-complete"),
            (
                *common,
                "verify",
                *provider,
                "--level",
                "complete",
                "--env-file",
                ".env",
                "--corpus-root",
                corpus,
                "--output-root",
                output,
            ),
        )

    def test_variables_override_basic_target_without_shell_evaluation(self) -> None:
        self.assertEqual(
            dry_run(
                "asterion-verify-basic",
                "ASTERION_PROVIDER=fixture-provider",
                "ASTERION_ENV_FILE=fixture.env",
                "ASTERION_CORPUS_ROOT=/tmp/fixture-corpus",
                "ASTERION_VERIFY_OUTPUT_ROOT=/tmp/fixture-output",
            ),
            (
                "uv",
                "run",
                "asterion",
                "verify",
                "--provider",
                "fixture-provider",
                "--level",
                "basic",
                "--env-file",
                "fixture.env",
                "--corpus-root",
                "/tmp/fixture-corpus",
                "--output-root",
                "/tmp/fixture-output",
            ),
        )


if __name__ == "__main__":
    unittest.main()
