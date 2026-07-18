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
_REQUIRED_EXTENSION_EVIDENCE = (
    "compactionCount",
    "summaryAttempts",
    "summarySuppressed",
    "dci-context-telemetry",
    'event.reason === "resume"',
)
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


def validate_context_contract(profiles_path: Path, manifest_path: Path, extension_path: Path) -> str:
    try:
        profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        source = extension_path.read_bytes()
        text = source.decode("utf-8")
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("context contract is invalid") from exc
    definitions = profiles.get("profiles")
    if profiles.get("schema") != "dci.context-profile/v1" or not isinstance(definitions, dict):
        raise ValueError("context contract is invalid")
    if tuple(definitions) != _PROFILES:
        raise ValueError("context contract is invalid")
    level3 = definitions["level3"]
    level4 = definitions["level4"]
    if (
        level3.get("compaction_character_trigger") != 240_000
        or level3.get("retained_turns") != 12
        or level4.get("summary_recent_token_target") != 20_000
        or level4.get("summary_failure_limit") != 3
    ):
        raise ValueError("context contract is invalid")
    digest = hashlib.sha256(source).hexdigest()
    if (
        manifest.get("schema") != "dci.context-extension-manifest/v1"
        or manifest.get("contract_version") != "dci.context-profile/v1"
        or manifest.get("resource") != extension_path.name
        or manifest.get("byte_length") != len(source)
        or manifest.get("sha256") != digest
        or any(item not in text for item in _REQUIRED_EXTENSION_EVIDENCE)
    ):
        raise ValueError("context contract is invalid")
    return digest


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


def _runner_command(repo_root: Path, output_dir: Path, profile: str | None) -> list[str]:
    command = [
        sys.executable,
        str(repo_root / "src/dci/benchmark/pi_rpc_runner.py"),
        "--runtime",
        "pi",
        "--cwd",
        str(repo_root / "corpus/wiki_corpus"),
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
        command.extend(("--runtime-context-level", profile, "--keep-session"))
    command.append(_QUESTION)
    return command


def _artifact_hashes(output_dir: Path) -> dict[str, str]:
    paths = {
        "question.txt": output_dir / "question.txt",
        "final.txt": output_dir / "final.txt",
        "conversation_full.json": output_dir / "conversation_full.json",
        "effective-config.json": output_dir / "effective-config.json",
    }
    protocol = output_dir / "protocol"
    protocol_files = sorted(protocol.glob("attempt-*.*"))
    if not protocol_files:
        raise ValueError("bounded artifact contract is invalid")
    for path in protocol_files:
        paths[f"protocol/{path.name}"] = path
    hashes: dict[str, str] = {}
    for name, path in paths.items():
        if not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
            raise ValueError("bounded artifact contract is invalid")
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
) -> int:
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    root = Path(__file__).resolve().parents[1] if repo_root is None else Path(repo_root).resolve()
    try:
        args = _parser().parse_args(argv)
        validate_readme_contract(root / "README.md")
        extension_digest = validate_context_contract(
            root / "asterion/src/asterion/dci/resources/context-profiles.json",
            root / "asterion/src/asterion/dci/resources/pi/context-extension-manifest.json",
            root / "asterion/src/asterion/dci/resources/pi/dci-context-extension.ts",
        )
        if args.level == "local":
            stdout.write("PASS\nAgent operations: 0\nJudge operations: 0\nFull dataset ran: no\n")
            return 0
        if args.env_file is None or args.output_root is None:
            raise ValueError("bounded verification requires --env-file and --output-root")
        output_root = _prepare_private_root(args.output_root)
        environment = _load_env_file(args.env_file.resolve(), os.environ)
        environment["PYTHONPATH"] = str(root / "src")
        cases = (("quick-start-programmatic", None), ("context-level3", "level3"), ("context-level4", "level4"))
        records = []
        for command_id, profile in cases:
            output_dir = output_root / command_id
            completed = executor(
                _runner_command(root, output_dir, profile),
                cwd=root,
                env=environment,
                check=False,
                text=True,
            )
            if completed.returncode != 0:
                raise ValueError(f"bounded command failed: {command_id}")
            hashes = _artifact_hashes(output_dir)
            config = json.loads((output_dir / "effective-config.json").read_text(encoding="utf-8"))
            records.append({"command_id": command_id, "effective_config_sha256": config["identity_sha256"], "private_artifact_sha256": hashes})
        report = {
            "schema": "dci.original-readme-acceptance/v1",
            "mode": "bounded",
            "command_ids": [item["command_id"] for item in records],
            "agent_operations": 3,
            "judge_operations": 0,
            "full_dataset_ran": False,
            "context_extension_sha256": extension_digest,
            "commands": records,
        }
        report_path = output_root / "original-readme-acceptance.json"
        report_path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        report_path.chmod(0o600)
        stdout.write("PASS\nAgent operations: 3\nJudge operations: 0\nFull dataset ran: no\n")
        return 0
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        stderr.write(f"Original README verification failed: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(verify_original_readme_main())
