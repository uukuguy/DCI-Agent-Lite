from __future__ import annotations

import io
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.cli import _parser
from asterion.dci.cli import main
from asterion.dci.artifacts import DciConversationFeatures
from asterion.dci.evaluation import DciEvaluationError
from asterion.dci.run import DciRunError, DciRunRequest, DciRunResult
from asterion.runtime.host import RunEvent


ROOT = Path(__file__).resolve().parents[1]


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
    def test_run_generates_distinct_default_ids_and_destinations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch("asterion.dci.cli.run_pi_research") as run:
                run.side_effect = lambda _paths, request, *, output_dir: fixture_result(
                    output_dir
                )
                for _ in range(2):
                    self.assertEqual(
                        main(
                            ["run", "question"],
                            repo_root=root,
                            stdin=io.StringIO(),
                            stdout=io.StringIO(),
                            stderr=io.StringIO(),
                        ),
                        0,
                    )

        requests = [call.args[1] for call in run.call_args_list]
        destinations = [call.kwargs["output_dir"] for call in run.call_args_list]
        self.assertNotEqual(requests[0].run_id, requests[1].run_id)
        self.assertNotEqual(destinations[0], destinations[1])
        self.assertTrue(
            all(request.run_id.startswith("asterion-dci-") for request in requests)
        )

    def test_run_rejects_explicit_destination_collision_before_pi(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            collision = root / "outputs" / "asterion-dci-runs" / "stable"
            collision.mkdir(parents=True)
            with patch("asterion.dci.cli.run_pi_research") as run:
                code = main(
                    ["run", "--run-id", "stable", "question"],
                    repo_root=root,
                    stdin=io.StringIO(),
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )

        self.assertEqual(code, 2)
        run.assert_not_called()

    def test_run_question_sources_have_file_tokens_stdin_priority(self) -> None:
        class TtyInput(io.StringIO):
            def isatty(self) -> bool:
                return True

            def read(self, *args: object, **kwargs: object) -> str:
                raise AssertionError("TTY stdin must not be read")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            question_file = root / "question.txt"
            question_file.write_text("from file\n", encoding="utf-8")
            cases = (
                (
                    [
                        "run",
                        "--question-file",
                        str(question_file.resolve()),
                        "ignored",
                        "tokens",
                    ],
                    io.StringIO("ignored stdin"),
                    "from file",
                ),
                (
                    ["run", "multiple", "question", "tokens"],
                    io.StringIO("ignored stdin"),
                    "multiple question tokens",
                ),
                (["run"], io.StringIO("from stdin\n"), "from stdin"),
            )
            with patch("asterion.dci.cli.run_pi_research") as run:
                run.side_effect = lambda _paths, request, *, output_dir: fixture_result(
                    output_dir
                )
                for argv, stdin, expected in cases:
                    with self.subTest(argv=argv):
                        self.assertEqual(
                            main(
                                argv,
                                repo_root=root,
                                stdin=stdin,
                                stdout=io.StringIO(),
                                stderr=io.StringIO(),
                            ),
                            0,
                        )
                        self.assertEqual(run.call_args.args[1].question, expected)
                self.assertEqual(
                    main(
                        ["run"],
                        repo_root=root,
                        stdin=TtyInput(),
                        stdout=io.StringIO(),
                        stderr=io.StringIO(),
                    ),
                    2,
                )

    def test_run_resolves_resources_before_child_cwd_with_repo_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            invocation = root / "invocation"
            invocation.mkdir()
            child = root / "child"
            child.mkdir()
            local_prompt = invocation / "system.txt"
            local_prompt.write_text("local", encoding="utf-8")
            repo_append = root / "append.txt"
            repo_append.write_text("repo", encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(invocation)
                with patch("asterion.dci.cli.run_pi_research") as run:
                    run.return_value = fixture_result(root / "run")
                    code = main(
                        [
                            "run",
                            "--cwd",
                            str(child),
                            "--system-prompt-file",
                            "system.txt",
                            "--append-system-prompt-file",
                            "append.txt",
                            "question",
                        ],
                        repo_root=root,
                        stdin=io.StringIO(),
                        stdout=io.StringIO(),
                        stderr=io.StringIO(),
                    )
            finally:
                os.chdir(previous)

        self.assertEqual(code, 0)
        request = run.call_args.args[1]
        self.assertEqual(request.cwd, child.resolve())
        self.assertEqual(request.system_prompt_file, local_prompt.resolve())
        self.assertEqual(request.append_system_prompt_file, repo_append.resolve())

    def test_run_rejects_missing_unreadable_and_symlink_resources_before_pi(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            target = root / "target.txt"
            target.write_text("body", encoding="utf-8")
            symlink = root / "link.txt"
            symlink.symlink_to(target)
            unreadable = root / "unreadable.txt"
            unreadable.write_text("body", encoding="utf-8")
            unreadable.chmod(0)
            cases = (
                ["run", "--system-prompt-file", "missing.txt", "question"],
                ["run", "--system-prompt-file", str(unreadable.resolve()), "question"],
                ["run", "--question-file", str(symlink)],
            )
            with patch("asterion.dci.cli.run_pi_research") as run:
                for argv in cases:
                    with self.subTest(argv=argv):
                        self.assertEqual(
                            main(
                                argv,
                                repo_root=root,
                                stdin=io.StringIO(),
                                stdout=io.StringIO(),
                                stderr=io.StringIO(),
                            ),
                            2,
                        )
            unreadable.chmod(0o600)

        run.assert_not_called()

    def test_run_maps_all_conversation_controls_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch("asterion.dci.cli.run_pi_research") as run:
                run.return_value = fixture_result(root / "run")
                code = main(
                    [
                        "run",
                        "--conversation-clear-tool-results",
                        "--conversation-clear-tool-results-keep-last",
                        "0",
                        "--conversation-externalize-tool-results",
                        "--conversation-strip-thinking",
                        "--conversation-strip-usage",
                        "question",
                    ],
                    repo_root=root,
                    stdin=io.StringIO(),
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )

        self.assertEqual(code, 0)
        self.assertEqual(
            run.call_args.args[1].conversation_features,
            DciConversationFeatures(
                clear_tool_results=True,
                clear_tool_results_keep_last=0,
                externalize_tool_results=True,
                strip_thinking=True,
                strip_usage=True,
            ),
        )

    def test_asterion_examples_use_shared_env_and_package_command(self) -> None:
        for path in (
            ROOT / "scripts/examples/asterion_dci_basic_example.sh",
            ROOT / "scripts/examples/asterion_dci_runtime_context_example.sh",
        ):
            source = path.read_text()
            self.assertIn("uv run asterion-dci run", source)
            self.assertIn("asterion-dci run", source)
            self.assertIn("DCI_PROVIDER", source)
            self.assertNotIn("python -m dci.", source)

    def test_asterion_examples_validate_missing_provider_before_pi(self) -> None:
        launcher = subprocess.run(
            ["uv", "run", "asterion-dci", "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        self.assertNotEqual(launcher.returncode, 127)
        self.assertIn("usage: asterion-dci", launcher.stdout)
        self.assertNotIn("command not found", launcher.stdout + launcher.stderr)

        for path in (
            ROOT / "scripts/examples/asterion_dci_basic_example.sh",
            ROOT / "scripts/examples/asterion_dci_runtime_context_example.sh",
        ):
            with self.subTest(path=path.name):
                result = subprocess.run(
                    [
                        "bash",
                        "-c",
                        'source() { :; }; builtin source "$1"',
                        "bash",
                        str(path),
                    ],
                    cwd=ROOT,
                    env={"PATH": os.environ["PATH"]},
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("DCI_PROVIDER", result.stderr)
                self.assertNotIn("command not found", result.stdout + result.stderr)

    def test_asterion_examples_use_explicit_corpus_root_and_fail_before_launcher(
        self,
    ) -> None:
        examples = (
            (ROOT / "scripts/examples/asterion_dci_basic_example.sh", "wiki_corpus"),
            (
                ROOT / "scripts/examples/asterion_dci_runtime_context_example.sh",
                "bc_plus_docs",
            ),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            corpus_root = temporary_root / "corpus"
            corpus_root.mkdir()
            launcher_bin = temporary_root / "bin"
            launcher_bin.mkdir()
            launcher_log = temporary_root / "launcher.log"
            launcher = launcher_bin / "uv"
            launcher.write_text(
                '#!/usr/bin/env bash\nprintf \'%s\\n\' "$*" >> "$UV_CALLED"\n',
                encoding="utf-8",
            )
            launcher.chmod(0o755)

            for path, corpus_name in examples:
                with self.subTest(path=path.name, case="uses override"):
                    (corpus_root / corpus_name).mkdir()
                    result = subprocess.run(
                        ["bash", str(path)],
                        cwd=ROOT,
                        env={
                            "PATH": f"{launcher_bin}:{os.environ['PATH']}",
                            "DCI_PROVIDER": "test-provider",
                            "DCI_MODEL": "test-model",
                            "ASTERION_DCI_CORPUS_ROOT": str(corpus_root),
                            "UV_CALLED": str(launcher_log),
                        },
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn(
                        f"--cwd {corpus_root / corpus_name}",
                        launcher_log.read_text(encoding="utf-8"),
                    )

            launcher_log.unlink()
            missing_root = temporary_root / "missing-corpus"
            result = subprocess.run(
                ["bash", str(examples[0][0])],
                cwd=ROOT,
                env={
                    "PATH": f"{launcher_bin}:{os.environ['PATH']}",
                    "DCI_PROVIDER": "test-provider",
                    "DCI_MODEL": "test-model",
                    "ASTERION_DCI_CORPUS_ROOT": str(missing_root),
                    "UV_CALLED": str(launcher_log),
                },
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Asterion DCI corpus directory does not exist", result.stderr)
            self.assertFalse(launcher_log.exists())

            for path, corpus_name in examples:
                with self.subTest(path=path.name, case="rejects relative override"):
                    relative_root = temporary_root / "relative"
                    (relative_root / corpus_name).mkdir(parents=True, exist_ok=True)
                    result = subprocess.run(
                        ["bash", str(path)],
                        cwd=temporary_root,
                        env={
                            "PATH": f"{launcher_bin}:{os.environ['PATH']}",
                            "DCI_PROVIDER": "test-provider",
                            "DCI_MODEL": "test-model",
                            "ASTERION_DCI_CORPUS_ROOT": "relative",
                            "UV_CALLED": str(launcher_log),
                        },
                        capture_output=True,
                        text=True,
                        timeout=30,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(
                        "ASTERION_DCI_CORPUS_ROOT must be an absolute path",
                        result.stderr,
                    )
                    self.assertFalse(launcher_log.exists())

    def test_run_uses_shared_defaults_and_explicit_runtime_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch.dict(
                os.environ,
                {"DCI_PROVIDER": "openai", "DCI_MODEL": "gpt-test"},
                clear=True,
            ):
                with patch("asterion.dci.cli.run_pi_research") as run:
                    run.return_value = fixture_result(root / "run")
                    code = main(
                        [
                            "run",
                            "--runtime-context-level",
                            "level3",
                            "--thinking-level",
                            "high",
                            "question",
                        ],
                        repo_root=root,
                        stdout=io.StringIO(),
                        stderr=io.StringIO(),
                    )

        self.assertEqual(code, 0)
        request = run.call_args.args[1]
        self.assertEqual((request.provider, request.model), ("openai", "gpt-test"))
        self.assertEqual(
            (request.runtime_context_level, request.thinking_level), ("level3", "high")
        )

    def test_run_explicit_options_override_shared_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch.dict(
                os.environ,
                {"DCI_PROVIDER": "environment", "DCI_MODEL": "environment-model"},
                clear=True,
            ):
                with patch("asterion.dci.cli.run_pi_research") as run:
                    run.return_value = fixture_result(root / "run")
                    code = main(
                        [
                            "run",
                            "--provider",
                            "openai",
                            "--model",
                            "cli-model",
                            "--tools",
                            "read",
                            "--rpc-timeout-seconds",
                            "42",
                            "--node-max-old-space-size-mb",
                            "4096",
                            "--keep-session",
                            "--extra-arg=--verbose",
                            "question",
                        ],
                        repo_root=root,
                        stdout=io.StringIO(),
                        stderr=io.StringIO(),
                    )

        self.assertEqual(code, 0)
        request = run.call_args.args[1]
        self.assertEqual(
            (request.provider, request.model, request.tools),
            ("openai", "cli-model", "read"),
        )
        self.assertEqual(request.timeout_seconds, 42.0)
        self.assertEqual(request.node_max_old_space_size_mb, 4096)
        self.assertTrue(request.keep_session)
        self.assertEqual(request.extra_args, ("--verbose",))

    def test_run_redacts_invalid_shared_runtime_configuration(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch.dict(
                os.environ, {"DCI_RPC_TIMEOUT_SECONDS": "credential=secret"}, clear=True
            ):
                with patch("asterion.dci.cli.run_pi_research") as run:
                    stderr = io.StringIO()
                    code = main(
                        ["run", "question"],
                        repo_root=root,
                        stdout=io.StringIO(),
                        stderr=stderr,
                    )

        self.assertEqual(code, 2)
        run.assert_not_called()
        self.assertEqual(stderr.getvalue(), "DCI Pi execution failed\n")

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
                        "runtime_context_level": None,
                        "thinking_level": None,
                        "node_max_old_space_size_mb": None,
                        "keep_session": False,
                        "resume_count": 0,
                    }
                ),
                encoding="utf-8",
            )
            resumed = DciRunRequest(
                run_id="prior-run",
                question="question",
                cwd=root,
                provider="anthropic",
                model="fixture-model",
                max_turns=6,
                resume=True,
            )
            with (
                patch(
                    "asterion.dci.cli.resume_request_from_output_dir",
                    return_value=resumed,
                ),
                patch("asterion.dci.cli.run_pi_research") as run,
            ):
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
            with patch(
                "asterion.dci.cli.evaluate_run_directory",
                return_value={"is_correct": True},
            ):
                stdout = io.StringIO()
                code = main(
                    [
                        "evaluate",
                        "--output-dir",
                        str(root / "run"),
                        "--gold-answer",
                        "gold",
                    ],
                    repo_root=root,
                    stdout=stdout,
                    stderr=io.StringIO(),
                )

        self.assertEqual(code, 0)
        self.assertEqual(
            stdout.getvalue(),
            f"output_dir={root / 'run'}\nis_correct=True\nevaluation_uri=eval_result.json\n",
        )

    def test_evaluate_redacts_artifact_io_failure(self) -> None:
        with patch(
            "asterion.dci.cli.evaluate_run_directory",
            side_effect=OSError("credential=synthetic-secret"),
        ):
            stdout = io.StringIO()
            stderr = io.StringIO()
            code = main(
                ["evaluate", "--output-dir", "run", "--gold-answer", "gold"],
                stdout=stdout,
                stderr=stderr,
            )

        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "DCI evaluation failed\n")
        self.assertNotIn("synthetic-secret", stdout.getvalue() + stderr.getvalue())

    def test_benchmark_maps_shared_runtime_options_without_generic_cli_changes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch("asterion.dci.cli.run_benchmark") as benchmark:
                benchmark.return_value = type(
                    "Result", (), {"output_root": root / "out", "counts": {"total": 1}}
                )()
                self.assertEqual(
                    main(
                        [
                            "benchmark",
                            "--dataset",
                            "data.jsonl",
                            "--output-root",
                            "out",
                            "--cwd",
                            str(root),
                            "--provider",
                            "openai",
                            "--model",
                            "gpt-test",
                            "--tools",
                            "read",
                            "--rpc-timeout-seconds",
                            "45",
                            "--runtime-context-level",
                            "level3",
                            "--thinking-level",
                            "high",
                            "--node-max-old-space-size-mb",
                            "4096",
                            "--keep-session",
                            "--extra-arg=--verbose",
                            "--limit",
                            "1",
                        ],
                        repo_root=root,
                        stdout=io.StringIO(),
                        stderr=io.StringIO(),
                    ),
                    0,
                )

        self.assertTrue(benchmark.called)
        request = benchmark.call_args.args[0]
        self.assertEqual(request.limit, 1)
        self.assertEqual(
            (
                request.runtime_options.provider,
                request.runtime_options.model,
                request.runtime_options.tools,
                request.runtime_options.timeout_seconds,
                request.runtime_options.runtime_context_level,
                request.runtime_options.thinking_level,
                request.runtime_options.node_max_old_space_size_mb,
                request.runtime_options.keep_session,
                request.runtime_options.extra_args,
            ),
            (
                "openai",
                "gpt-test",
                "read",
                45.0,
                "level3",
                "high",
                4096,
                True,
                ("--verbose",),
            ),
        )

    def test_benchmark_redacts_native_and_artifact_failures(self) -> None:
        for failure in (
            DciRunError("credential=synthetic-secret"),
            DciEvaluationError("credential=synthetic-secret"),
            OSError("credential=synthetic-secret"),
        ):
            with self.subTest(failure=type(failure).__name__):
                with patch("asterion.dci.cli.run_benchmark", side_effect=failure):
                    stdout = io.StringIO()
                    stderr = io.StringIO()
                    code = main(
                        [
                            "benchmark",
                            "--dataset",
                            "data.jsonl",
                            "--output-root",
                            "out",
                        ],
                        stdout=stdout,
                        stderr=stderr,
                    )

                self.assertEqual(code, 2)
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(stderr.getvalue(), "DCI benchmark failed\n")
                self.assertNotIn(
                    "synthetic-secret", stdout.getvalue() + stderr.getvalue()
                )

    def test_cli_rejects_invalid_resume_without_calling_pi(self) -> None:
        stderr = io.StringIO()
        self.assertEqual(main(["run", "--resume", "question"], stderr=stderr), 2)
        self.assertIn("use asterion-dci resume", stderr.getvalue())

    def test_run_evaluates_native_result_and_redacts_evaluation_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch("asterion.dci.cli.run_pi_research") as run:
                run.return_value = fixture_result(root / "run")
                with patch(
                    "asterion.dci.cli.evaluate_run_directory",
                    return_value={"is_correct": True},
                ) as evaluate:
                    stdout = io.StringIO()
                    code = main(
                        ["run", "--eval-answer", "gold", "question"],
                        repo_root=root,
                        stdout=stdout,
                        stderr=io.StringIO(),
                    )

        self.assertEqual(code, 0)
        self.assertEqual(evaluate.call_args.kwargs["gold_answer"], "gold")
        self.assertEqual(
            stdout.getvalue(),
            f"output_dir={root / 'run'}\nis_correct=True\nevaluation_uri=eval_result.json\n",
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with patch(
                "asterion.dci.cli.run_pi_research",
                return_value=fixture_result(root / "run"),
            ):
                with patch(
                    "asterion.dci.cli.evaluate_run_directory",
                    side_effect=DciEvaluationError("credential=secret"),
                ):
                    stderr = io.StringIO()
                    code = main(
                        ["run", "--eval-answer", "gold", "question"],
                        repo_root=root,
                        stdout=io.StringIO(),
                        stderr=stderr,
                    )

        self.assertEqual(code, 2)
        self.assertEqual(stderr.getvalue(), "DCI evaluation failed\n")

    def test_product_help_is_separate_from_the_generic_cli(self) -> None:
        stdout = io.StringIO()
        self.assertEqual(main(["--help"], stdout=stdout, stderr=io.StringIO()), 0)
        self.assertIn("system-prompt", stdout.getvalue())
        self.assertNotIn("dci", _parser().format_help().lower())

    def test_system_prompt_failure_is_publicly_safe(self) -> None:
        with patch(
            "asterion.dci.cli.render_pi_system_prompt",
            side_effect=RuntimeError("provider detail"),
        ):
            stderr = io.StringIO()
            code = main(["system-prompt"], stderr=stderr)

        self.assertEqual(code, 2)
        self.assertIn("DCI system prompt generation failed", stderr.getvalue())
        self.assertNotIn("provider detail", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
