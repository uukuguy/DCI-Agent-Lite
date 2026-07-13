from __future__ import annotations

import io
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

    def test_cli_rejects_deferred_features_without_calling_pi(self) -> None:
        stderr = io.StringIO()
        self.assertEqual(main(["run", "--resume", "question"], stderr=stderr), 2)
        self.assertIn("resume is not available until AF-190", stderr.getvalue())
        stderr = io.StringIO()
        self.assertEqual(main(["run", "--eval-answer", "gold", "question"], stderr=stderr), 2)
        self.assertIn("evaluation is not available until AF-200", stderr.getvalue())
        stderr = io.StringIO()
        self.assertEqual(main(["benchmark"], stderr=stderr), 2)
        self.assertIn("benchmark is not available until AF-200", stderr.getvalue())

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
