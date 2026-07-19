#!/usr/bin/env python3
"""Verify the original README contract for quick-start and context-management snippets.

Local mode only parses README text and validates executable command templates.
Bounded mode runs the documented original quick-start command plus one L3 and one
L4 bounded run against the original DCI entry point.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Sequence, Set


README_SECTION_PATTERN = re.compile(r"(?m)^##\s+.+$")
def _find_section_indices(text: str, title_substring: str) -> tuple[int, int]:
    headings = list(README_SECTION_PATTERN.finditer(text))
    start = None
    for i, match in enumerate(headings):
        if title_substring in match.group(0):
            start = match.start()
            if i + 1 < len(headings):
                return start, headings[i + 1].start()
            return start, len(text)
    raise ValueError(f"section not found: {title_substring}")


def _extract_section(text: str, title_substring: str) -> str:
    start, end = _find_section_indices(text, title_substring)
    return text[start:end]


def _extract_bash_blocks(section: str) -> list[str]:
    blocks: list[str] = []
    opened = False
    current: list[str] = []
    for line in section.splitlines():
        if line.lstrip().startswith("```"):
            if opened:
                blocks.append("\n".join(current))
                current = []
            opened = not opened
            continue
        if opened:
            current.append(line)
    return blocks


def _has_flag(text: str, flag: str) -> bool:
    pattern = re.compile(rf"(?:^|\s){re.escape(flag)}(?:\s|$)")
    return pattern.search(text) is not None


def _validate_no_hardcoded_provider_model(block: str) -> None:
    if _has_flag(block, "--provider") or _has_flag(block, "--model"):
        raise ValueError("default README command must not hardcode provider/model")


def _validate_tokens_present(text: str, token: str) -> None:
    if token not in text:
        raise ValueError(f"missing README token: {token}")


def _validate_quick_start(readme: str) -> None:
    section = _extract_section(readme, "⚡ Quick Start")
    blocks = _extract_bash_blocks(section)
    command_blocks = [block for block in blocks if "dci.benchmark.pi_rpc_runner" in block]
    if len(command_blocks) < 2:
        raise ValueError("Quick Start should contain both terminal and programmatic examples")

    terminal_defaults = [
        block
        for block in command_blocks
        if "--terminal" in block
        and not (_has_flag(block, "--provider") or _has_flag(block, "--model"))
    ]
    if not terminal_defaults:
        raise ValueError("Quick Start should show a terminal command")
    for block in terminal_defaults:
        _validate_no_hardcoded_provider_model(block)

    default_programmatic = [
        block
        for block in command_blocks
        if "--terminal" not in block
        and not (_has_flag(block, "--provider") or _has_flag(block, "--model"))
    ]
    if not default_programmatic:
        raise ValueError("Quick Start should show a programmatic command")
    for block in default_programmatic:
        _validate_no_hardcoded_provider_model(block)

    override_blocks = [
        block
        for block in command_blocks
        if _has_flag(block, "--provider") and _has_flag(block, "--model")
    ]
    if not override_blocks:
        raise ValueError("Quick Start must include a provider/model override example")

    if not any(req in block for block in override_blocks for req in ("--provider", "--model")):
        raise ValueError("Quick Start override example must include provider/model flags")
    _validate_tokens_present(section, "PYTHONPATH=src uv run python -m dci.benchmark.pi_rpc_runner")
    _validate_tokens_present(section, "--extra-arg=\"--thinking high\"")


def _validate_context_strategy(readme: str) -> None:
    section = _extract_section(readme, "Context Management Strategies")
    _validate_tokens_present(section, "one short bounded command")
    required_levels = {"level0", "level1", "level2", "level3", "level4"}
    loop_levels: set[str] = set()
    for line in section.splitlines():
        if "for profile in " in line and "do" in line:
            loop_levels.update(re.findall(r"level[0-4]", line))
    if loop_levels and not required_levels.issubset(loop_levels):
        missing = ", ".join(sorted(required_levels - loop_levels))
        raise ValueError(f"Context-management section missing {missing}")

    blocks = _extract_bash_blocks(section)
    context_blocks = [
        block for block in blocks if "--runtime-context-level" in block
    ]
    if not context_blocks:
        raise ValueError("context section should include runtime-context-level examples")

    seen: Set[str] = set()
    for block in context_blocks:
        if re.search(r'--runtime-context-level\s+["\']?\$profile["\']?', block):
            seen = required_levels.copy()
            break
        for level in ("level0", "level1", "level2", "level3", "level4"):
            pattern = re.compile(rf"--runtime-context-level\s+\"?{re.escape(level)}\"?")
            if pattern.search(block):
                seen.add(level)
    if seen != {"level0", "level1", "level2", "level3", "level4"}:
        raise ValueError("Context examples should cover level0..level4")


def verify_readme_contract(readme_path: Path) -> list[str]:
    text = readme_path.read_text(encoding="utf-8")
    _validate_quick_start(text)
    _validate_context_strategy(text)
    return [
        "quick-start contract: ok",
        "context-management contract: ok",
    ]


def _parse_env_file(path: Optional[Path]) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    env: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        env[key.strip()] = value
    return env


def _run_command(
    args: Sequence[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
        timeout=timeout_seconds,
    )


def _write_question(path: Path) -> None:
    path.write_text(
        "Answer the following question using only wiki_dump.jsonl in the current directory. "
        "Question: In which street did the Great Fire of London originate?",
        encoding="utf-8",
    )


def _ensure_output_artifacts(output_dir: Path) -> None:
    required = ("question.txt", "final.txt", "state.json", "events.jsonl", "conversation_full.json", "effective-config.json")
    missing = [name for name in required if not (output_dir / name).is_file()]
    if missing:
        raise RuntimeError(
            f"bounded quick-start output missing files: {', '.join(missing)} in {output_dir}"
        )


def verify_bounded_contract(
    readme_path: Path,
    env_file: Optional[Path],
    output_root: Path,
    repo_root: Path,
) -> list[str]:
    verify_readme_contract(readme_path)
    output_root = output_root.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    env = os.environ.copy()
    if env_file is not None:
        env.update(_parse_env_file(env_file))
    env["PYTHONPATH"] = "src"
    command_base = [
        "uv",
        "run",
        "python",
        "-m",
        "dci.benchmark.pi_rpc_runner",
        "--runtime",
        "pi",
        "--cwd",
        "corpus/wiki_corpus",
        "--extra-arg=--thinking high",
    ]

    with tempfile.TemporaryDirectory(prefix="verify-original-readme-", dir=output_root) as temporary:
        question_file = Path(temporary) / "question.txt"
        _write_question(question_file)

        # quick-start programmatic command
        quick_output = output_root / "quick-start"
        quick = _run_command(
            [
                *command_base,
                "--max-turns",
                "2",
                "--output-dir",
                str(quick_output),
                "--question-file",
                str(question_file),
            ],
            cwd=repo_root,
            env=env,
            timeout_seconds=1200,
        )
        if quick.returncode != 0:
            raise RuntimeError(
                "bounded quick-start failed\n"
                f"stdout:\n{quick.stdout}\nstderr:\n{quick.stderr}"
            )
        _ensure_output_artifacts(quick_output)

        for level in ("level3", "level4"):
            level_output = output_root / f"context-{level}"
            level_case = _run_command(
                [
                *command_base,
                "--runtime-context-level",
                level,
                "--max-turns",
                "3",
                "--output-dir",
                str(level_output),
                "--question-file",
                str(question_file),
            ],
            cwd=repo_root,
            env=env,
            timeout_seconds=1200,
        )
            if level_case.returncode != 0:
                raise RuntimeError(
                    f"bounded context {level} failed\n"
                    f"stdout:\n{level_case.stdout}\nstderr:\n{level_case.stderr}"
                )
            _ensure_output_artifacts(level_output)

    return [
        f"bounded quick-start: {quick_output}",
        f"bounded level3: {output_root / 'context-level3'}",
        f"bounded level4: {output_root / 'context-level4'}",
    ]


def verify_original_readme_main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--level", choices=("local", "bounded"), default="local")
    parser.add_argument("--readme", default="README.md")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output-root", default="outputs/verify-original-readme")
    args = parser.parse_args(list(argv) if argv is not None else None)

    readme_path = Path(args.readme).resolve()
    repo_root = readme_path.parent
    try:
        if args.level == "local":
            report = verify_readme_contract(readme_path)
        else:
            report = verify_bounded_contract(
                readme_path=readme_path,
                env_file=args.env_file,
                output_root=(repo_root / args.output_root).resolve(),
                repo_root=repo_root,
            )
    except Exception as exc:
        print(f"verify_original_readme failed: {exc}", flush=True)
        return 2

    for line in report:
        print(line, flush=True)
    print("PASS: Agent operations: 0", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(verify_original_readme_main())
