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
    def test_terminal_maps_operator_controls_without_artifacts(self) -> None:
        class TtyStream(io.StringIO):
            def isatty(self) -> bool:
                return True

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            prompt = root / "prompt.txt"
            prompt.write_text("prompt", encoding="utf-8")
            with patch("asterion.dci.cli.run_pi_terminal", return_value=23) as terminal:
                code = main(
                    [
                        "terminal",
                        "--cwd",
                        str(root),
                        "--provider",
                        "provider",
                        "--model",
                        "model --tools bash",
                        "--tools",
                        "read,bash",
                        "--system-prompt-file",
                        str(prompt),
                        "--thinking-level",
                        "high --model injected",
                        "--node-max-old-space-size-mb",
                        "4096",
                        "--extra-arg=--custom value",
                        "initial",
                        "question",
                    ],
                    repo_root=root,
                    stdin=TtyStream(),
                    stdout=TtyStream(),
                    stderr=io.StringIO(),
                )

        self.assertEqual(code, 23)
        kwargs = terminal.call_args.kwargs
        self.assertEqual(kwargs["cwd"], root)
        self.assertEqual(kwargs["model"], "model --tools bash")
        self.assertEqual(kwargs["thinking_level"], "high --model injected")
        self.assertEqual(kwargs["extra_args"], ("--custom value",))
        self.assertEqual(kwargs["initial_question"], "initial question")
        self.assertEqual(kwargs["system_prompt_file"], prompt)

    def test_terminal_question_file_has_priority_and_resources_are_preflighted(
        self,
    ) -> None:
        class TtyStream(io.StringIO):
            def isatty(self) -> bool:
                return True

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            question = root / "question.txt"
            question.write_text("from file\n", encoding="utf-8")
            with patch("asterion.dci.cli.run_pi_terminal", return_value=0) as terminal:
                self.assertEqual(
                    main(
                        ["terminal", "--question-file", str(question), "ignored"],
                        repo_root=root,
                        stdin=TtyStream(),
                        stdout=TtyStream(),
                        stderr=io.StringIO(),
                    ),
                    0,
                )
            self.assertEqual(terminal.call_args.kwargs["initial_question"], "from file")

            unsafe = root / "unsafe.txt"
            unsafe.symlink_to(question)
            with patch("asterion.dci.cli.run_pi_terminal") as terminal:
                for argv in (
                    ["terminal", "--question-file", str(unsafe)],
                    ["terminal", "--system-prompt-file", "missing.txt"],
                ):
                    with self.subTest(argv=argv):
                        self.assertEqual(
                            main(
                                argv,
                                repo_root=root,
                                stdin=TtyStream(),
                                stdout=TtyStream(),
                                stderr=io.StringIO(),
                            ),
                            2,
                        )
            terminal.assert_not_called()

    def test_terminal_redacts_node_and_child_failures(self) -> None:
        class TtyStream(io.StringIO):
            def isatty(self) -> bool:
                return True

        with tempfile.TemporaryDirectory() as temporary_directory:
            stderr = io.StringIO()
            with patch(
                "asterion.dci.cli.run_pi_terminal",
                side_effect=RuntimeError("sentinel-secret-node-detail"),
            ):
                code = main(
                    ["terminal"],
                    repo_root=Path(temporary_directory),
                    stdin=TtyStream(),
                    stdout=TtyStream(),
                    stderr=stderr,
                )

        self.assertEqual(code, 2)
        self.assertEqual(stderr.getvalue(), "DCI Pi terminal failed\n")
        self.assertNotIn("sentinel", stderr.getvalue())

    def test_terminal_rejects_non_tty_and_runner_only_options_before_child(
        self,
    ) -> None:
        class TtyStream(io.StringIO):
            def isatty(self) -> bool:
                return True

        cases = (
            (["terminal"], io.StringIO(), TtyStream()),
            (["terminal"], TtyStream(), io.StringIO()),
            (["terminal", "--rpc-timeout-seconds", "1"], TtyStream(), TtyStream()),
            (["terminal", "--max-turns", "1"], TtyStream(), TtyStream()),
            (["terminal", "--output-dir", "run"], TtyStream(), TtyStream()),
            (["terminal", "--no-session"], TtyStream(), TtyStream()),
        )
        with patch("asterion.dci.cli.run_pi_terminal") as terminal:
            for argv, stdin, stdout in cases:
                with self.subTest(argv=argv):
                    self.assertEqual(
                        main(
                            argv,
                            repo_root=Path.cwd(),
                            stdin=stdin,
                            stdout=stdout,
                            stderr=io.StringIO(),
                        ),
                        2,
                    )
        terminal.assert_not_called()

    def test_parse_failures_are_body_free_and_use_injected_error_stream(self) -> None:
        cases = (
            (
                [
                    "terminal",
                    "--node-max-old-space-size-mb",
                    "sentinel-secret-typed",
                ],
                "DCI Pi terminal failed\n",
            ),
            (
                ["terminal", "--output-dir=sentinel-secret-runner"],
                "DCI Pi terminal failed\n",
            ),
            (
                ["run", "--unknown=sentinel-secret-run"],
                "DCI Pi execution failed\n",
            ),
            (
                ["system-prompt", "--unknown=sentinel-secret-prompt"],
                "DCI system prompt generation failed\n",
            ),
            (
                ["benchmark", "--unknown=sentinel-secret-benchmark"],
                "DCI benchmark failed\n",
            ),
            (
                ["evaluate", "--unknown=sentinel-secret-evaluate"],
                "DCI evaluation failed\n",
            ),
            (
                ["resume", "--unknown=sentinel-secret-resume"],
                "DCI Pi execution failed\n",
            ),
        )
        for argv, expected in cases:
            with self.subTest(argv=argv):
                injected = io.StringIO()
                process_stderr = io.StringIO()
                with patch("sys.stderr", process_stderr):
                    code = main(argv, stderr=injected)
                self.assertEqual(code, 2)
                self.assertEqual(injected.getvalue(), expected)
                self.assertEqual(process_stderr.getvalue(), "")
                self.assertNotIn("sentinel", injected.getvalue())

        help_stdout = io.StringIO()
        help_stderr = io.StringIO()
        with patch("sys.stdout", io.StringIO()), patch("sys.stderr", io.StringIO()):
            self.assertEqual(
                main(
                    ["terminal", "--help"],
                    stdout=help_stdout,
                    stderr=help_stderr,
                ),
                0,
            )
        self.assertIn("--question-file", help_stdout.getvalue())
        self.assertEqual(help_stderr.getvalue(), "")

    def test_terminal_rejects_invalid_cwd_before_terminal_boundary(self) -> None:
        class TtyStream(io.StringIO):
            def isatty(self) -> bool:
                return True

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            file_path = root / "file"
            file_path.write_text("x", encoding="utf-8")
            target = root / "target"
            target.mkdir()
            symlink = root / "link"
            symlink.symlink_to(target, target_is_directory=True)
            unreadable = root / "unreadable"
            unreadable.mkdir()
            unreadable.chmod(0)
            with patch("asterion.dci.cli.run_pi_terminal") as terminal:
                for cwd in (root / "missing", file_path, symlink, unreadable):
                    with self.subTest(cwd=cwd):
                        self.assertEqual(
                            main(
                                ["terminal", "--cwd", str(cwd)],
                                repo_root=root,
                                stdin=TtyStream(),
                                stdout=TtyStream(),
                                stderr=io.StringIO(),
                            ),
                            2,
                        )
            unreadable.chmod(0o700)
        terminal.assert_not_called()

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

    def test_run_preflights_evaluation_answer_file_with_resource_precedence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            invocation = root / "invocation"
            invocation.mkdir()
            repo_answer = root / "gold.txt"
            repo_answer.write_text("repo answer", encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(invocation)
                with (
                    patch("asterion.dci.cli.run_pi_research") as run,
                    patch("asterion.dci.cli.evaluate_run_directory") as evaluate,
                ):
                    run.return_value = fixture_result(root / "run")
                    evaluate.return_value = {"is_correct": True}
                    self.assertEqual(
                        main(
                            ["run", "--eval-answer-file", "gold.txt", "question"],
                            repo_root=root,
                            stdin=io.StringIO(),
                            stdout=io.StringIO(),
                            stderr=io.StringIO(),
                        ),
                        0,
                    )
                    self.assertEqual(
                        evaluate.call_args.kwargs["gold_answer"], "repo answer"
                    )

                    local_answer = invocation / "gold.txt"
                    local_answer.write_text("local answer", encoding="utf-8")
                    self.assertEqual(
                        main(
                            ["run", "--eval-answer-file", "gold.txt", "question"],
                            repo_root=root,
                            stdin=io.StringIO(),
                            stdout=io.StringIO(),
                            stderr=io.StringIO(),
                        ),
                        0,
                    )
                    self.assertEqual(
                        evaluate.call_args.kwargs["gold_answer"], "local answer"
                    )
            finally:
                os.chdir(previous)

    def test_run_rejects_unsafe_evaluation_answer_file_before_pi(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "answer.txt"
            target.write_text("answer", encoding="utf-8")
            link = root / "answer-link.txt"
            link.symlink_to(target)
            unreadable = root / "unreadable.txt"
            unreadable.write_text("answer", encoding="utf-8")
            unreadable.chmod(0)
            cases = ("missing.txt", str(link), str(unreadable))
            with patch("asterion.dci.cli.run_pi_research") as run:
                for resource in cases:
                    with self.subTest(resource=resource):
                        self.assertEqual(
                            main(
                                [
                                    "run",
                                    "--eval-answer-file",
                                    resource,
                                    "question",
                                ],
                                repo_root=root,
                                stdin=io.StringIO(),
                                stdout=io.StringIO(),
                                stderr=io.StringIO(),
                            ),
                            2,
                        )
            unreadable.chmod(0o600)

        run.assert_not_called()

    def test_system_prompt_preflights_append_resource_before_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            invocation = root / "invocation"
            invocation.mkdir()
            append = root / "append.txt"
            append.write_text("append", encoding="utf-8")
            previous = Path.cwd()
            try:
                os.chdir(invocation)
                with patch("asterion.dci.cli.render_pi_system_prompt") as render:
                    render.return_value = "prompt"
                    self.assertEqual(
                        main(
                            [
                                "system-prompt",
                                "--append-system-prompt-file",
                                "append.txt",
                            ],
                            repo_root=root,
                            stdout=io.StringIO(),
                            stderr=io.StringIO(),
                        ),
                        0,
                    )
                    self.assertEqual(render.call_args.args[3], append)

                    local_append = invocation / "append.txt"
                    local_append.write_text("local", encoding="utf-8")
                    self.assertEqual(
                        main(
                            [
                                "system-prompt",
                                "--append-system-prompt-file",
                                "append.txt",
                            ],
                            repo_root=root,
                            stdout=io.StringIO(),
                            stderr=io.StringIO(),
                        ),
                        0,
                    )
                    self.assertEqual(render.call_args.args[3], local_append)
            finally:
                os.chdir(previous)

    def test_system_prompt_rejects_unsafe_append_before_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            target = root / "append.txt"
            target.write_text("append", encoding="utf-8")
            link = root / "append-link.txt"
            link.symlink_to(target)
            unreadable = root / "unreadable.txt"
            unreadable.write_text("append", encoding="utf-8")
            unreadable.chmod(0)
            with patch("asterion.dci.cli.render_pi_system_prompt") as render:
                render.return_value = ""
                for resource in ("missing.txt", str(link), str(unreadable)):
                    with self.subTest(resource=resource):
                        stderr = io.StringIO()
                        self.assertEqual(
                            main(
                                [
                                    "system-prompt",
                                    "--append-system-prompt-file",
                                    resource,
                                ],
                                repo_root=root,
                                stdout=io.StringIO(),
                                stderr=stderr,
                            ),
                            2,
                        )
                        self.assertEqual(
                            stderr.getvalue(), "DCI system prompt generation failed\n"
                        )
            unreadable.chmod(0o600)

        render.assert_not_called()

    def test_run_redacts_destination_probe_oserror_before_pi(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            with (
                patch(
                    "asterion.dci.cli.Path.exists",
                    side_effect=PermissionError("credential=synthetic-secret"),
                ),
                patch("asterion.dci.cli.run_pi_research") as run,
            ):
                stderr = io.StringIO()
                code = main(
                    ["run", "question"],
                    repo_root=root,
                    stdin=io.StringIO(),
                    stdout=io.StringIO(),
                    stderr=stderr,
                )

        self.assertEqual(code, 2)
        run.assert_not_called()
        self.assertEqual(stderr.getvalue(), "DCI Pi execution failed\n")
        self.assertNotIn("synthetic-secret", stderr.getvalue())

    def test_commands_redact_invocation_cwd_oserror_before_any_boundary(self) -> None:
        cases = (
            (["run", "question"], "DCI Pi execution failed\n"),
            (["system-prompt"], "DCI system prompt generation failed\n"),
            (
                ["benchmark", "--dataset", "data.jsonl", "--output-root", "out"],
                "DCI benchmark failed\n",
            ),
            (
                ["evaluate", "--output-dir", "run", "--gold-answer", "gold"],
                "DCI evaluation failed\n",
            ),
            (["resume", "--output-dir", "run"], "DCI Pi execution failed\n"),
        )
        for argv, expected_error in cases:
            with self.subTest(argv=argv):
                with (
                    patch(
                        "asterion.dci.cli.Path.cwd",
                        side_effect=PermissionError("credential=setup-secret"),
                    ),
                    patch("asterion.dci.cli.run_pi_research") as run,
                    patch("asterion.dci.cli.render_pi_system_prompt") as render,
                    patch("asterion.dci.cli.run_benchmark") as benchmark,
                    patch("asterion.dci.cli.evaluate_run_directory") as evaluate,
                    patch("asterion.dci.cli.resume_request_from_output_dir") as resume,
                ):
                    stderr = io.StringIO()
                    code = main(
                        argv,
                        stdin=io.StringIO(),
                        stdout=io.StringIO(),
                        stderr=stderr,
                    )

            self.assertEqual(code, 2)
            self.assertEqual(stderr.getvalue(), expected_error)
            self.assertNotIn("setup-secret", stderr.getvalue())
            run.assert_not_called()
            render.assert_not_called()
            benchmark.assert_not_called()
            evaluate.assert_not_called()
            resume.assert_not_called()

    def test_run_and_resume_reject_symlink_output_paths_before_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            dangling_target = root / "dangling-target"
            dangling = root / "dangling-output"
            dangling.symlink_to(dangling_target, target_is_directory=True)
            real_parent = root / "real-parent"
            real_parent.mkdir()
            linked_parent = root / "linked-parent"
            linked_parent.symlink_to(real_parent, target_is_directory=True)
            cases = (
                (dangling, dangling_target),
                (linked_parent / "run", real_parent / "run"),
            )
            for supplied, forbidden_target in cases:
                with (
                    self.subTest(command="run", supplied=supplied),
                    patch("asterion.dci.cli.run_pi_research") as run,
                ):
                    stderr = io.StringIO()
                    code = main(
                        ["run", "--output-dir", str(supplied), "question"],
                        repo_root=root,
                        stdin=io.StringIO(),
                        stdout=io.StringIO(),
                        stderr=stderr,
                    )
                    self.assertEqual(code, 2)
                    self.assertEqual(stderr.getvalue(), "DCI Pi execution failed\n")
                    run.assert_not_called()
                    self.assertFalse(forbidden_target.exists())

                with (
                    self.subTest(command="resume", supplied=supplied),
                    patch("asterion.dci.cli.resume_request_from_output_dir") as resume,
                    patch("asterion.dci.cli.run_pi_research") as run,
                ):
                    stderr = io.StringIO()
                    code = main(
                        ["resume", "--output-dir", str(supplied)],
                        repo_root=root,
                        stdout=io.StringIO(),
                        stderr=stderr,
                    )
                    self.assertEqual(code, 2)
                    self.assertEqual(stderr.getvalue(), "DCI Pi execution failed\n")
                    resume.assert_not_called()
                    run.assert_not_called()
                    self.assertFalse(forbidden_target.exists())

    def test_default_and_benchmark_output_roots_preserve_symlinks_for_rejection(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            run_target = root / "run-target"
            run_link = root / "run-link"
            run_link.symlink_to(run_target, target_is_directory=True)
            with (
                patch.dict(
                    os.environ,
                    {"ASTERION_DCI_OUTPUT_ROOT": str(run_link)},
                    clear=True,
                ),
                patch("asterion.dci.cli.run_pi_research") as run,
            ):
                stderr = io.StringIO()
                self.assertEqual(
                    main(
                        ["run", "question"],
                        repo_root=root,
                        stdin=io.StringIO(),
                        stdout=io.StringIO(),
                        stderr=stderr,
                    ),
                    2,
                )
                self.assertEqual(stderr.getvalue(), "DCI Pi execution failed\n")
                run.assert_not_called()
                self.assertFalse(run_target.exists())

            benchmark_target = root / "benchmark-target"
            benchmark_link = root / "benchmark-link"
            benchmark_link.symlink_to(benchmark_target, target_is_directory=True)
            with patch("asterion.dci.cli.run_benchmark") as benchmark:
                stderr = io.StringIO()
                self.assertEqual(
                    main(
                        [
                            "benchmark",
                            "--dataset",
                            "data.jsonl",
                            "--output-root",
                            str(benchmark_link),
                        ],
                        repo_root=root,
                        stdout=io.StringIO(),
                        stderr=stderr,
                    ),
                    2,
                )
                self.assertEqual(stderr.getvalue(), "DCI benchmark failed\n")
                benchmark.assert_not_called()
                self.assertFalse(benchmark_target.exists())

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
            root = Path(temporary_directory).resolve()
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
            (root / "system.md").write_text("system")
            (root / "append.md").write_text("append")
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
                            "--max-concurrency",
                            "3",
                            "--max-turns",
                            "9",
                            "--system-prompt-file",
                            "system.md",
                            "--append-system-prompt-file",
                            "append.md",
                            "--conversation-clear-tool-results",
                            "--conversation-clear-tool-results-keep-last",
                            "2",
                            "--conversation-externalize-tool-results",
                            "--conversation-strip-thinking",
                            "--conversation-strip-usage",
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
        self.assertEqual(request.max_concurrency, 3)
        self.assertEqual(request.max_turns, 9)
        self.assertEqual(request.system_prompt_file, (root / "system.md").resolve())
        self.assertEqual(request.append_system_prompt_file, (root / "append.md").resolve())
        self.assertEqual(
            request.conversation_features,
            DciConversationFeatures(
                clear_tool_results=True,
                clear_tool_results_keep_last=2,
                externalize_tool_results=True,
                strip_thinking=True,
                strip_usage=True,
            ),
        )
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

    def test_benchmark_help_exposes_complete_source_and_asterion_controls(self) -> None:
        stdout = io.StringIO()
        self.assertEqual(
            main(
                ["benchmark", "--help"],
                repo_root=ROOT,
                stdout=stdout,
                stderr=io.StringIO(),
            ),
            0,
        )
        help_text = stdout.getvalue()
        for option in (
            "--dataset", "--output-root", "--profile", "--corpus", "--corpus-dir",
            "--provider", "--model", "--tools", "--max-turns", "--max-concurrency",
            "--limit", "--runtime-context-level", "--system-prompt-file",
            "--append-system-prompt-file", "--extra-arg", "--pi-extra-arg",
            "--thinking-level", "--pi-thinking-level", "--enable-ir", "--corpus-hint",
            "--judge-base-url", "--judge-api", "--judge-model", "--judge-api-key-env",
            "--judge-timeout-seconds", "--judge-max-output-tokens", "--judge-json-mode",
            "--judge-strict-json-schema", "--judge-responses-store", "--judge-thinking",
            "--judge-input-price-per-1m", "--judge-cached-input-price-per-1m",
            "--judge-output-price-per-1m", "--node-max-old-space-size-mb",
            "--resume-policy", "--no-analysis", "--no-figures", "--package-dir",
            "--agent-dir",
        ):
            with self.subTest(option=option):
                self.assertIn(option, help_text)

    def test_benchmark_cli_judge_overrides_take_precedence_over_shared_env(self) -> None:
        environment = {
            "DCI_EVAL_JUDGE_BASE_URL": "https://env.invalid/v1",
            "DCI_EVAL_JUDGE_API": "responses",
            "DCI_EVAL_JUDGE_MODEL": "env-model",
            "DCI_EVAL_JUDGE_JSON_MODE": "true",
            "DCI_EVAL_JUDGE_STRICT_JSON_SCHEMA": "false",
            "DCI_EVAL_JUDGE_RESPONSES_STORE": "true",
            "OVERRIDE_JUDGE_KEY": "synthetic-secret-key",
        }
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory).resolve()
            dataset = root / "data.jsonl"
            corpus = root / "corpus"
            dataset.write_text("{}\n", encoding="utf-8")
            corpus.mkdir()
            with patch.dict(os.environ, environment, clear=True), patch(
                "asterion.dci.cli.run_benchmark"
            ) as benchmark:
                benchmark.return_value = type(
                    "Result", (), {"output_root": root / "out", "counts": {"total": 1}}
                )()
                stdout = io.StringIO()
                stderr = io.StringIO()
                status = main(
                    [
                        "benchmark", "--dataset", str(dataset), "--output-root", "out",
                        "--corpus", str(corpus), "--judge-base-url", "https://cli.invalid/v1",
                        "--judge-api", "chat-completions", "--judge-model", "cli-model",
                        "--judge-api-key-env", "OVERRIDE_JUDGE_KEY",
                        "--judge-timeout-seconds", "17", "--judge-max-output-tokens", "321",
                        "--no-judge-json-mode", "--judge-strict-json-schema",
                        "--no-judge-responses-store", "--judge-thinking", "omit",
                        "--judge-input-price-per-1m", "1.5",
                        "--judge-cached-input-price-per-1m", "0.25",
                        "--judge-output-price-per-1m", "3.75",
                    ],
                    repo_root=root,
                    stdout=stdout,
                    stderr=stderr,
                )
        self.assertEqual(status, 0, stderr.getvalue())
        config = benchmark.call_args.args[0].judge_config
        self.assertEqual(config.base_url, "https://cli.invalid/v1")
        self.assertEqual(config.api, "chat-completions")
        self.assertEqual(config.model, "cli-model")
        self.assertEqual(config.api_key_env, "OVERRIDE_JUDGE_KEY")
        self.assertEqual(config.api_key, "synthetic-secret-key")
        self.assertEqual(config.timeout_seconds, 17)
        self.assertEqual(config.max_output_tokens, 321)
        self.assertFalse(config.json_mode)
        self.assertTrue(config.strict_json_schema)
        self.assertFalse(config.responses_store)
        self.assertEqual(config.thinking, "omit")
        self.assertEqual(config.input_price_per_1m, 1.5)
        self.assertEqual(config.cached_input_price_per_1m, 0.25)
        self.assertEqual(config.output_price_per_1m, 3.75)
        self.assertNotIn("synthetic-secret", stdout.getvalue() + stderr.getvalue())

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
