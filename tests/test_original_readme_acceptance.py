from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from tools.verify_original_readme import (
    _prepare_private_root,
    validate_context_contract,
    validate_readme_contract,
    verify_original_readme_main,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class OriginalReadmeAcceptanceTests(unittest.TestCase):
    def test_bounded_output_root_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / "target"
            target.mkdir()
            link = root / "linked-output"
            link.symlink_to(target, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "output root"):
                _prepare_private_root(link)

    def test_literal_quick_start_and_context_commands(self) -> None:
        contract = validate_readme_contract(REPO_ROOT / "README.md")

        self.assertNotIn("--provider", contract["terminal"])
        self.assertNotIn("--model", contract["terminal"])
        self.assertNotIn("--provider", contract["programmatic"])
        self.assertNotIn("--model", contract["programmatic"])
        self.assertIn("src/dci/benchmark/pi_rpc_runner.py", contract["terminal"])
        self.assertIn("src/dci/benchmark/pi_rpc_runner.py", contract["programmatic"])
        self.assertIn("--provider openai-codex", contract["override"])
        self.assertIn("--model gpt-5.6-luna", contract["override"])
        self.assertEqual(
            set(contract["context_commands"]),
            {"level0", "level1", "level2", "level3", "level4"},
        )

    def test_local_context_contract_requires_every_behavior_and_digest(self) -> None:
        profiles = REPO_ROOT / "asterion/src/asterion/dci/resources/context-profiles.json"
        manifest = REPO_ROOT / "asterion/src/asterion/dci/resources/pi/context-extension-manifest.json"
        extension = REPO_ROOT / "asterion/src/asterion/dci/resources/pi/dci-context-extension.ts"
        validate_context_contract(profiles, manifest, extension)

        source = extension.read_text(encoding="utf-8")
        for evidence in (
            "compactionCount",
            "summaryAttempts",
            "summarySuppressed",
            "dci-context-telemetry",
            'event.reason === "resume"',
        ):
            with self.subTest(evidence=evidence), tempfile.TemporaryDirectory() as temp:
                changed = Path(temp) / "extension.ts"
                changed.write_text(source.replace(evidence, "missing-evidence", 1), encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "context contract"):
                    validate_context_contract(profiles, manifest, changed)

    def test_local_verifier_is_provider_free(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        result = verify_original_readme_main(
            ["--level", "local"],
            repo_root=REPO_ROOT,
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(result, 0, stderr.getvalue())
        self.assertIn("PASS", stdout.getvalue())
        self.assertIn("Agent operations: 0", stdout.getvalue())
        self.assertIn("Judge operations: 0", stdout.getvalue())
        self.assertIn("Full dataset ran: no", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
