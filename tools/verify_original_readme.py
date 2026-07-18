#!/usr/bin/env python3
"""Verify the literal original-DCI README Quick Start and context paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TextIO


_PROFILES = ("level0", "level1", "level2", "level3", "level4")
_QUESTION = (
    "Answer the following question using only wiki_dump.jsonl in the current "
    "directory. Do not use web search. Use rg instead of grep for fast searching. "
    "Question: In which street did the Great Fire of London originate?"
)


def _section(text: str, heading: str) -> str:
    match = re.search(rf"(?m)^## [^\n]*{re.escape(heading)}[^\n]*$", text)
    if match is None:
        raise ValueError("README contract is invalid")
    following = re.search(r"(?m)^## ", text[match.end() :])
    end = len(text) if following is None else match.end() + following.start()
    return text[match.end() : end]


def _fences(section: str) -> tuple[str, ...]:
    return tuple(match.group(1).strip() for match in re.finditer(r"```bash\n(.*?)```", section, re.S))


def _marked(fences: Sequence[str], marker: str) -> str:
    matches = [fence for fence in fences if marker in fence]
    if len(matches) != 1:
        raise ValueError("README contract is invalid")
    return matches[0]


def validate_readme_contract(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    quick = _section(text, "Quick Start")
    context = _section(text, "Context Management Strategies")
    quick_fences = _fences(quick)
    terminal = _marked(quick_fences, "quick-start-terminal")
    programmatic = _marked(quick_fences, "quick-start-programmatic")
    override = _marked(quick_fences, "quick-start-override")
    if "cp .env.template .env" not in quick:
        raise ValueError("README contract is invalid")
    for command in (terminal, programmatic):
        if (
            "src/dci/benchmark/pi_rpc_runner.py" not in command
            or "--provider" in command
            or "--model" in command
        ):
            raise ValueError("README contract is invalid")
    if "--provider openai-codex" not in override or "--model gpt-5.6-luna" not in override:
        raise ValueError("README contract is invalid")
    context_commands: dict[str, str] = {}
    for fence in _fences(context):
        for profile in re.findall(r"--runtime-context-level[= ]+(level[0-9]+)", fence):
            if profile in context_commands:
                raise ValueError("README contract is invalid")
            context_commands[profile] = fence
    if tuple(sorted(context_commands)) != _PROFILES:
        raise ValueError("README contract is invalid")
    if "tools/verify_original_readme.py --level local" not in context:
        raise ValueError("README contract is invalid")
    return {
        "terminal": terminal,
        "programmatic": programmatic,
        "override": override,
        "context_commands": context_commands,
    }


def _original_context_api(repo_root: Path):
    source_root = str(repo_root / "src")
    if source_root not in sys.path:
        sys.path.insert(0, source_root)
    from dci.context_management import (  # noqa: PLC0415
        ModelFreeContextPolicy,
        context_profile_names,
        resolve_context_extension,
        resolve_context_profile,
    )

    return (
        ModelFreeContextPolicy,
        context_profile_names,
        resolve_context_extension,
        resolve_context_profile,
    )


def _model_free_context_contract(repo_root: Path) -> str:
    policy_type, names, resolve_extension, resolve_profile = _original_context_api(
        repo_root
    )
    if names() != _PROFILES:
        raise ValueError("context contract is invalid")
    extension = resolve_extension()
    level1 = policy_type(resolve_profile("level1"))
    if len(level1.tool_result("x" * 60_000)) != 50_000:
        raise ValueError("context contract is invalid")
    level3 = policy_type(resolve_profile("level3"))
    level3.tool_result("x" * 240_001)
    level3.compact(summary_succeeded=None)
    if level3.compactions != 1 or level3.visible_turn_count(13) != 12:
        raise ValueError("context contract is invalid")
    level4 = policy_type(resolve_profile("level4"))
    for _ in range(3):
        level4.tool_result("x" * 240_001)
        level4.compact(summary_succeeded=False)
    if level4.summary_attempts != 3 or not level4.summary_suppressed:
        raise ValueError("context contract is invalid")
    resumed = policy_type.resume(resolve_profile("level4"), level4.snapshot())
    if not any(item.get("event") == "resume" for item in resumed.telemetry):
        raise ValueError("context contract is invalid")
    return extension.sha256


def _terminal_preflight(repo_root: Path, environment: Mapping[str, str]) -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(repo_root / "src/dci/benchmark/pi_rpc_runner.py"),
            "--terminal",
            "--output-dir",
            str(repo_root / "outputs/terminal-preflight-must-not-run"),
            "preflight",
        ],
        cwd=repo_root,
        env=dict(environment),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 2 or "--terminal cannot be combined" not in completed.stderr:
        raise ValueError("terminal preflight is invalid")


def _resolve_pi_loader(repo_root: Path, environment: Mapping[str, str]) -> Path:
    candidates = []
    configured = environment.get("DCI_PI_DIR")
    if configured:
        value = Path(configured).expanduser()
        candidates.append(value if value.is_absolute() else repo_root / value)
    candidates.append(repo_root / "pi")
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if common.returncode == 0:
        common_dir = Path(common.stdout.strip())
        if not common_dir.is_absolute():
            common_dir = repo_root / common_dir
        candidates.append(common_dir.resolve().parent / "pi")
    for pi_dir in candidates:
        loader = pi_dir / "packages/coding-agent/dist/core/extensions/loader.js"
        if loader.is_file():
            return loader
    raise ValueError("installed Pi extension loader is unavailable")


def _run_extension_fixture(
    repo_root: Path, environment: Mapping[str, str], extension_path: Path
) -> None:
    completed = subprocess.run(
        [
            "node",
            str(repo_root / "tools/fixtures/original-context-extension-harness.mjs"),
            str(_resolve_pi_loader(repo_root, environment)),
            str(extension_path),
            str(repo_root),
        ],
        cwd=repo_root,
        env=dict(environment),
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("context extension fixture is invalid") from exc
    expected_characters = {
        "level0": 240_001,
        "level1": 50_000,
        "level2": 20_000,
        "level3": 20_000,
        "level4": 20_000,
    }
    expected_turns = {
        "level0": 13,
        "level1": 13,
        "level2": 13,
        "level3": 12,
        "level4": 12,
    }
    if (
        completed.returncode != 0
        or {name: value.get("toolCharacters") for name, value in result.get("profiles", {}).items()} != expected_characters
        or {name: value.get("retainedUsers") for name, value in result.get("profiles", {}).items()} != expected_turns
        or result.get("profiles", {}).get("level3", {}).get("compactions") != 1
        or result.get("profiles", {}).get("level4", {}).get("summarySuccesses") != 1
        or result.get("failureSuppression") != {"attempts": 3, "suppressed": True}
        or result.get("resumeEvent") != "resume"
        or any(
            value.get("customTypes")
            != ["dci-context-state", "dci-context-telemetry"]
            for value in result.get("profiles", {}).values()
        )
    ):
        raise ValueError("context extension fixture is invalid")


def _load_env_file(path: Path | None, inherited: Mapping[str, str]) -> dict[str, str]:
    environment = dict(inherited)
    if path is None:
        return environment
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        environment.setdefault(name.strip(), value.strip().strip("\"'"))
    return environment


def _prepare_private_root(path: Path) -> Path:
    path = Path(os.path.abspath(os.path.normpath(path.expanduser())))
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError("bounded output root must not contain symlinks")
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ValueError("bounded output root must be a new empty directory")
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    path.chmod(0o700)
    return path


def _runner_command(
    repo_root: Path,
    output_dir: Path,
    profile: str | None,
    *,
    corpus_dir: Path | None = None,
) -> list[str]:
    command = [
        sys.executable,
        str(repo_root / "src/dci/benchmark/pi_rpc_runner.py"),
        "--runtime",
        "pi",
        "--cwd",
        str(corpus_dir or repo_root / "corpus/wiki_corpus"),
        "--output-dir",
        str(output_dir),
        "--max-turns",
        "8",
        "--rpc-timeout-seconds",
        "300",
        "--pi-thinking-level",
        "high",
    ]
    if profile is not None:
        command.extend(
            (
                "--runtime-context-level",
                profile,
                "--keep-session",
                "--extra-arg=--session",
                f"--extra-arg={output_dir / 'pi-session.jsonl'}",
            )
        )
        for _ in range(12):
            command.extend(("--prelude-question", "Reply only with ok."))
        command.append(
            "Run exactly these five commands as separate tool calls in order, then reply only with done: "
            + "; ".join(f"sed -n '{index}p' pressure.txt" for index in range(1, 6))
        )
    else:
        command.append(_QUESTION)
    return command


def _write_pressure_fixture(output_root: Path) -> Path:
    corpus = output_root / "pressure-corpus"
    corpus.mkdir(mode=0o700)
    payload = "".join(f"{index}:" + "x" * 74_997 + "\n" for index in range(1, 6))
    path = corpus / "pressure.txt"
    path.write_text(payload, encoding="utf-8")
    path.chmod(0o600)
    return corpus


def _bounded_context_evidence(profile: str, summary: Mapping[str, object]) -> dict[str, object]:
    required = {
        "profile",
        "compactions",
        "summary_attempts",
        "summary_successes",
        "summary_suppressed",
        "extension_sha256",
    }
    if set(summary) != required or summary.get("profile") != profile:
        raise ValueError("bounded context evidence is invalid")
    compactions = summary.get("compactions")
    attempts = summary.get("summary_attempts")
    successes = summary.get("summary_successes")
    digest = summary.get("extension_sha256")
    if (
        isinstance(compactions, bool)
        or not isinstance(compactions, int)
        or compactions < 1
        or not isinstance(attempts, int)
        or not isinstance(successes, int)
        or not isinstance(digest, str)
        or re.fullmatch(r"[0-9a-f]{64}", digest) is None
    ):
        raise ValueError("bounded context evidence is invalid")
    if profile == "level3" and (attempts != 0 or successes != 0):
        raise ValueError("bounded context evidence is invalid")
    if profile == "level4" and (attempts < 1 or successes < 1 or summary.get("summary_suppressed") is not False):
        raise ValueError("bounded context evidence is invalid")
    return dict(summary)


def _read_context_evidence(session_file: Path, profile: str, extension_sha256: str) -> dict[str, object]:
    telemetry = []
    for line in session_file.read_text(encoding="utf-8").splitlines():
        entry = json.loads(line)
        if entry.get("type") == "custom" and entry.get("customType") == "dci-context-telemetry":
            telemetry.append(entry.get("data"))
    if not telemetry or not isinstance(telemetry[-1], dict):
        raise ValueError("bounded context evidence is invalid")
    latest = telemetry[-1]
    return _bounded_context_evidence(
        profile,
        {
            "profile": latest.get("profile"),
            "compactions": latest.get("compactionCount"),
            "summary_attempts": latest.get("summaryAttempts"),
            "summary_successes": latest.get("summarySuccesses"),
            "summary_suppressed": latest.get("summarySuppressed"),
            "extension_sha256": extension_sha256,
        },
    )


def _artifact_hashes(output_dir: Path) -> dict[str, str]:
    required = {
        "question.txt",
        "final.txt",
        "conversation_full.json",
        "effective-config.json",
    }
    files = sorted(path for path in output_dir.rglob("*") if path.is_file())
    if not required.issubset({path.name for path in files}) or not any(
        path.parent.name == "protocol" for path in files
    ):
        raise ValueError("bounded artifact contract is invalid")
    hashes: dict[str, str] = {}
    for directory in (path for path in output_dir.rglob("*") if path.is_dir()):
        if stat.S_IMODE(directory.stat().st_mode) != 0o700:
            raise ValueError("bounded artifact contract is invalid")
    for path in files:
        if stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise ValueError("bounded artifact contract is invalid")
        name = path.relative_to(output_dir).as_posix()
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verify_original_readme.py")
    parser.add_argument("--level", choices=("local", "bounded"), required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output-root", type=Path)
    return parser


def verify_original_readme_main(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path | None = None,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    executor: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    raise_errors: bool = False,
) -> int:
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    root = Path(__file__).resolve().parents[1] if repo_root is None else Path(repo_root).resolve()
    try:
        args = _parser().parse_args(argv)
        validate_readme_contract(root / "README.md")
        environment = _load_env_file(args.env_file.resolve() if args.env_file else None, os.environ)
        environment["PYTHONPATH"] = str(root / "src")
        extension_digest = _model_free_context_contract(root)
        _run_extension_fixture(
            root,
            environment,
            _original_context_api(root)[2]().path,
        )
        _terminal_preflight(root, environment)
        if args.level == "local":
            stdout.write("PASS\nAgent operations: 0\nJudge operations: 0\nFull dataset ran: no\n")
            return 0
        if args.env_file is None or args.output_root is None:
            raise ValueError("bounded verification requires --env-file and --output-root")
        output_root = _prepare_private_root(args.output_root)
        pressure_corpus = _write_pressure_fixture(output_root)
        cases = (("quick-start-programmatic", None), ("context-level3", "level3"), ("context-level4", "level4"))
        records = []
        for command_id, profile in cases:
            output_dir = output_root / command_id
            completed = executor(
                _runner_command(
                    root,
                    output_dir,
                    profile,
                    corpus_dir=pressure_corpus if profile is not None else None,
                ),
                cwd=root,
                env=environment,
                check=False,
                text=True,
                capture_output=True,
                umask=0o077,
            )
            if completed.returncode != 0:
                raise ValueError(f"bounded command failed: {command_id}")
            if profile is not None:
                evidence = _read_context_evidence(
                    output_dir / "pi-session.jsonl", profile, extension_digest
                )
                evidence_path = output_dir / "context-evidence.json"
                evidence_path.write_text(
                    json.dumps(evidence, sort_keys=True, indent=2) + "\n",
                    encoding="utf-8",
                )
                evidence_path.chmod(0o600)
            hashes = _artifact_hashes(output_dir)
            config = json.loads((output_dir / "effective-config.json").read_text(encoding="utf-8"))
            records.append({"command_id": command_id, "effective_config_sha256": config["identity_sha256"], "private_artifact_sha256": hashes})
        report = {
            "command_ids": [item["command_id"] for item in records],
            "agent_operations": 3,
            "judge_operations": 0,
            "commands": records,
        }
        report_path = output_root / "original-readme-acceptance.json"
        report_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        report_path.chmod(0o600)
        stdout.write("PASS\nAgent operations: 3\nJudge operations: 0\nFull dataset ran: no\n")
        return 0
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        if raise_errors:
            raise
        stderr.write("Original README verification failed\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(verify_original_readme_main())
