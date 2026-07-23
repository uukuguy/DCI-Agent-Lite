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
    "asterion-integration-acceptance",
)


def dry_run_lines(target: str, *assignments: str) -> tuple[tuple[str, ...], ...]:
    completed = subprocess.run(
        ["make", "--no-print-directory", "-n", target, *assignments],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    rendered = completed.stdout.replace("\\\n", " ")
    return tuple(
        tuple(shlex.split(line))
        for line in rendered.splitlines()
        if line.strip()
    )


def dry_run(target: str, *assignments: str) -> tuple[str, ...]:
    return dry_run_lines(target, *assignments)[-1]


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

    def test_default_targets_delegate_then_render_exact_asterion_commands(self) -> None:
        common = ("uv", "run", "asterion")
        provider = ("--provider", "dci-agent-lite")
        corpus = str(ROOT / "corpus")
        output = str(ROOT / "outputs/asterion-verification")
        delegated_args = {
            "asterion-describe": "",
            "asterion-verify-preflight": (
                f'--env-file ".env" --corpus-root "{corpus}"'
            ),
            "asterion-verify-basic": (
                f'--env-file ".env" --corpus-root "{corpus}" --output-root "{output}"'
            ),
            "asterion-verify-acceptance": "",
            "asterion-verify-complete": (
                f'--env-file ".env" --corpus-root "{corpus}" --output-root "{output}"'
            ),
        }
        for target, arguments in delegated_args.items():
            with self.subTest(target=target):
                delegated = dry_run_lines(target)[0]
                self.assertEqual(Path(delegated[0]).name, "make")
                self.assertEqual(
                    delegated[1:],
                    (
                        "-C",
                        "asterion",
                        target,
                        "ASTERION_PROVIDER=dci-agent-lite",
                        f"ASTERION_ARGS={arguments}",
                    ),
                )

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

    def test_integration_acceptance_is_explicit_exact_and_provider_free(self) -> None:
        text = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^asterion-integration-acceptance:\s*$")
        self.assertRegex(text, r"(?m)^asterion-verify-acceptance:\s*$")
        self.assertEqual(
            dry_run("asterion-integration-acceptance"),
            ("uv", "run", "python", "tools/verify_asterion_dci_product.py"),
        )
        for target in (
            "asterion-describe",
            "asterion-verify-acceptance",
            "asterion-integration-acceptance",
        ):
            rendered = "\n".join(" ".join(line) for line in dry_run_lines(target))
            with self.subTest(target=target):
                self.assertNotIn("--level basic", rendered)
                self.assertNotIn("--level complete", rendered)
                self.assertNotIn("--authorize-full", rendered)
                self.assertNotIn("API_KEY", rendered)

        self.assertNotIn("uv run asterion describe", text)
        self.assertNotIn("uv run asterion verify", text)

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
