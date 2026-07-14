"""Package-local command line for the independent Asterion DCI product."""

from __future__ import annotations

import argparse
import contextlib
import io
import os
import secrets
import stat
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

from asterion.dci.config import (
    DciRuntimeOptions,
    load_asterion_dci_env,
    resolve_dci_paths,
    resolve_dci_runtime_options,
)
from asterion.dci.benchmark import BenchmarkRequest, DciBenchmarkError, run_benchmark
from asterion.dci.artifacts import DciConversationFeatures
from asterion.dci.evaluation import DciEvaluationError, evaluate_run_directory
from asterion.dci.judge import JudgeConfig
from asterion.dci.pi_rpc import run_pi_terminal, validate_terminal_cwd
from asterion.dci.run import (
    DciRunError,
    DciRunResult,
    request_from_runtime_options,
    resume_request_from_output_dir,
    run_pi_research,
    validate_dci_run_request,
)
from asterion.dci.system_prompt import render_pi_system_prompt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asterion-dci")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("question", nargs="*")
    run.add_argument("--question-file", type=Path)
    run.add_argument("--cwd", type=Path, default=Path("."))
    _add_runtime_option_arguments(run)
    run.add_argument("--max-turns", type=int)
    run.add_argument("--show-tools", action="store_true")
    run.add_argument("--system-prompt-file", type=Path)
    run.add_argument("--append-system-prompt-file", type=Path)
    run.add_argument("--output-dir", type=Path)
    run.add_argument("--run-id")
    run.add_argument("--conversation-clear-tool-results", action="store_true")
    run.add_argument("--conversation-clear-tool-results-keep-last", type=int, default=3)
    run.add_argument("--conversation-externalize-tool-results", action="store_true")
    run.add_argument("--conversation-strip-thinking", action="store_true")
    run.add_argument("--conversation-strip-usage", action="store_true")
    run.add_argument("--resume", action="store_true")
    run.add_argument("--eval-answer")
    run.add_argument("--eval-answer-file", type=Path)
    terminal = commands.add_parser("terminal")
    terminal.add_argument("question", nargs="*")
    terminal.add_argument("--question-file", type=Path)
    terminal.add_argument("--cwd", type=Path, default=Path("."))
    terminal.add_argument("--provider")
    terminal.add_argument("--model")
    terminal.add_argument("--tools")
    terminal.add_argument("--thinking-level")
    terminal.add_argument("--node-max-old-space-size-mb", type=int)
    terminal.add_argument("--extra-arg", action="append")
    terminal.add_argument("--system-prompt-file", type=Path)
    terminal.add_argument("--append-system-prompt-file", type=Path)
    resume = commands.add_parser("resume")
    resume.add_argument("--output-dir", type=Path, required=True)
    prompt = commands.add_parser("system-prompt")
    prompt.add_argument("--cwd", type=Path, default=Path("."))
    prompt.add_argument("--tools")
    prompt.add_argument("--append-system-prompt-file", type=Path)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--output-dir", type=Path, required=True)
    evaluate.add_argument("--gold-answer", required=True)
    evaluate.add_argument("--answer")
    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("--dataset", type=Path, required=True)
    benchmark.add_argument("--output-root", type=Path, required=True)
    benchmark.add_argument("--cwd", type=Path, default=Path("."))
    _add_runtime_option_arguments(benchmark)
    benchmark.add_argument("--limit", type=int)
    benchmark.add_argument("--mode", choices=("qa", "ir"), default="qa")
    benchmark.add_argument("--profile")
    benchmark.add_argument("--corpus", type=Path)
    benchmark.add_argument("--corpus-hint")
    benchmark.add_argument("--max-concurrency", type=int, default=1)
    benchmark.add_argument("--max-turns", type=int)
    benchmark.add_argument(
        "--resume-policy", choices=("compatible", "fresh", "reuse"), default="compatible"
    )
    benchmark.add_argument("--no-analysis", action="store_true")
    benchmark.add_argument("--no-figures", action="store_true")
    benchmark.add_argument("--system-prompt-file", type=Path)
    benchmark.add_argument("--append-system-prompt-file", type=Path)
    benchmark.add_argument("--conversation-clear-tool-results", action="store_true")
    benchmark.add_argument(
        "--conversation-clear-tool-results-keep-last", type=int, default=3
    )
    benchmark.add_argument(
        "--conversation-externalize-tool-results", action="store_true"
    )
    benchmark.add_argument("--conversation-strip-thinking", action="store_true")
    benchmark.add_argument("--conversation-strip-usage", action="store_true")
    return parser


def _add_runtime_option_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared DCI settings with None defaults for environment resolution."""

    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--tools")
    parser.add_argument("--rpc-timeout-seconds", type=float)
    parser.add_argument("--runtime-context-level")
    parser.add_argument("--thinking-level")
    parser.add_argument("--node-max-old-space-size-mb", type=int)
    parser.add_argument("--keep-session", action="store_true", default=None)
    parser.add_argument("--extra-arg", action="append")


def main(
    argv: list[str] | None = None,
    *,
    repo_root: Path | None = None,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run an Asterion DCI command without changing generic CLI ownership."""

    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    effective_argv = list(sys.argv[1:] if argv is None else argv)
    parser = _parser()
    if effective_argv == ["--help"]:
        parser.print_help(file=stdout)
        return 0
    try:
        with (
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            args = parser.parse_args(effective_argv)
    except SystemExit as error:
        if error.code == 0:
            return 0
        _write_command_failure(stderr, _requested_command(effective_argv))
        return 2
    try:
        invocation_cwd = Path.cwd().resolve()
        root = invocation_cwd if repo_root is None else Path(repo_root).resolve()
        load_asterion_dci_env(root)
        paths = resolve_dci_paths(root)
    except (OSError, ValueError):
        _write_command_failure(stderr, args.command)
        return 2
    if args.command == "evaluate":
        try:
            result = evaluate_run_directory(
                args.output_dir,
                gold_answer=args.gold_answer,
                predicted_answer=args.answer,
                judge_config=JudgeConfig.from_env(),
            )
        except (DciEvaluationError, OSError, ValueError):
            stderr.write("DCI evaluation failed\n")
            return 2
        stdout.write(f"output_dir={args.output_dir}\n")
        stdout.write(f"is_correct={result['is_correct']}\n")
        stdout.write("evaluation_uri=eval_result.json\n")
        return 0
    if args.command == "benchmark":
        try:
            benchmark_output_root = _output_path_from_invocation(
                args.output_root, invocation_cwd
            )
            if _path_has_symlink(benchmark_output_root):
                raise ValueError("benchmark destination is unsafe")
            benchmark_system_prompt = _resolve_resource(
                args.system_prompt_file,
                invocation_cwd=invocation_cwd,
                repo_root=root,
            )
            benchmark_append_prompt = _resolve_resource(
                args.append_system_prompt_file,
                invocation_cwd=invocation_cwd,
                repo_root=root,
            )
            result = run_benchmark(
                BenchmarkRequest(
                    dataset=args.dataset,
                    output_root=benchmark_output_root,
                    cwd=_absolute_from_invocation(args.cwd, invocation_cwd),
                    judge_config=JudgeConfig.from_env(),
                    runtime_options=_runtime_options(args),
                    limit=args.limit,
                    mode=args.mode,
                    profile=args.profile,
                    corpus=(
                        _absolute_from_invocation(args.corpus, invocation_cwd)
                        if args.corpus is not None
                        else None
                    ),
                    corpus_hint=args.corpus_hint,
                    max_concurrency=args.max_concurrency,
                    max_turns=args.max_turns,
                    resume_policy=args.resume_policy,
                    analysis=not args.no_analysis,
                    figures=not args.no_figures,
                    system_prompt_file=benchmark_system_prompt,
                    append_system_prompt_file=benchmark_append_prompt,
                    conversation_features=DciConversationFeatures(
                        clear_tool_results=args.conversation_clear_tool_results,
                        clear_tool_results_keep_last=args.conversation_clear_tool_results_keep_last,
                        externalize_tool_results=args.conversation_externalize_tool_results,
                        strip_thinking=args.conversation_strip_thinking,
                        strip_usage=args.conversation_strip_usage,
                    ),
                ),
                paths=paths,
            )
        except (
            DciBenchmarkError,
            DciEvaluationError,
            DciRunError,
            OSError,
            ValueError,
        ):
            stderr.write("DCI benchmark failed\n")
            return 2
        stdout.write(f"output_root={result.output_root}\n")
        stdout.write(f"total={result.counts['total']}\n")
        return 0
    if args.command == "system-prompt":
        try:
            append_system_prompt_file = _resolve_resource(
                args.append_system_prompt_file,
                invocation_cwd=invocation_cwd,
                repo_root=root,
            )
            stdout.write(
                render_pi_system_prompt(
                    paths,
                    _absolute_from_invocation(args.cwd, invocation_cwd),
                    args.tools,
                    append_system_prompt_file,
                )
            )
            return 0
        except (OSError, RuntimeError, ValueError):
            stderr.write("DCI system prompt generation failed\n")
            return 2
    if args.command == "resume":
        try:
            output_dir = _output_path_from_invocation(args.output_dir, invocation_cwd)
            if _path_has_symlink(output_dir):
                raise ValueError("run destination is unsafe")
            request = resume_request_from_output_dir(output_dir)
            result = run_pi_research(paths, request, output_dir=output_dir)
        except (DciRunError, OSError, ValueError):
            stderr.write("DCI Pi execution failed\n")
            return 2
        _write_run_result(stdout, result)
        return 0
    if args.command == "terminal":
        try:
            if not stdin.isatty() or not stdout.isatty():
                raise ValueError("terminal requires an interactive TTY")
            question_file = _resolve_resource(
                args.question_file, invocation_cwd=invocation_cwd, repo_root=root
            )
            system_prompt_file = _resolve_resource(
                args.system_prompt_file,
                invocation_cwd=invocation_cwd,
                repo_root=root,
            )
            append_system_prompt_file = _resolve_resource(
                args.append_system_prompt_file,
                invocation_cwd=invocation_cwd,
                repo_root=root,
            )
            initial_question = _read_terminal_question(
                args, question_file=question_file
            )
            options = _terminal_runtime_options(args)
            terminal_cwd = validate_terminal_cwd(
                _path_from_invocation(args.cwd, invocation_cwd)
            )
            return run_pi_terminal(
                package_dir=paths.pi.package_dir,
                cwd=terminal_cwd,
                agent_dir=paths.pi.agent_dir,
                provider=options.provider,
                model=options.model,
                tools=options.tools,
                system_prompt_file=system_prompt_file,
                append_system_prompt_file=append_system_prompt_file,
                thinking_level=options.thinking_level,
                extra_args=options.extra_args,
                node_max_old_space_size_mb=options.node_max_old_space_size_mb,
                initial_question=initial_question,
                stdin=stdin,
                stdout=stdout,
            )
        except (OSError, RuntimeError, ValueError):
            stderr.write("DCI Pi terminal failed\n")
            return 2
    if args.resume:
        stderr.write("use asterion-dci resume --output-dir RUN_DIR\n")
        return 2
    try:
        question_file = _resolve_resource(
            args.question_file, invocation_cwd=invocation_cwd, repo_root=root
        )
        system_prompt_file = _resolve_resource(
            args.system_prompt_file, invocation_cwd=invocation_cwd, repo_root=root
        )
        append_system_prompt_file = _resolve_resource(
            args.append_system_prompt_file,
            invocation_cwd=invocation_cwd,
            repo_root=root,
        )
        evaluation_answer_file = _resolve_resource(
            args.eval_answer_file,
            invocation_cwd=invocation_cwd,
            repo_root=root,
        )
        evaluation_answer = _read_evaluation_answer(
            args, evaluation_answer_file=evaluation_answer_file
        )
        if (
            args.eval_answer is not None or args.eval_answer_file is not None
        ) and not evaluation_answer:
            raise ValueError("evaluation answer is required")
        question = _read_question(args, stdin, question_file=question_file)
        run_cwd = _absolute_from_invocation(args.cwd, invocation_cwd)
        if args.run_id is not None and not _safe_run_id(args.run_id):
            raise ValueError("invalid run id")
        conversation_features = DciConversationFeatures(
            clear_tool_results=args.conversation_clear_tool_results,
            clear_tool_results_keep_last=args.conversation_clear_tool_results_keep_last,
            externalize_tool_results=args.conversation_externalize_tool_results,
            strip_thinking=args.conversation_strip_thinking,
            strip_usage=args.conversation_strip_usage,
        )
    except (OSError, RuntimeError, ValueError):
        stderr.write("DCI Pi execution failed\n")
        return 2
    if not question:
        stderr.write("question is required\n")
        return 2
    try:
        request = replace(
            request_from_runtime_options(
                _runtime_options(args),
                run_id=args.run_id or "pending-generated-run-id",
                question=question,
                cwd=run_cwd,
            ),
            max_turns=args.max_turns,
            show_tools=args.show_tools,
            system_prompt_file=system_prompt_file,
            append_system_prompt_file=append_system_prompt_file,
            conversation_features=conversation_features,
        )
        validate_dci_run_request(request, paths)
        run_id = args.run_id or _new_run_id()
        request = replace(request, run_id=run_id)
        output_dir = (
            _output_path_from_invocation(args.output_dir, invocation_cwd)
            if args.output_dir is not None
            else paths.output_root / run_id
        )
        if _path_has_symlink(output_dir) or output_dir.exists():
            raise ValueError("run destination already exists")
    except (OSError, RuntimeError, ValueError):
        stderr.write("DCI Pi execution failed\n")
        return 2
    try:
        result = run_pi_research(paths, request, output_dir=output_dir)
    except DciRunError:
        stderr.write("DCI Pi execution failed\n")
        return 2
    if args.eval_answer is not None or args.eval_answer_file is not None:
        try:
            verdict = evaluate_run_directory(
                result.output_dir,
                gold_answer=evaluation_answer,
                judge_config=JudgeConfig.from_env(),
            )
        except (DciEvaluationError, OSError, ValueError):
            stderr.write("DCI evaluation failed\n")
            return 2
        stdout.write(f"output_dir={result.output_dir}\n")
        stdout.write(f"is_correct={verdict['is_correct']}\n")
        stdout.write("evaluation_uri=eval_result.json\n")
        return 0
    _write_run_result(stdout, result)
    return 0


def _read_question(
    args: argparse.Namespace,
    stdin: TextIO,
    *,
    question_file: Path | None,
) -> str:
    if question_file is not None:
        return question_file.read_text(encoding="utf-8").strip()
    if args.question:
        return " ".join(args.question).strip()
    if stdin.isatty():
        return ""
    return stdin.read().strip()


def _read_terminal_question(
    args: argparse.Namespace, *, question_file: Path | None
) -> str | None:
    if question_file is not None:
        return question_file.read_text(encoding="utf-8").strip() or None
    if args.question:
        return " ".join(args.question).strip() or None
    return None


def _absolute_from_invocation(path: Path, invocation_cwd: Path) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = invocation_cwd / candidate
    return candidate.resolve()


def _path_from_invocation(path: Path, invocation_cwd: Path) -> Path:
    """Make an input path absolute without following security-relevant links."""

    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = invocation_cwd / candidate
    return Path(os.path.normpath(candidate))


def _output_path_from_invocation(path: Path, invocation_cwd: Path) -> Path:
    """Make a destination absolute without erasing security-relevant links."""

    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = invocation_cwd / candidate
    return Path(os.path.normpath(candidate))


def _resolve_resource(
    path: Path | None,
    *,
    invocation_cwd: Path,
    repo_root: Path,
) -> Path | None:
    if path is None:
        return None
    expanded = path.expanduser()
    candidates = (
        (expanded,)
        if expanded.is_absolute()
        else (invocation_cwd / expanded, repo_root / expanded)
    )
    for candidate in dict.fromkeys(candidates):
        if not candidate.exists() and not candidate.is_symlink():
            continue
        if _path_has_symlink(candidate):
            raise ValueError("resource path is unsafe")
        metadata = candidate.stat()
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o444 == 0:
            raise ValueError("resource is not readable")
        resolved = candidate.resolve(strict=True)
        with resolved.open("rb"):
            pass
        return resolved
    raise ValueError("resource does not exist")


def _path_has_symlink(path: Path) -> bool:
    absolute = path.absolute()
    parts = absolute.parts
    current = Path(parts[0])
    for part in parts[1:]:
        current /= part
        if current.is_symlink():
            return True
    return False


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    return f"asterion-dci-{timestamp}-{secrets.token_hex(4)}"


def _safe_run_id(value: str) -> bool:
    return (
        bool(value.strip()) and value not in {".", ".."} and Path(value).name == value
    )


def _read_evaluation_answer(
    args: argparse.Namespace,
    *,
    evaluation_answer_file: Path | None,
) -> str | None:
    if evaluation_answer_file is not None:
        return evaluation_answer_file.read_text(encoding="utf-8").strip()
    if args.eval_answer is None:
        return None
    return str(args.eval_answer).strip()


def _write_command_failure(stderr: TextIO, command: str) -> None:
    messages = {
        "evaluate": "DCI evaluation failed\n",
        "benchmark": "DCI benchmark failed\n",
        "system-prompt": "DCI system prompt generation failed\n",
        "terminal": "DCI Pi terminal failed\n",
    }
    stderr.write(messages.get(command, "DCI Pi execution failed\n"))


def _requested_command(argv: list[str]) -> str:
    """Classify only the exact command token without retaining argument values."""

    return (
        argv[0]
        if argv
        and argv[0]
        in {
            "run",
            "terminal",
            "resume",
            "system-prompt",
            "evaluate",
            "benchmark",
        }
        else ""
    )


def _runtime_options(args: argparse.Namespace) -> DciRuntimeOptions:
    values = {
        "provider": args.provider,
        "model": args.model,
        "tools": args.tools,
        "timeout_seconds": args.rpc_timeout_seconds,
        "runtime_context_level": args.runtime_context_level,
        "thinking_level": args.thinking_level,
        "node_max_old_space_size_mb": args.node_max_old_space_size_mb,
        "keep_session": args.keep_session,
        "extra_args": tuple(args.extra_arg or ()),
    }
    return resolve_dci_runtime_options(
        {name: value for name, value in values.items() if value is not None}
    )


def _terminal_runtime_options(args: argparse.Namespace) -> DciRuntimeOptions:
    values = {
        "provider": args.provider,
        "model": args.model,
        "tools": args.tools,
        "thinking_level": args.thinking_level,
        "node_max_old_space_size_mb": args.node_max_old_space_size_mb,
        "extra_args": tuple(args.extra_arg or ()),
        "timeout_seconds": None,
        "runtime_context_level": None,
        "keep_session": True,
    }
    return resolve_dci_runtime_options(
        {name: value for name, value in values.items() if value is not None}
    )


def _write_run_result(stdout: TextIO, result: DciRunResult) -> None:
    stdout.write(f"output_dir={result.output_dir}\n")
    stdout.write(f"status={result.status}\n")
    stdout.write("final_answer_uri=final.txt\n")
