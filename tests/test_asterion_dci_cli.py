from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.cli import _parser
from asterion.dci.cli import main
from asterion.dci.run import DciRunResult
from asterion.runtime.host import RunEvent


def fixture_result(output_dir: Path) -> DciRunResult:
    return DciRunResult(
        output_dir=output_dir,
        final_text="answer",
        events=(
            RunEvent("run", 1, "run.started", {"capabilities": []}),
            RunEvent("run", 2, "run.completed", {"status": "completed"}),
        ),
        status="completed",
    )


class AsterionDciCliTests(unittest.TestCase):
    def test_run_maps_original_single_run_options_to_domain_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch("asterion.dci.cli.run_pi_research") as run:
                run.return_value = fixture_result(root / "run")
                stdout = io.StringIO()
                code = main(
                    [
                        "run",
                        "--cwd",
                        str(root),
                        "--tools",
                        "read,bash",
                        "--max-turns",
                        "6",
                        "--show-tools",
                        "--extra-arg",
                        "--thinking high",
                        "question",
                    ],
                    repo_root=root,
                    stdout=stdout,
                    stderr=io.StringIO(),
                )

        self.assertEqual(code, 0)
        request = run.call_args.args[1]
        self.assertEqual(request.tools, "read,bash")
        self.assertEqual(request.max_turns, 6)
        self.assertEqual(request.extra_args, ("--thinking high",))
        self.assertEqual(
            stdout.getvalue(),
            f"output_dir={root / 'run'}\nstatus=completed\nfinal_answer_uri=final.txt\n",
        )

    def test_resume_maps_existing_run_directory_to_a_resume_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "run"
            output_dir.mkdir()
            (output_dir / "state.json").write_text(
                json.dumps(
                    {
                        "run_id": "prior-run",
                        "status": "failed",
                        "question": "question",
                        "cwd": str(root),
                        "provider": "anthropic",
                        "model": "fixture-model",
                        "tools": "read,bash",
                        "max_turns": 6,
                        "resume_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            with patch("asterion.dci.cli.run_pi_research") as run:
                run.return_value = fixture_result(output_dir)
                stdout = io.StringIO()
                code = main(
                    ["resume", "--output-dir", str(output_dir)],
                    repo_root=root,
                    stdout=stdout,
                    stderr=io.StringIO(),
                )

        self.assertEqual(code, 0)
        request = run.call_args.args[1]
        self.assertTrue(request.resume)
        self.assertEqual(request.run_id, "prior-run")
        self.assertEqual(request.question, "question")
        self.assertEqual(request.cwd, root)
        self.assertEqual(request.provider, "anthropic")
        self.assertEqual(request.max_turns, 6)
        self.assertEqual(
            stdout.getvalue(),
            f"output_dir={output_dir}\nstatus=completed\nfinal_answer_uri=final.txt\n",
        )

    def test_resume_rejects_invalid_state_without_starting_pi(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            output_dir = root / "run"
            output_dir.mkdir()
            (output_dir / "state.json").write_text("{}", encoding="utf-8")
            with patch("asterion.dci.cli.run_pi_research") as run:
                stderr = io.StringIO()
                code = main(
                    ["resume", "--output-dir", str(output_dir)],
                    repo_root=root,
                    stdout=io.StringIO(),
                    stderr=stderr,
                )

        self.assertEqual(code, 2)
        run.assert_not_called()
        self.assertEqual(stderr.getvalue(), "DCI Pi execution failed\n")

    def test_evaluate_maps_native_run_directory_without_exposing_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch("asterion.dci.cli.evaluate_run_directory", return_value={"is_correct": True}):
                stdout = io.StringIO()
                code = main(
                    ["evaluate", "--output-dir", str(root / "run"), "--gold-answer", "gold"],
                    repo_root=root,
                    stdout=stdout,
                    stderr=io.StringIO(),
                )

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), f"output_dir={root / 'run'}\nis_correct=True\nevaluation_uri=eval_result.json\n")

    def test_benchmark_maps_explicit_dataset_without_generic_cli_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch("asterion.dci.cli.run_benchmark") as benchmark:
                benchmark.return_value = type("Result", (), {"output_root": root / "out", "counts": {"total": 1}})()
                self.assertEqual(main(["benchmark", "--dataset", "data.jsonl", "--output-root", "out", "--cwd", str(root)], repo_root=root, stdout=io.StringIO(), stderr=io.StringIO()), 0)

        self.assertTrue(benchmark.called)

    def test_cli_rejects_deferred_features_without_calling_pi(self) -> None:
        stderr = io.StringIO()
        self.assertEqual(main(["run", "--resume", "question"], stderr=stderr), 2)
        self.assertIn("use asterion-dci resume", stderr.getvalue())
        stderr = io.StringIO()
        self.assertEqual(main(["run", "--eval-answer", "gold", "question"], stderr=stderr), 2)
        self.assertIn("evaluation is not available until AF-200", stderr.getvalue())

    def test_product_help_is_separate_from_the_generic_cli(self) -> None:
        stdout = io.StringIO()
        self.assertEqual(main(["--help"], stdout=stdout, stderr=io.StringIO()), 0)
        self.assertIn("system-prompt", stdout.getvalue())
        self.assertNotIn("dci", _parser().format_help().lower())

    def test_system_prompt_failure_is_publicly_safe(self) -> None:
        with patch("asterion.dci.cli.render_pi_system_prompt", side_effect=RuntimeError("provider detail")):
            stderr = io.StringIO()
            code = main(["system-prompt"], stderr=stderr)

        self.assertEqual(code, 2)
        self.assertIn("DCI system prompt generation failed", stderr.getvalue())
        self.assertNotIn("provider detail", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
