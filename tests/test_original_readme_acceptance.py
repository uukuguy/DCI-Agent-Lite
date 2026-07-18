from __future__ import annotations

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools.verify_original_readme import (
    _bounded_context_evidence,
    _prepare_private_root,
    _runner_command,
    validate_readme_contract,
    verify_original_readme_main,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class OriginalReadmeAcceptanceTests(unittest.TestCase):
    def test_bounded_context_command_uses_pressure_preludes_and_bounds(self) -> None:
        command = _runner_command(
            REPO_ROOT,
            Path("/private/run"),
            "level4",
            corpus_dir=Path("/private/corpus"),
        )

        self.assertEqual(command.count("--prelude-question"), 12)
        self.assertIn("--runtime", command)
        self.assertIn("pi", command)
        self.assertIn("--max-turns", command)
        self.assertIn("--rpc-timeout-seconds", command)
        self.assertIn("pressure.txt", command[-1])

    def test_bounded_captures_child_bodies_and_reports_only_hashes(self) -> None:
        calls = []

        def fake_executor(command, **kwargs):
            calls.append((command, kwargs))
            output = Path(command[command.index("--output-dir") + 1])
            output.mkdir(mode=0o700)
            protocol = output / "protocol"
            protocol.mkdir(mode=0o700)
            files = {
                "question.txt": "question-canary",
                "final.txt": "answer-canary",
                "conversation_full.json": "{}",
                "effective-config.json": json.dumps({"identity_sha256": "b" * 64}),
                "protocol/attempt-0001.events.jsonl": "{}\n",
            }
            for name, body in files.items():
                path = output / name
                path.write_text(body, encoding="utf-8")
                path.chmod(0o600)
            profile = next(
                (value for value in ("level3", "level4") if value in command), None
            )
            if profile:
                telemetry = {
                    "type": "custom",
                    "customType": "dci-context-telemetry",
                    "data": {
                        "profile": profile,
                        "compactionCount": 1,
                        "summaryAttempts": 1 if profile == "level4" else 0,
                        "summarySuccesses": 1 if profile == "level4" else 0,
                        "summarySuppressed": False,
                    },
                }
                session = output / "pi-session.jsonl"
                session.write_text(json.dumps(telemetry) + "\n", encoding="utf-8")
                session.chmod(0o600)
            return subprocess.CompletedProcess(command, 0, "answer-canary", "stderr-canary")

        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            env_file = root / "env"
            env_file.write_text("DCI_RUNTIME=pi\n", encoding="utf-8")
            stdout = io.StringIO()
            stderr = io.StringIO()
            result = verify_original_readme_main(
                [
                    "--level",
                    "bounded",
                    "--env-file",
                    str(env_file),
                    "--output-root",
                    str(root / "output"),
                ],
                repo_root=REPO_ROOT,
                stdout=stdout,
                stderr=stderr,
                executor=fake_executor,
                raise_errors=True,
            )
            self.assertEqual(result, 0, stderr.getvalue())
            report = json.loads(
                (root / "output/original-readme-acceptance.json").read_text()
            )

        self.assertTrue(all(kwargs["capture_output"] for _cmd, kwargs in calls))
        self.assertTrue(all(kwargs["umask"] == 0o077 for _cmd, kwargs in calls))
        self.assertNotIn("answer-canary", stdout.getvalue())
        self.assertNotIn("stderr-canary", stdout.getvalue())
        self.assertEqual(report["command_ids"], ["quick-start-programmatic", "context-level3", "context-level4"])
        self.assertEqual(report["agent_operations"], 3)
        self.assertEqual(report["judge_operations"], 0)
        self.assertEqual(
            set(report),
            {"command_ids", "agent_operations", "judge_operations", "commands"},
        )
        self.assertTrue(
            all(
                set(command) == {"command_id", "effective_config_sha256", "private_artifact_sha256"}
                for command in report["commands"]
            )
        )

    def test_bounded_context_evidence_requires_observed_counters(self) -> None:
        base = {
            "profile": "level3",
            "compactions": 0,
            "summary_attempts": 0,
            "summary_successes": 0,
            "summary_suppressed": False,
            "extension_sha256": "a" * 64,
        }
        with self.assertRaisesRegex(ValueError, "bounded context evidence"):
            _bounded_context_evidence("level3", base)
        with self.assertRaisesRegex(ValueError, "bounded context evidence"):
            _bounded_context_evidence(
                "level4", {**base, "profile": "level4", "compactions": 1}
            )

        self.assertEqual(
            _bounded_context_evidence(
                "level4",
                {
                    **base,
                    "profile": "level4",
                    "compactions": 1,
                    "summary_attempts": 1,
                    "summary_successes": 1,
                },
            )["summary_successes"],
            1,
        )

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
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        context_section = readme.split("## 🚀 Context Management Strategies", 1)[1].split("## 🎯", 1)[0]

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
        self.assertIn("Original DCI ships its own", context_section)
        self.assertNotIn("Asterion ships", context_section)

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
