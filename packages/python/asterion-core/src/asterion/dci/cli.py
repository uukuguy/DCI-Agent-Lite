"""Package-local command line for the independent Asterion DCI product."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TextIO

from asterion.dci.config import load_asterion_dci_env, resolve_dci_paths
from asterion.dci.benchmark import BenchmarkRequest, DciBenchmarkError, run_benchmark
from asterion.dci.evaluation import DciEvaluationError, evaluate_run_directory
from asterion.dci.judge import JudgeConfig
from asterion.dci.run import (
    DciRunError,
    DciRunRequest,
    DciRunResult,
    resume_request_from_output_dir,
    run_pi_research,
)
from asterion.dci.system_prompt import render_pi_system_prompt


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="asterion-dci")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run")
    run.add_argument("question", nargs="?")
    run.add_argument("--question-file", type=Path)
    run.add_argument("--provider")
    run.add_argument("--model")
    run.add_argument("--cwd", type=Path, default=Path.cwd())
    run.add_argument("--tools", default="read,bash")
    run.add_argument("--max-turns", type=int)
    run.add_argument("--rpc-timeout-seconds", type=float, default=3600.0)
    run.add_argument("--show-tools", action="store_true")
    run.add_argument("--extra-arg", action="append", default=[])
    run.add_argument("--system-prompt-file", type=Path)
    run.add_argument("--append-system-prompt-file", type=Path)
    run.add_argument("--output-dir", type=Path)
    run.add_argument("--run-id", default="asterion-dci-run")
    run.add_argument("--resume", action="store_true")
    run.add_argument("--eval-answer")
    run.add_argument("--eval-answer-file", type=Path)
    resume = commands.add_parser("resume")
    resume.add_argument("--output-dir", type=Path, required=True)
    prompt = commands.add_parser("system-prompt")
    prompt.add_argument("--cwd", type=Path, default=Path.cwd())
    prompt.add_argument("--tools")
    prompt.add_argument("--append-system-prompt-file", type=Path)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--output-dir", type=Path, required=True)
    evaluate.add_argument("--gold-answer", required=True)
    evaluate.add_argument("--answer")
    benchmark = commands.add_parser("benchmark")
    benchmark.add_argument("--dataset", type=Path, required=True)
    benchmark.add_argument("--output-root", type=Path, required=True)
    benchmark.add_argument("--cwd", type=Path, default=Path.cwd())
    return parser


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
    parser = _parser()
    if argv == ["--help"]:
        parser.print_help(file=stdout)
        return 0
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2
    root = Path.cwd() if repo_root is None else Path(repo_root)
    load_asterion_dci_env(root)
    paths = resolve_dci_paths(root)
    if args.command == "evaluate":
        try:
            result = evaluate_run_directory(
                args.output_dir,
                gold_answer=args.gold_answer,
                predicted_answer=args.answer,
                judge_config=JudgeConfig.from_env(),
            )
        except (DciEvaluationError, ValueError):
            stderr.write("DCI evaluation failed\n")
            return 2
        stdout.write(f"output_dir={args.output_dir}\n")
        stdout.write(f"is_correct={result['is_correct']}\n")
        stdout.write("evaluation_uri=eval_result.json\n")
        return 0
    if args.command == "benchmark":
        try:
            result = run_benchmark(
                BenchmarkRequest(
                    dataset=args.dataset,
                    output_root=args.output_root,
                    cwd=args.cwd,
                    judge_config=JudgeConfig.from_env(),
                ),
                paths=paths,
            )
        except (DciBenchmarkError, ValueError):
            stderr.write("DCI benchmark failed\n")
            return 2
        stdout.write(f"output_root={result.output_root}\n")
        stdout.write(f"total={result.counts['total']}\n")
        return 0
    if args.command == "system-prompt":
        try:
            stdout.write(
                render_pi_system_prompt(
                    paths,
                    args.cwd,
                    args.tools,
                    args.append_system_prompt_file,
                )
            )
            return 0
        except (OSError, RuntimeError, ValueError):
            stderr.write("DCI system prompt generation failed\n")
            return 2
    if args.command == "resume":
        try:
            request = resume_request_from_output_dir(args.output_dir)
            result = run_pi_research(paths, request, output_dir=args.output_dir)
        except DciRunError:
            stderr.write("DCI Pi execution failed\n")
            return 2
        _write_run_result(stdout, result)
        return 0
    if args.resume:
        stderr.write("use asterion-dci resume --output-dir RUN_DIR\n")
        return 2
    if args.eval_answer is not None or args.eval_answer_file is not None:
        stderr.write("evaluation is not available until AF-200\n")
        return 2
    question = _read_question(args, stdin)
    if not question:
        stderr.write("question is required\n")
        return 2
    request = DciRunRequest(
        run_id=args.run_id,
        question=question,
        cwd=args.cwd,
        provider=args.provider,
        model=args.model,
        tools=args.tools,
        max_turns=args.max_turns,
        timeout_seconds=args.rpc_timeout_seconds,
        extra_args=tuple(args.extra_arg),
        show_tools=args.show_tools,
        system_prompt_file=args.system_prompt_file,
        append_system_prompt_file=args.append_system_prompt_file,
    )
    try:
        result = run_pi_research(paths, request, output_dir=args.output_dir)
    except DciRunError:
        stderr.write("DCI Pi execution failed\n")
        return 2
    _write_run_result(stdout, result)
    return 0


def _read_question(args: argparse.Namespace, stdin: TextIO) -> str:
    if args.question_file is not None:
        return args.question_file.read_text(encoding="utf-8").strip()
    if args.question is not None:
        return args.question
    return stdin.read().strip()


def _write_run_result(stdout: TextIO, result: DciRunResult) -> None:
    stdout.write(f"output_dir={result.output_dir}\n")
    stdout.write(f"status={result.status}\n")
    stdout.write("final_answer_uri=final.txt\n")
