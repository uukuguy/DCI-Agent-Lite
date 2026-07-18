#!/usr/bin/env python3
"""Coordinate AF-340 provider-free, bounded, retained, and authorized checks."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from io import StringIO
from pathlib import Path
from typing import NamedTuple, TextIO


REPORT_SCHEMA = "dci.af340-reproduction/v1"
FULL_REPORT_SCHEMA = "dci.af340-full-reproduction/v2"
RETAINED_DIMENSIONS = frozenset(
    {
        "original-pi",
        "asterion-pi",
        "asterion-claude-subscription",
        "asterion-claude-minimax",
    }
)
LOCAL_CHECK_IDS = (
    "scope-governance",
    "original-readme-local",
    "configuration-and-judge",
    "launcher-contracts",
    "profile-and-reproduction-contracts",
    "product-source-wheel",
    "documentation-contracts",
)
_LAUNCHERS = (
    ("bcplus_eval/run_bcplus_eval_openai.sh", ("level3", "high"), True),
    ("qa/run_2wikimultihopqa_dev_sample50.sh", (), True),
    ("qa/run_bamboogle_test_sample50.sh", (), True),
    ("qa/run_hotpotqa_dev_sample50.sh", (), True),
    ("qa/run_musique_dev_sample50.sh", (), True),
    ("qa/run_nq_test_sample50.sh", (), True),
    ("qa/run_triviaqa_test_sample50.sh", (), True),
    ("bright/run_bio.sh", (), False),
    ("bright/run_earth_science.sh", (), False),
    ("bright/run_economics.sh", (), False),
    ("bright/run_robotics.sh", (), False),
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_BOUNDED_NATIVE_NAMES = frozenset(
    {"request.json", "state.json", "events.jsonl", "eval_result.json", "effective-config.json", "config.json", "native-config.json"}
)


class Operation(NamedTuple):
    operation_id: str
    kind: str
    command: tuple[str, ...]


class OperationResult(NamedTuple):
    """Body-free facts measured by an execution adapter, never planned counts."""

    status: str
    agent_operations: int
    judge_operations: int
    artifacts: Mapping[str, bytes]


class BoundedPreflight(NamedTuple):
    environment: Mapping[str, str]
    wheel_asterion: Path
    cleanup_root: Path | None = None


class FullRunResult(NamedTuple):
    agent_operations: int
    judge_operations: int
    full_dataset_ran: bool = False


class FullScopeRequest(NamedTuple):
    product: str
    scope_id: str
    authorization: object
    output_root: Path
    profile: object
    repo_root: Path


class FullScopeResult(NamedTuple):
    agent_operations: int
    judge_operations: int
    manifest: object


FullRunner = Callable[..., FullRunResult]


def local_operation_plan(repo_root: Path) -> tuple[Operation, ...]:
    python = sys.executable
    return (
        Operation("scope-governance", "local", (python, "tools/project_scope_check.py")),
        Operation(
            "original-readme-local",
            "local",
            (python, "tools/verify_original_readme.py", "--level", "local"),
        ),
        Operation(
            "configuration-and-judge",
            "local",
            (
                python,
                "-m",
                "unittest",
                "-v",
                "tests.test_effective_config",
                "tests.test_asterion_dci_config",
                "tests.test_judge",
                "tests.test_asterion_dci_judge",
            ),
        ),
        Operation(
            "launcher-contracts",
            "local",
            (
                python,
                "-m",
                "unittest",
                "-v",
                "tests.test_asterion_dci_batch_launchers",
                "tests.test_asterion_dci_product_parity",
            ),
        ),
        Operation(
            "profile-and-reproduction-contracts",
            "local",
            (
                python,
                "-m",
                "unittest",
                "-v",
                "tests.test_asterion_dci_experiment_profiles",
                "tests.test_asterion_dci_reproduction",
            ),
        ),
        Operation(
            "product-source-wheel",
            "local",
            (python, "tools/verify_asterion_dci_product.py"),
        ),
        Operation(
            "documentation-contracts",
            "local",
            (python, "-m", "unittest", "-v", "tests.test_asterion_documentation"),
        ),
    )


def _original_runner(profile: str | None) -> tuple[str, ...]:
    command = [
        sys.executable,
        "src/dci/benchmark/pi_rpc_runner.py",
        "--runtime",
        "pi",
        "--cwd",
        "{PRESSURE_CORPUS}" if profile else "corpus/wiki_corpus",
        "--output-dir",
        "{OUTPUT_ROOT}/" + ("original-quick-start" if profile is None else f"original-{profile}"),
        "--max-turns",
        "8",
        "--rpc-timeout-seconds",
        "300",
    ]
    if profile is not None:
        command.extend(("--runtime-context-level", profile, "--keep-session"))
        for _ in range(12):
            command.extend(("--prelude-question", "Reply only with ok."))
        command.append("Use five separate sed tool calls to inspect pressure.txt, then reply only done.")
    else:
        command.append("In which street did the Great Fire of London originate?")
    return tuple(command)


def _asterion_run(
    runtime: str,
    suffix: str,
    *,
    context_profile: str | None = None,
) -> tuple[str, ...]:
    command = [
        "uv",
        "run",
        "--project",
        "asterion",
        "asterion-dci",
        "run",
        "--runtime",
        runtime,
        "--cwd",
        "{PRESSURE_CORPUS}" if context_profile else "corpus/wiki_corpus",
        "--output-dir",
        f"{{OUTPUT_ROOT}}/{suffix}",
        "--max-turns",
        "8",
    ]
    if context_profile:
        command.extend(("--runtime-context-level", context_profile))
        command.append("Use five separate sed tool calls to inspect pressure.txt, then reply only done.")
    else:
        command.append("In which street did the Great Fire of London originate?")
    return tuple(command)


def _installed_application(runtime: str, suffix: str, *, provider: str | None = None, model: str | None = None) -> tuple[str, ...]:
    del provider, model
    command = [
        "uv",
        "run",
        "--project",
        "asterion",
        "asterion",
        "run",
        "--provider",
        "dci-agent-lite",
        "--application",
        "dci.complete-application@1.0.0",
        "--runtime",
        f"{runtime}.reference",
        "--run-id",
        suffix,
        "--input",
        json.dumps(
            {
                "protocol": "asterion.dci.complete-input/v1",
                "question": "Using only wiki_dump.jsonl, where did the Great Fire of London originate?",
                "gold_answer": "Pudding Lane",
            },
            sort_keys=True,
        ),
    ]
    return tuple(command)


def _wheel_application(runtime: str, suffix: str, *, provider: str | None = None, model: str | None = None) -> tuple[str, ...]:
    del provider, model
    command = [
        "{WHEEL_ASTERION}",
        "run",
        "--provider",
        "dci-agent-lite",
        "--application",
        "dci.complete-application@1.0.0",
        "--runtime",
        f"{runtime}.reference",
        "--run-id",
        suffix,
        "--input",
        json.dumps(
            {
                "protocol": "asterion.dci.complete-input/v1",
                "question": "Using only wiki_dump.jsonl, where did the Great Fire of London originate?",
                "gold_answer": "Pudding Lane",
            },
            sort_keys=True,
        ),
    ]
    return tuple(command)


def bounded_operation_plan(
    repo_root: Path,
    variant: str,
    provider: str | None,
    model: str | None,
) -> tuple[Operation, ...]:
    del repo_root
    if variant == "claude-subscription":
        if provider is not None or model is not None:
            raise ValueError("Claude subscription bounded identity is invalid")
        return (
            Operation(
                "asterion:installed-claude-subscription",
                "agent-and-judge",
                _installed_application("claude-code", "installed-claude-subscription"),
            ),
            Operation(
                "asterion:wheel-claude-subscription",
                "agent-and-judge",
                _wheel_application("claude-code", "wheel-claude-subscription"),
            ),
        )
    if variant == "claude-minimax":
        if provider not in {"minimax", "minimax-cn"} or not model:
            raise ValueError("Claude MiniMax bounded identity is required")
        return (
            Operation(
                "asterion:installed-claude-minimax",
                "agent-and-judge",
                _installed_application(
                    "claude-code", "installed-claude-minimax", provider=provider, model=model
                ),
            ),
            Operation(
                "asterion:wheel-claude-minimax",
                "agent-and-judge",
                _wheel_application(
                    "claude-code", "wheel-claude-minimax", provider=provider, model=model
                ),
            ),
        )
    if variant != "pi" or provider is not None or model is not None:
        raise ValueError("Pi bounded identity is invalid")
    operations: list[Operation] = [
        Operation("original:quick-start", "agent", _original_runner(None)),
        Operation("original:context-level3", "agent", _original_runner("level3")),
        Operation("original:context-level4", "agent", _original_runner("level4")),
    ]
    for product, prefix in (("original", "scripts"), ("asterion", "asterion/scripts")):
        for relative, leading, judged in _LAUNCHERS:
            operations.append(
                Operation(
                    f"launcher:{product}:{relative}",
                    "agent-and-judge" if judged else "agent",
                    (
                        "bash",
                        f"{prefix}/{relative}",
                        *leading,
                        "--limit",
                        "1",
                        "--output-root",
                        f"{{OUTPUT_ROOT}}/launchers/{product}/{relative.replace('/', '-')}",
                        "--resume-policy",
                        "fresh",
                    ),
                )
            )
    operations.extend(
        (
            Operation("asterion:pi-quick-start", "agent", _asterion_run("pi", "asterion-pi-quick")),
            Operation("asterion:pi-context-level3", "agent", _asterion_run("pi", "asterion-pi-level3", context_profile="level3")),
            Operation("asterion:pi-context-level4", "agent", _asterion_run("pi", "asterion-pi-level4", context_profile="level4")),
            Operation("asterion:installed-pi", "agent-and-judge", _installed_application("pi", "installed-pi")),
            Operation("asterion:wheel-pi", "agent-and-judge", _wheel_application("pi", "wheel-pi")),
        )
    )
    return tuple(operations)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="verify_af340_reproduction.py")
    commands = parser.add_subparsers(dest="mode", required=True)
    commands.add_parser("local")
    bounded = commands.add_parser("bounded")
    bounded.add_argument(
        "--variant", choices=("pi", "claude-subscription", "claude-minimax"), required=True
    )
    bounded.add_argument("--env-file", type=Path, required=True)
    bounded.add_argument("--output-root", type=Path, required=True)
    bounded.add_argument("--provider")
    bounded.add_argument("--model")
    full = commands.add_parser("full")
    full.add_argument("--profile", required=True)
    full.add_argument("--output-root", type=Path, required=True)
    full.add_argument("--estimated-budget-usd", type=float, required=True)
    full.add_argument("--authorize-full", action="store_true")
    full.add_argument("--dry-run", action="store_true")
    full.add_argument("--provider")
    full.add_argument("--model")
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--report", type=Path, action="append", required=True)
    inspect_full = commands.add_parser("inspect-full")
    inspect_full.add_argument("--report", type=Path, required=True)
    return parser


def _private_root(path: Path) -> Path:
    requested = Path(os.path.abspath(os.path.normpath(path.expanduser())))
    if requested.is_symlink() or requested.exists():
        raise ValueError("AF-340 output root must be fresh")
    requested = requested.parent.resolve() / requested.name
    requested.mkdir(parents=True, mode=0o700)
    requested.chmod(0o700)
    return requested


def _preflight_env_file(path: Path) -> Path:
    resolved = path.expanduser()
    if resolved.is_symlink() or not resolved.is_file():
        raise ValueError("AF-340 bounded environment file is invalid")
    return resolved.resolve()


def _bounded_environment(path: Path) -> dict[str, str]:
    environment = dict(os.environ)
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        environment.setdefault(name.strip(), value.strip().strip("\"'"))
    return environment


def _root_environment(root: Path) -> dict[str, str]:
    """Load the repository .env without overriding the invoking process."""

    path = root / ".env"
    if not path.exists():
        return dict(os.environ)
    if path.is_symlink() or not path.is_file():
        raise ValueError("AF-340 environment configuration is invalid")
    return _bounded_environment(path)


def _render_command(
    operation: Operation, output_root: Path, wheel_asterion: Path
) -> tuple[str, ...]:
    pressure_corpus = output_root / "private-pressure-corpus"
    return tuple(
        value.replace("{OUTPUT_ROOT}", str(output_root)).replace(
            "{WHEEL_ASTERION}", str(wheel_asterion)
        ).replace("{PRESSURE_CORPUS}", str(pressure_corpus))
        for value in operation.command
    )


def _write_pressure_corpus(output_root: Path) -> None:
    corpus = output_root / "private-pressure-corpus"
    corpus.mkdir(mode=0o700)
    # Deterministic local pressure, large enough to force the configured L3/L4 path.
    payload = ("AF340_CONTEXT_PRESSURE " + ("x" * 4000) + "\n") * 1024
    pressure = corpus / "pressure.txt"
    pressure.write_text(payload, encoding="utf-8")
    pressure.chmod(0o600)


def _command_sha256(command: Sequence[str]) -> str:
    return hashlib.sha256("\0".join(command).encode("utf-8")).hexdigest()


def _operation_counts(operations: Sequence[Operation]) -> tuple[int, int]:
    agent = sum(item.kind in {"agent", "agent-and-judge"} for item in operations)
    judge = sum(item.kind in {"judge", "agent-and-judge"} for item in operations)
    return agent, judge


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _plan_sha256(operations: Sequence[Operation]) -> str:
    return _canonical_sha256(
        [
            {"operation_id": item.operation_id, "kind": item.kind, "command": item.command}
            for item in operations
        ]
    )


def _safe_slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]+", "-", value)


def _store_private_artifacts(
    root: Path, operation_id: str, artifacts: Mapping[str, bytes]
) -> dict[str, dict[str, str]]:
    private_root = root / "private"
    private_root.mkdir(mode=0o700, exist_ok=True)
    private_root.chmod(0o700)
    operation_root = private_root / _safe_slug(operation_id)
    operation_root.mkdir(mode=0o700)
    retained: dict[str, dict[str, str]] = {}
    for name, body in sorted(artifacts.items()):
        if not re.fullmatch(r"[a-z][a-z0-9_.-]*", name) or type(body) is not bytes:
            raise ValueError("AF-340 execution artifact is invalid")
        target = operation_root / name
        target.write_bytes(body)
        target.chmod(0o600)
        retained[name] = {
            "ref": target.relative_to(root).as_posix(),
            "sha256": hashlib.sha256(body).hexdigest(),
        }
    return retained


def _coerce_operation_result(completed: object) -> OperationResult:
    if isinstance(completed, OperationResult):
        result = completed
    elif all(
        hasattr(completed, name)
        for name in ("status", "agent_operations", "judge_operations", "artifacts")
    ):
        result = OperationResult(
            completed.status,
            completed.agent_operations,
            completed.judge_operations,
            completed.artifacts,
        )
    else:
        status_value = "completed" if getattr(completed, "returncode", 1) == 0 else "failed"
        stdout = str(getattr(completed, "stdout", "")).encode()
        stderr = str(getattr(completed, "stderr", "")).encode()
        # A generic subprocess cannot truthfully prove provider-call counts or effective
        # configuration. It is therefore never accepted as successful retained evidence.
        result = OperationResult(status_value, 0, 0, {"stdout.txt": stdout, "stderr.txt": stderr})
    if (
        result.status not in {"completed", "failed", "timed_out", "cancelled"}
        or isinstance(result.agent_operations, bool)
        or isinstance(result.judge_operations, bool)
        or min(result.agent_operations, result.judge_operations) < 0
    ):
        raise ValueError("AF-340 execution result is invalid")
    if result.status == "completed" and (
        result.agent_operations + result.judge_operations == 0
        or "effective-config.json" not in result.artifacts
    ):
        raise ValueError("AF-340 successful execution lacks measured evidence")
    return result


def _bounded_native_snapshot(root: Path) -> dict[Path, str]:
    """Hash only bounded native control evidence, never answer/conversation bodies."""

    snapshot: dict[Path, str] = {}
    for path in root.rglob("*"):
        if not path.is_file() or path.is_symlink():
            continue
        if path.name not in _BOUNDED_NATIVE_NAMES and not re.fullmatch(
            r"attempt-[0-9]{4}\.request\.json", path.name
        ):
            continue
        snapshot[path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return snapshot


def _read_native_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return None


def _native_run_root(path: Path) -> Path:
    if re.fullmatch(r"attempt-[0-9]{4}\.request\.json", path.name):
        return path.parent.parent
    return path.parent


def _completed_claude_events(path: Path) -> bool:
    try:
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    return bool(rows and isinstance(rows[-1], dict) and rows[-1].get("type") == "run.completed")


def _bounded_native_operation_result(
    *,
    completed: object,
    before: Mapping[Path, str],
    output_root: Path,
    operation: Operation,
    command: Sequence[str],
    variant: str,
    provider: str | None,
    model: str | None,
) -> OperationResult:
    """Project one subprocess and its new native artifacts into body-free evidence."""

    after = _bounded_native_snapshot(output_root)
    changed = tuple(
        path for path, digest in after.items() if before.get(path) != digest
    )
    pi_request_roots: set[Path] = set()
    pi_completed_roots: set[Path] = set()
    claude_request_roots: set[Path] = set()
    claude_completed_roots: set[Path] = set()
    judge_roots: set[Path] = set()
    native_artifacts: list[dict[str, str]] = []
    retained_native: dict[str, bytes] = {}
    for index, path in enumerate(sorted(changed), start=1):
        document = _read_native_json(path) if path.suffix == ".json" else None
        run_root = _native_run_root(path)
        if re.fullmatch(r"attempt-[0-9]{4}\.request\.json", path.name):
            if isinstance(document, dict):
                pi_request_roots.add(_native_run_root(path))
        elif path.name == "state.json":
            if isinstance(document, dict) and document.get("status") == "completed":
                pi_completed_roots.add(path.parent)
        elif path.name == "request.json":
            if isinstance(document, dict) and isinstance(document.get("run_id"), str):
                claude_request_roots.add(path.parent)
        elif path.name == "events.jsonl" and _completed_claude_events(path):
            claude_completed_roots.add(path.parent)
        elif path.name == "eval_result.json":
            if isinstance(document, dict) and isinstance(document.get("is_correct"), bool):
                judge_roots.add(path.parent)
        artifact_name = f"native-{index:04d}-{path.name}"
        retained_native[artifact_name] = path.read_bytes()
        native_artifacts.append(
            {
                "artifact": artifact_name,
                "kind": path.name,
                "root_ref": run_root.relative_to(output_root).as_posix(),
                "sha256": after[path],
            }
        )

    agent_roots = (pi_request_roots & pi_completed_roots) | (
        claude_request_roots & claude_completed_roots
    )
    for native_root in agent_roots | judge_roots:
        _validate_private_tree(native_root)
    agent_count = len(agent_roots)
    judge_count = len(judge_roots)
    expected_agent = int(operation.kind in {"agent", "agent-and-judge"})
    expected_judge = int(operation.kind in {"judge", "agent-and-judge"})
    returncode = getattr(completed, "returncode", 1)
    status_value = "completed" if returncode == 0 else "failed"
    if (agent_count, judge_count) != (expected_agent, expected_judge):
        status_value = "failed"
    stdout_body = str(getattr(completed, "stdout", "")).encode()
    stderr_body = str(getattr(completed, "stderr", "")).encode()
    identity = {
        "schema": "dci.af340-effective-config/v1",
        "operation_id": operation.operation_id,
        "kind": operation.kind,
        "variant": variant,
        "runtime": _bounded_runtime_identity(variant, provider),
        "provider": provider,
        "model": model,
        "rendered_command_sha256": _command_sha256(command),
        "command_template_sha256": _command_sha256(operation.command),
        "native_artifacts": native_artifacts,
        "actual_counts": {"agent": agent_count, "judge": judge_count},
        "process": {
            "status": status_value,
            "returncode": returncode,
            "stdout_sha256": hashlib.sha256(stdout_body).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr_body).hexdigest(),
        },
    }
    return OperationResult(
        status_value,
        agent_count,
        judge_count,
        {
            "effective-config.json": json.dumps(identity, sort_keys=True).encode() + b"\n",
            **retained_native,
        },
    )


def _coordinator_bounded_result(
    outcome: OperationResult,
    *,
    operation: Operation,
    command: Sequence[str],
    variant: str,
    provider: str | None,
    model: str | None,
) -> OperationResult:
    """Replace injected/private artifacts with one exact body-free projection."""

    # Programmatic executor results are useful for orchestration tests, but they
    # are not native provenance.  Never retain executor-authored evidence bytes.
    native_artifacts: list[dict[str, str]] = []
    identity = {
        "schema": "dci.af340-effective-config/v1",
        "operation_id": operation.operation_id,
        "kind": operation.kind,
        "variant": variant,
        "runtime": _bounded_runtime_identity(variant, provider),
        "provider": provider,
        "model": model,
        "command_template_sha256": _command_sha256(operation.command),
        "rendered_command_sha256": _command_sha256(command),
        "native_artifacts": native_artifacts,
        "actual_counts": {
            "agent": outcome.agent_operations,
            "judge": outcome.judge_operations,
        },
        "process": {"status": outcome.status},
    }
    return OperationResult(
        outcome.status,
        outcome.agent_operations,
        outcome.judge_operations,
        {"effective-config.json": json.dumps(identity, sort_keys=True).encode() + b"\n"},
    )


def _write_report(path: Path, report: Mapping[str, object]) -> None:
    path.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    path.chmod(0o600)


def _validate_private_tree(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("AF-340 private tree symlink is invalid")
    for path in (root, *root.rglob("*")):
        if path.is_symlink():
            raise ValueError("AF-340 private tree symlink is invalid")
        mode = stat.S_IMODE(path.stat().st_mode)
        if (path.is_dir() and mode != 0o700) or (path.is_file() and mode != 0o600):
            raise ValueError("AF-340 private tree permissions are invalid")
        if not path.is_dir() and not path.is_file():
            raise ValueError("AF-340 private tree type is invalid")


def _private_tree_sha256(root: Path) -> str:
    _validate_private_tree(root)
    entries: list[dict[str, object]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            entries.append({"path": relative, "type": "directory", "mode": "0700"})
        else:
            entries.append(
                {
                    "path": relative,
                    "type": "file",
                    "mode": "0600",
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                }
            )
    return _canonical_sha256(entries)


def _run_local(
    root: Path,
    executor: Callable[..., object],
    stdout: TextIO,
) -> int:
    for operation in local_operation_plan(root):
        completed = executor(
            operation.command,
            cwd=root,
            check=False,
            text=True,
            capture_output=True,
        )
        succeeded = (
            completed.status == "completed"
            if hasattr(completed, "status")
            else getattr(completed, "returncode", 1) == 0
        )
        if not succeeded:
            raise ValueError(f"AF-340 local check failed: {operation.operation_id}")
    stdout.write("PASS\nAgent operations: 0\nJudge operations: 0\nFull dataset ran: no\n")
    return 0


def _dimensions_for_variant(variant: str) -> list[str]:
    return {
        "pi": ["original-pi", "asterion-pi"],
        "claude-subscription": ["asterion-claude-subscription"],
        "claude-minimax": ["asterion-claude-minimax"],
    }[variant]


def _bounded_runtime_identity(
    variant: str, provider: str | None
) -> dict[str, str]:
    if variant == "pi":
        return {
            "identity": "pi.reference",
            "authentication_mode": "saved-auth-or-provider-key",
        }
    if variant == "claude-subscription":
        return {
            "identity": "claude-code.reference",
            "authentication_mode": "local-subscription",
        }
    return {
        "identity": "claude-code.reference",
        "authentication_mode": (
            "minimax-cn-coding-plan" if provider == "minimax-cn" else "minimax-coding-plan"
        ),
    }


def _run_bounded(
    args: argparse.Namespace,
    root: Path,
    executor: Callable[..., object],
    bounded_preflight: Callable[..., BoundedPreflight],
    stdout: TextIO,
) -> int:
    env_file = _preflight_env_file(args.env_file)
    plan = bounded_operation_plan(root, args.variant, args.provider, args.model)
    for operation in plan:
        for value in operation.command:
            if value.startswith(("scripts/", "asterion/scripts/")) and not (root / value).is_file():
                raise ValueError("AF-340 launcher preflight failed")
    environment = _bounded_environment(env_file)
    if args.variant == "pi":
        environment["DCI_RUNTIME"] = "pi"
    else:
        environment["DCI_RUNTIME"] = "claude-code"
    if args.variant == "claude-subscription":
        environment.pop("DCI_PROVIDER", None)
        environment.pop("DCI_MODEL", None)
    elif args.variant == "claude-minimax":
        environment["DCI_PROVIDER"] = args.provider
        environment["DCI_MODEL"] = args.model
    preflight = bounded_preflight(args, root, plan, environment)
    output_root = _private_root(args.output_root)
    _write_pressure_corpus(output_root)
    environment = dict(preflight.environment)
    environment["ASTERION_RUNTIME_CWD"] = str(root / "corpus/wiki_corpus")
    environment["ASTERION_DCI_OUTPUT_ROOT"] = str(output_root)
    environment["ASTERION_CLAUDE_OUTPUT_ROOT"] = str(output_root / "claude-native")
    records: list[dict[str, object]] = []
    status_value = "passed"
    retainable = executor is subprocess.run
    for operation in plan:
        command = _render_command(operation, output_root, preflight.wheel_asterion)
        native_before = _bounded_native_snapshot(output_root)
        projected_result = False
        try:
            completed = executor(
                command,
                cwd=root,
                env=environment,
                umask=0o077,
                check=False,
                text=True,
                capture_output=True,
            )
            if isinstance(completed, OperationResult) or all(
                hasattr(completed, name)
                for name in ("status", "agent_operations", "judge_operations", "artifacts")
            ):
                outcome = _coerce_operation_result(completed)
                retainable = False
                projected_result = True
            else:
                outcome = _bounded_native_operation_result(
                    completed=completed,
                    before=native_before,
                    output_root=output_root,
                    operation=operation,
                    command=command,
                    variant=args.variant,
                    provider=args.provider,
                    model=args.model,
                )
        except subprocess.TimeoutExpired:
            outcome = OperationResult("timed_out", 0, 0, {})
            projected_result = True
        except KeyboardInterrupt:
            outcome = OperationResult("cancelled", 0, 0, {})
            projected_result = True
        if projected_result:
            outcome = _coordinator_bounded_result(
                outcome,
                operation=operation,
                command=command,
                variant=args.variant,
                provider=args.provider,
                model=args.model,
            )
        retained_artifacts = _store_private_artifacts(
            output_root, operation.operation_id, outcome.artifacts
        )
        records.append(
            {
                "operation_id": operation.operation_id,
                "kind": operation.kind,
                "status": outcome.status,
                "command_sha256": _command_sha256(operation.command),
                "agent_operations": outcome.agent_operations,
                "judge_operations": outcome.judge_operations,
                "artifacts": retained_artifacts,
            }
        )
        if outcome.status != "completed":
            status_value = outcome.status
            break
        if not retainable:
            status_value = "non-retainable"
            break
    agent_count = sum(int(item["agent_operations"]) for item in records)
    judge_count = sum(int(item["judge_operations"]) for item in records)
    report = {
        "schema": REPORT_SCHEMA,
        "mode": "bounded",
        "status": status_value,
        "variant": args.variant,
        "evidence_dimensions": _dimensions_for_variant(args.variant),
        "agent_operations": agent_count,
        "judge_operations": judge_count,
        "attempted_operations": len(records),
        "full_dataset_ran": False,
        "operations": records,
        "plan_sha256": _plan_sha256(plan),
    }
    report["report_sha256"] = _canonical_sha256(report)
    if retainable:
        _write_report(output_root / "af340-bounded-report.json", report)
    if preflight.cleanup_root is not None:
        shutil.rmtree(preflight.cleanup_root)
    if status_value != "passed":
        raise ValueError("AF-340 bounded operation failed")
    stdout.write(
        f"PASS\nAgent operations: {agent_count}\nJudge operations: {judge_count}\nFull dataset ran: no\n"
    )
    return 0


def _default_bounded_preflight(
    args: argparse.Namespace,
    root: Path,
    plan: Sequence[Operation],
    environment: Mapping[str, str],
) -> BoundedPreflight:
    """Finish all local/runtime/input/credential checks before provider dispatch."""

    del plan
    source = str(root / "asterion/src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from asterion.dci.paper_benchmarks import (  # noqa: PLC0415
        paper_benchmark_ids,
        resolve_paper_benchmark,
    )

    for dataset_id in paper_benchmark_ids():
        benchmark = resolve_paper_benchmark(dataset_id)
        dataset = root / benchmark.dataset_path
        corpus = root / benchmark.corpus_path if benchmark.corpus_path else None
        if dataset.is_symlink() or not dataset.is_file():
            raise ValueError("AF-340 dataset/corpus preflight failed")
        if corpus is not None and (corpus.is_symlink() or not corpus.exists()):
            raise ValueError("AF-340 dataset/corpus preflight failed")
    if not environment.get("DEEPSEEK_API_KEY"):
        raise ValueError("AF-340 Judge credential preflight failed")
    if args.variant == "claude-minimax":
        key_name = {
            "minimax": "MINIMAX_API_KEY",
            "minimax-cn": "MINIMAX_CN_API_KEY",
        }.get(args.provider)
        competing = (
            "MINIMAX_CN_API_KEY" if key_name == "MINIMAX_API_KEY" else "MINIMAX_API_KEY"
        )
        if key_name is None or not environment.get(key_name) or environment.get(competing):
            raise ValueError("AF-340 MiniMax credential preflight failed")
    if args.variant.startswith("claude") and shutil.which("claude") is None:
        raise ValueError("AF-340 Claude runtime preflight failed")
    claude_executable = shutil.which("claude") if args.variant.startswith("claude") else None
    if args.variant == "claude-subscription" and not _claude_login_ready(
        claude_executable, environment
    ):
        raise ValueError("AF-340 Claude authentication preflight failed")
    if args.variant == "pi":
        from asterion.dci.config import resolve_dci_paths  # noqa: PLC0415

        paths = resolve_dci_paths(root, environment=environment)
        provider = environment.get("DCI_PROVIDER", "openai-codex").strip() or "openai-codex"
        if (
            not paths.pi.package_dir.is_dir()
            or not paths.pi.agent_dir.is_dir()
            or not _pi_auth_ready(paths.pi.agent_dir, provider, environment)
        ):
            raise ValueError("AF-340 Pi authentication preflight failed")

    setup = Path(tempfile.mkdtemp(prefix="af340-wheel-"))
    setup.chmod(0o700)
    dist = setup / "dist"
    venv = setup / "venv"
    commands = (
        ("uv", "build", "--project", "asterion", "--out-dir", str(dist)),
        ("uv", "venv", str(venv)),
    )
    for command in commands:
        completed = subprocess.run(command, cwd=root, check=False, capture_output=True, text=True)
        if completed.returncode != 0:
            shutil.rmtree(setup)
            raise ValueError("AF-340 wheel build preflight failed")
    wheels = tuple(dist.glob("*.whl"))
    if len(wheels) != 1:
        shutil.rmtree(setup)
        raise ValueError("AF-340 wheel build preflight failed")
    completed = subprocess.run(
        ("uv", "pip", "install", "--python", str(venv / "bin/python"), str(wheels[0])),
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    wheel_cli = venv / "bin/asterion"
    if completed.returncode != 0 or not wheel_cli.is_file():
        shutil.rmtree(setup)
        raise ValueError("AF-340 wheel install preflight failed")
    return BoundedPreflight(dict(environment), wheel_cli, setup)


def _provider_key_name(provider: str) -> str | None:
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", provider) is None:
        return None
    aliases = {
        "google": "GOOGLE_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "openai-codex": "OPENAI_API_KEY",
    }
    return aliases.get(provider.lower(), f"{provider.upper().replace('-', '_')}_API_KEY")


def _pi_auth_ready(
    agent_dir: Path, provider: str, environment: Mapping[str, str]
) -> bool:
    key_name = _provider_key_name(provider)
    if key_name is not None and environment.get(key_name, "").strip():
        return True
    path = agent_dir / "auth.json"
    if path.is_symlink() or not path.is_file():
        return False
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    if not isinstance(document, dict):
        return False
    credential = document.get(provider)
    if not isinstance(credential, dict):
        return False
    credential_type = credential.get("type")
    if credential_type == "api_key":
        return isinstance(credential.get("key"), str) and bool(
            credential["key"].strip()
        )
    if credential_type == "oauth":
        refresh = credential.get("refresh")
        if isinstance(refresh, str) and refresh.strip():
            return True
        access = credential.get("access")
        if not isinstance(access, str) or not access.strip():
            return False
        expires = credential.get("expires")
        if isinstance(expires, bool) or expires is None:
            return expires is None
        if not isinstance(expires, (int, float)):
            return False
        now = time.time() * (1000 if expires > 1_000_000_000_000 else 1)
        return expires > now
    return False


def _claude_login_ready(
    executable: str | None, environment: Mapping[str, str]
) -> bool:
    if executable is None:
        return False
    completed = subprocess.run(
        (executable, "auth", "status", "--json"),
        env=dict(environment),
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return False
    try:
        document = json.loads(completed.stdout)
    except (TypeError, ValueError):
        return False
    return isinstance(document, dict) and (
        document.get("loggedIn") is True
        or document.get("authenticated") is True
        or document.get("status") in {"logged_in", "authenticated"}
    )


def _asterion_profile_api(root: Path):
    source = str(root / "asterion/src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from asterion.dci.experiment_profiles import (  # noqa: PLC0415
        authorize_full_execution,
        experiment_profile_sha256,
        resolve_experiment_profile,
    )
    from asterion.dci.paper_benchmarks import (  # noqa: PLC0415
        paper_benchmark_ids,
        resolve_paper_benchmark,
        resolve_paper_experiment_scope,
    )

    return (
        authorize_full_execution,
        experiment_profile_sha256,
        resolve_experiment_profile,
        paper_benchmark_ids,
        resolve_paper_benchmark,
        resolve_paper_experiment_scope,
    )


def _full_preflight(args: argparse.Namespace, root: Path) -> tuple[object, dict[str, object]]:
    (
        _,
        profile_digest,
        resolve_profile,
        benchmark_ids,
        resolve_benchmark,
        resolve_scope,
    ) = _asterion_profile_api(root)
    if not math.isfinite(args.estimated_budget_usd) or args.estimated_budget_usd < 0:
        raise ValueError("AF-340 full budget is invalid")
    if args.output_root.exists() or args.output_root.is_symlink():
        raise ValueError("AF-340 full output root must be fresh")
    profile = resolve_profile(
        args.profile,
        invocation_provider=args.provider,
        invocation_model=args.model,
    )
    selected_count = sum(resolve_scope(scope).selection_count for scope in profile.scope_ids)
    judge_count = sum(
        resolve_scope(scope).selection_count
        for scope in profile.scope_ids
        if resolve_benchmark(resolve_scope(scope).dataset_id).mode == "qa"
    )
    return profile, {
        "profile_sha256": profile_digest(
            args.profile,
            invocation_provider=args.provider,
            invocation_model=args.model,
        ),
        "dataset_count": len(benchmark_ids()),
        "scope_count": len(profile.scope_ids),
        "selected_count": selected_count,
        "agent_maximum": selected_count * (2 if profile.runtime == "pi" else 1),
        "judge_maximum": judge_count * (2 if profile.runtime == "pi" else 1),
    }


def _print_full_plan(
    args: argparse.Namespace, profile: object, plan: Mapping[str, object], stdout: TextIO
) -> None:
    stdout.write(f"Profile: {profile.profile_id}\n")
    stdout.write(f"Profile SHA-256: {plan['profile_sha256']}\n")
    stdout.write(f"Dataset inventory SHA-256: {profile.dataset_inventory_sha256}\n")
    stdout.write(f"Experiment scopes SHA-256: {profile.experiment_scopes_sha256}\n")
    stdout.write(f"Datasets: {plan['dataset_count']}\n")
    stdout.write(f"Experiment scopes: {plan['scope_count']}\n")
    stdout.write(f"Selected queries: {plan['selected_count']}\n")
    stdout.write(f"Maximum agent operations: {plan['agent_maximum']}\n")
    stdout.write(f"Maximum Judge operations: {plan['judge_maximum']}\n")
    stdout.write(f"Estimated budget USD: {args.estimated_budget_usd:g}\n")
    output_identity = str(Path(os.path.abspath(os.path.normpath(args.output_root))))
    stdout.write(
        "Output root identity SHA-256: "
        + hashlib.sha256(output_identity.encode()).hexdigest()
        + "\n"
    )
    stdout.write(
        "Comparison root identity SHA-256: "
        + hashlib.sha256((output_identity + "/comparisons").encode()).hexdigest()
        + "\n"
    )


def _default_full_comparator(baseline: object | None, candidate: object, profile: object) -> object:
    from asterion.dci.reproduction import compare_reproduction_runs  # noqa: PLC0415

    return compare_reproduction_runs(baseline, candidate, profile)


def _default_full_runner(
    authorizations: Mapping[str, Mapping[str, object]],
    profile: object,
    root: Path,
    executor: Callable[..., object],
    comparator: Callable[[object | None, object, object], object],
) -> FullRunResult:
    """Execute every authorized scope and route normalized manifests through Task 7."""

    agent_operations = 0
    judge_operations = 0
    comparison_rejected = False
    for scope_id in profile.scope_ids:
        baseline = None
        if profile.runtime == "pi":
            baseline_result = executor(
                FullScopeRequest(
                    "original-dci",
                    scope_id,
                    authorizations["original-dci"][scope_id],
                    authorizations["original-dci"][scope_id].output_root,
                    profile,
                    root,
                )
            )
            if not isinstance(baseline_result, FullScopeResult):
                raise ValueError("AF-340 original full scope result is invalid")
            baseline = baseline_result.manifest
            agent_operations += baseline_result.agent_operations
            judge_operations += baseline_result.judge_operations
        candidate_result = executor(
            FullScopeRequest(
                "asterion-dci",
                scope_id,
                authorizations["asterion-dci"][scope_id],
                authorizations["asterion-dci"][scope_id].output_root,
                profile,
                root,
            )
        )
        if not isinstance(candidate_result, FullScopeResult):
            raise ValueError("AF-340 Asterion full scope result is invalid")
        agent_operations += candidate_result.agent_operations
        judge_operations += candidate_result.judge_operations
        comparison = comparator(baseline, candidate_result.manifest, profile)
        if hasattr(comparison, "to_dict"):
            from asterion.dci.reproduction import write_comparison_report  # noqa: PLC0415

            product_authorizations = authorizations["asterion-dci"]
            parent_root = next(iter(product_authorizations.values())).output_root.parent.parent
            comparison_root = parent_root / "comparisons"
            comparison_root.mkdir(mode=0o700, exist_ok=True)
            target = comparison_root / f"{_safe_slug(scope_id)}.json"
            write_comparison_report(target, comparison)
            target.chmod(0o600)
        if getattr(comparison, "accepted", None) is False:
            comparison_rejected = True
    if comparison_rejected:
        raise ValueError("AF-340 full comparison rejected [comparison-not-accepted]")
    return FullRunResult(agent_operations, judge_operations, True)


def _read_jsonl(path: Path) -> tuple[dict[str, object], ...]:
    if path.is_symlink() or not path.is_file():
        raise ValueError("AF-340 native analysis evidence is missing")
    rows: list[dict[str, object]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError("AF-340 native analysis evidence is invalid")
        rows.append(value)
    return tuple(rows)


def _native_analysis_rows(request: FullScopeRequest) -> tuple[dict[str, object], ...]:
    if request.product == "asterion-dci":
        return _read_jsonl(request.output_root / "analysis.jsonl")
    if request.product != "original-dci":
        raise ValueError("AF-340 product identity is invalid")
    analysis_path = request.output_root / "analysis.json"
    if analysis_path.is_symlink() or not analysis_path.is_file():
        raise ValueError("AF-340 original analysis evidence is missing")
    try:
        analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        raise ValueError("AF-340 original analysis evidence is invalid") from None
    exact_keys = {
        "generated_at", "cost_efficiency", "slices", "tool_summary", "rankings",
        "incorrect_queries", "per_query_metrics",
    }
    if not isinstance(analysis, dict) or set(analysis) != exact_keys:
        raise ValueError("AF-340 original analysis schema drifted")
    metrics = analysis.get("per_query_metrics")
    if not isinstance(metrics, list) or not all(isinstance(row, dict) for row in metrics):
        raise ValueError("AF-340 original analysis evidence is invalid")
    results = _read_jsonl(request.output_root / "results.jsonl")
    results_by_id: dict[str, dict[str, object]] = {}
    for result in results:
        query_id = result.get("query_id")
        if not isinstance(query_id, str) or query_id in results_by_id:
            raise ValueError("AF-340 original results identity drifted")
        results_by_id[query_id] = result
    metric_ids: set[str] = set()
    for metric in metrics:
        query_id = metric.get("query_id")
        if not isinstance(query_id, str) or query_id in metric_ids or query_id not in results_by_id:
            raise ValueError("AF-340 original analysis identity drifted")
        metric_ids.add(query_id)
        result = results_by_id[query_id]
        for name in ("run_status", "is_correct", "ndcg_at_10"):
            if name in metric and name in result and metric[name] != result[name]:
                raise ValueError("AF-340 original analysis/result evidence drifted")
    if metric_ids != set(results_by_id):
        raise ValueError("AF-340 original analysis/result selection drifted")
    return tuple(results_by_id[query_id] for query_id in sorted(results_by_id))


def _validate_native_summary(
    output_root: Path, rows: Sequence[Mapping[str, object]]
) -> None:
    path = output_root / "summary.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("AF-340 native summary evidence is missing")
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        raise ValueError("AF-340 native summary evidence is invalid") from None
    counts = summary.get("counts") if isinstance(summary, dict) else None
    expected_judged = sum(type(row.get("is_correct")) is bool for row in rows)
    expected_failed = sum(row.get("run_status", row.get("status")) != "completed" for row in rows)
    if (
        not isinstance(counts, Mapping)
        or counts.get("total") != len(rows)
        or counts.get("judged") != expected_judged
        or counts.get("failed_runs") != expected_failed
    ):
        raise ValueError("AF-340 native summary counts drifted")


def _source_dataset_rows(path: Path) -> tuple[dict[str, object], ...]:
    rows = _read_jsonl(path)
    identities: set[str] = set()
    for row in rows:
        query_id = row.get("query_id")
        if not isinstance(query_id, str) or not query_id or query_id in identities:
            raise ValueError("AF-340 source dataset identity is invalid")
        identities.add(query_id)
    return rows


def _scope_selection(repo_root: Path, scope: object, benchmark: object) -> tuple[str, ...]:
    source = str(repo_root / "asterion/src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from asterion.dci.paper_benchmarks import (  # noqa: PLC0415
        published_scope_selected_ids,
        select_and_verify_scope_ids,
    )

    dataset_path = repo_root / benchmark.dataset_path
    if not dataset_path.is_file() and scope.selection_seed_status == "paper-unreported":
        return published_scope_selected_ids(scope.scope_id)
    rows = _source_dataset_rows(dataset_path)
    return select_and_verify_scope_ids(
        scope.scope_id, tuple(str(row["query_id"]) for row in rows)
    )


def _count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError("AF-340 native usage evidence is invalid")
    integer = int(value)
    if integer != value:
        raise ValueError("AF-340 native usage evidence is invalid")
    return integer


def _native_query_evidence(
    row: Mapping[str, object] | None, query_id: str, metric: str
) -> dict[str, object]:
    if row is None:
        return {
            "query_id": query_id,
            "status": "missing",
            "judge_verdict": None,
            "ndcg_at_10": None,
            "failure_class": "dci.missing-evidence/v1",
            "exclusion_reason": None,
            "evidence_sha256": hashlib.sha256(b"missing\0" + query_id.encode()).hexdigest(),
            "operations": {"agent": 0, "judge": 0},
            "tokens": {"input": 0, "cached_input": 0, "output": 0},
            "cost_usd": 0.0,
        }
    if row.get("query_id") != query_id:
        raise ValueError("AF-340 native query identity drifted")
    native_status = row.get("run_status", row.get("status"))
    status_value = native_status if native_status in {"completed", "failed", "cancelled", "timed_out"} else "failed"
    agent_usage = row.get("agent_usage") or {}
    judge_usage = row.get("judge_usage") or {}
    judge_cost = row.get("judge_cost_estimate_usd") or {}
    if not isinstance(agent_usage, Mapping) or not isinstance(judge_usage, Mapping) or not isinstance(judge_cost, Mapping):
        raise ValueError("AF-340 native usage evidence is invalid")
    verdict = row.get("is_correct") if status_value == "completed" else None
    ndcg = row.get("ndcg_at_10") if status_value == "completed" else None
    if metric == "llm-answer-correctness":
        if status_value == "completed" and type(verdict) is not bool:
            raise ValueError("AF-340 native Judge evidence is missing")
        ndcg = None
    else:
        if status_value == "completed" and (
            isinstance(ndcg, bool) or not isinstance(ndcg, (int, float)) or not 0 <= float(ndcg) <= 1
        ):
            raise ValueError("AF-340 native IR evidence is missing")
        verdict = None
    cached = _count(agent_usage.get("cache_read_tokens", 0)) + _count(
        agent_usage.get("cache_write_tokens", 0)
    )
    agent_cost = float(agent_usage.get("cost_total", 0) or 0)
    judge_cost_value = float(judge_cost.get("total_cost", 0) or 0)
    if min(agent_cost, judge_cost_value) < 0 or not all(
        math.isfinite(value) for value in (agent_cost, judge_cost_value)
    ):
        raise ValueError("AF-340 native cost evidence is invalid")
    request_count = row.get("request_count")
    if (
        isinstance(request_count, bool)
        or not isinstance(request_count, (int, float))
        or request_count < 1
    ):
        raise ValueError("AF-340 native agent dispatch evidence is missing")
    judge_ran = type(row.get("is_correct")) is bool
    safe_identity = {
        "query_id": query_id,
        "status": status_value,
        "verdict": verdict,
        "ndcg_at_10": ndcg,
        "agent_usage": dict(agent_usage),
        "judge_usage": dict(judge_usage),
        "cost_usd": agent_cost + judge_cost_value,
    }
    return {
        "query_id": query_id,
        "status": status_value,
        "judge_verdict": verdict,
        "ndcg_at_10": None if ndcg is None else float(ndcg),
        "failure_class": None if status_value == "completed" else f"dci.{status_value}-evidence/v1",
        "exclusion_reason": None,
        "evidence_sha256": _canonical_sha256(safe_identity),
        "operations": {"agent": 1, "judge": int(judge_ran)},
        "tokens": {
            "input": _count(agent_usage.get("input_tokens", 0)) + _count(judge_usage.get("input_tokens", 0)),
            "cached_input": cached,
            "output": _count(agent_usage.get("output_tokens", 0)) + _count(judge_usage.get("output_tokens", 0)),
        },
        "cost_usd": agent_cost + judge_cost_value,
    }


def _native_config_document(request: FullScopeRequest) -> tuple[dict[str, object], bytes]:
    path = request.output_root / "config.json"
    if path.is_symlink() or not path.is_file():
        raise ValueError("AF-340 native effective configuration is missing")
    raw = path.read_bytes()
    try:
        config = json.loads(raw)
    except (UnicodeDecodeError, ValueError):
        raise ValueError("AF-340 native effective configuration is invalid") from None
    if not isinstance(config, dict):
        raise ValueError("AF-340 native effective configuration is invalid")
    profile = request.profile
    judge = profile.judge
    if request.product == "original-dci":
        expected = {
            "provider": profile.provider,
            "model": profile.model,
            "tools": profile.tools,
            "max_turns": profile.max_turns,
            "runtime_context_level": profile.context_profile,
            "pi_thinking_level": profile.reasoning,
            "judge_base_url": judge["base_url"],
            "judge_api": judge["api"],
            "judge_model": judge["model"],
            "judge_api_key_env": judge["key_source"],
            "judge_thinking": "enabled" if judge["thinking"] else "disabled",
            "judge_json_mode": bool(judge["json_object"]),
            "judge_strict_json_schema": (
                judge["output_shape_identity"] == "json-schema/strict/v1"
            ),
            "judge_responses_store": False,
        }
        if any(config.get(name) != value for name, value in expected.items()):
            raise ValueError("AF-340 original effective configuration drifted")
        effective_path = request.output_root / "effective-config.json"
        if effective_path.is_symlink() or not effective_path.is_file():
            raise ValueError("AF-340 original effective configuration is missing")
        effective_raw = effective_path.read_bytes()
        try:
            effective = json.loads(effective_raw)
        except (UnicodeDecodeError, ValueError):
            raise ValueError("AF-340 original effective configuration is invalid") from None
        agent = effective.get("agent") if isinstance(effective, dict) else None
        if (
            not isinstance(effective, dict)
            or effective.get("schema") != "dci.effective-config/v1"
            or effective.get("product") != "original-dci"
            or effective.get("runtime") != "pi"
            or not isinstance(agent, Mapping)
            or agent.get("provider") != profile.provider
            or agent.get("model") != profile.model
            or agent.get("reasoning") != profile.reasoning
            or agent.get("tools") != profile.tools
            or agent.get("max_turns") != profile.max_turns
        ):
            raise ValueError("AF-340 original effective configuration drifted")
        raw += effective_raw
    elif request.product == "asterion-dci" and profile.runtime == "pi":
        runtime = config.get("runtime")
        native_judge = config.get("judge")
        if (
            config.get("schema") != "asterion.dci.batch/v1"
            or config.get("max_turns") != profile.max_turns
            or not isinstance(runtime, Mapping)
            or runtime.get("provider") != profile.provider
            or runtime.get("model") != profile.model
            or runtime.get("tools") != profile.tools
            or runtime.get("runtime_context_level") != profile.context_profile
            or runtime.get("thinking_level") != profile.reasoning
            or not isinstance(native_judge, Mapping)
            or native_judge.get("judge_base_url") != judge["base_url"]
            or native_judge.get("judge_api") != judge["api"]
            or native_judge.get("judge_model") != judge["model"]
            or native_judge.get("judge_api_key_env") != judge["key_source"]
            or native_judge.get("judge_thinking")
            != ("enabled" if judge["thinking"] else "disabled")
            or native_judge.get("judge_json_mode") is not bool(judge["json_object"])
            or native_judge.get("judge_strict_json_schema")
            is not (judge["output_shape_identity"] == "json-schema/strict/v1")
            or native_judge.get("judge_responses_store") is not False
        ):
            raise ValueError("AF-340 Asterion effective configuration drifted")
    elif request.product == "asterion-dci" and profile.runtime == "claude-code":
        expected = {
            "schema": "dci.af340-claude-full-config/v1",
            "product": "asterion-dci",
            "application": "dci.research-capability@1.0.0",
            "runtime": "claude-code.reference",
            "profile_id": profile.profile_id,
            "provider": profile.provider,
            "model": profile.model,
            "authentication_mode": profile.authentication_mode,
            "reasoning": profile.reasoning,
            "tools": profile.tools,
            "max_turns": profile.max_turns,
            "context_profile": profile.context_profile,
            "judge": dict(judge),
            "scope_id": request.scope_id,
        }
        if config != expected:
            raise ValueError("AF-340 Claude effective configuration drifted")
    else:
        raise ValueError("AF-340 native product/runtime configuration is invalid")
    return config, raw


def normalize_full_scope_manifest(
    request: FullScopeRequest, *, write: bool = True
) -> object:
    """Normalize either product's compatible private native metrics into Task 7."""

    source = str(request.repo_root / "asterion/src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from asterion.dci.experiment_profiles import experiment_profile_sha256  # noqa: PLC0415
    from asterion.dci.paper_benchmarks import (  # noqa: PLC0415
        canonical_sha256,
        resolve_paper_benchmark,
        resolve_paper_experiment_scope,
    )
    from asterion.dci.reproduction import (  # noqa: PLC0415
        QueryEvidence,
        RunManifest,
        _computed_aggregates,
        load_run_manifest,
        reproduction_metric_contract_sha256,
    )

    scope = resolve_paper_experiment_scope(request.scope_id)
    benchmark = resolve_paper_benchmark(scope.dataset_id)
    selected = tuple(sorted(_scope_selection(request.repo_root, scope, benchmark)))
    rows = _native_analysis_rows(request)
    _validate_native_summary(request.output_root, rows)
    by_id: dict[str, Mapping[str, object]] = {}
    for row in rows:
        query_id = row.get("query_id")
        if not isinstance(query_id, str) or query_id in by_id or query_id not in selected:
            raise ValueError("AF-340 native analysis selection drifted")
        by_id[query_id] = row
    queries = tuple(
        QueryEvidence.from_mapping(_native_query_evidence(by_id.get(query_id), query_id, benchmark.metric))
        for query_id in selected
    )
    _config, config_raw = _native_config_document(request)
    config_digest = hashlib.sha256(config_raw).hexdigest()
    invocation_provider = (
        request.profile.provider if request.profile.compatible_config_key else None
    )
    invocation_model = (
        request.profile.model if request.profile.compatible_config_key else None
    )
    profile_digest = experiment_profile_sha256(
        request.profile.profile_id,
        invocation_provider=invocation_provider,
        invocation_model=invocation_model,
    )
    effective_digest = canonical_sha256(
        {
            "profile_sha256": profile_digest,
            "scope_id": request.scope_id,
            "selected_ids_sha256": scope.selected_ids_sha256,
        }
    )
    metric_identities = (benchmark.metric,)
    aggregates = _computed_aggregates(queries, metric_identities, request.profile.profile_id)
    implementation_root = request.repo_root / (
        "src/dci" if request.product == "original-dci" else "asterion/src/asterion/dci"
    )
    implementation_digest = hashlib.sha256(
        "".join(
            f"{path.relative_to(implementation_root).as_posix()}\0{hashlib.sha256(path.read_bytes()).hexdigest()}\n"
            for path in sorted(implementation_root.rglob("*.py"))
        ).encode()
    ).hexdigest()
    values: dict[str, object] = {
        "schema": "dci.reproduction-run/v1",
        "run_id": f"af340.{request.product}.{_safe_slug(request.scope_id)}",
        "product": request.product,
        "implementation_sha256": implementation_digest,
        "profile_id": request.profile.profile_id,
        "profile_sha256": profile_digest,
        "runtime": request.profile.runtime,
        "dataset_id": scope.dataset_id,
        "selection_id": request.scope_id,
        "selection_sha256": scope.selected_ids_sha256,
        "effective_config_sha256": effective_digest,
        "product_effective_config_sha256": config_digest,
        "metric_contract_sha256": reproduction_metric_contract_sha256(request.profile.profile_id),
        "metric_identities": list(metric_identities),
        "queries": [query.to_dict() for query in queries],
        "aggregates": aggregates.to_dict(),
    }
    values["identity_sha256"] = canonical_sha256(values)
    if not write:
        return RunManifest.from_mapping(values)
    manifest_path = request.output_root / "af340-run-manifest.json"
    _write_report(manifest_path, values)
    return load_run_manifest(manifest_path)


def _materialize_scope_dataset(request: FullScopeRequest) -> tuple[Path, object, object]:
    source = str(request.repo_root / "asterion/src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from asterion.dci.paper_benchmarks import (  # noqa: PLC0415
        resolve_paper_benchmark,
        resolve_paper_experiment_scope,
    )

    scope = resolve_paper_experiment_scope(request.scope_id)
    benchmark = resolve_paper_benchmark(scope.dataset_id)
    selected = set(_scope_selection(request.repo_root, scope, benchmark))
    rows = _source_dataset_rows(request.repo_root / benchmark.dataset_path)
    chosen = tuple(row for row in rows if row["query_id"] in selected)
    if len(chosen) != len(selected) or {row["query_id"] for row in chosen} != selected:
        raise ValueError("AF-340 full dataset selection preflight failed")
    staging = Path(tempfile.mkdtemp(prefix="af340-scope-dataset-"))
    staging.chmod(0o700)
    dataset = staging / "selected-dataset.jsonl"
    dataset.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in chosen),
        encoding="utf-8",
    )
    dataset.chmod(0o600)
    return dataset, scope, benchmark


def production_full_scope_executor(
    request: FullScopeRequest,
    *,
    process_executor: Callable[..., object] = subprocess.run,
    asterion_runner: Callable[..., object] | None = None,
    dataset_materializer: Callable[[FullScopeRequest], tuple[Path, object, object]] = _materialize_scope_dataset,
) -> FullScopeResult:
    """Execute one exact Task 6 scope through its product-owned native runner."""

    dataset, _scope, benchmark = dataset_materializer(request)
    cleanup_staging = dataset.parent if dataset.parent != request.output_root else None
    try:
        return _execute_production_full_scope(
            request,
            dataset,
            benchmark,
            process_executor=process_executor,
            asterion_runner=asterion_runner,
        )
    finally:
        if cleanup_staging is not None:
            shutil.rmtree(cleanup_staging)


def _claude_full_scope_native_analysis(
    request: FullScopeRequest,
    dataset: Path,
    benchmark: object,
    *,
    process_executor: Callable[..., object],
) -> None:
    """Run each selected row through the installed Claude application surface."""

    source = str(request.repo_root / "asterion/src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from asterion.dci.datasets import build_ir_prompt, build_qa_prompt  # noqa: PLC0415
    from asterion.dci.judge import JudgeConfig, judge_answer_sync  # noqa: PLC0415
    from asterion.dci.metrics import compute_ir_ndcg  # noqa: PLC0415
    from asterion.dci.paper_benchmarks import require_af320_executable_scope  # noqa: PLC0415

    require_af320_executable_scope(request.scope_id, request.authorization)
    rows = _read_jsonl(dataset)
    corpus = request.repo_root / benchmark.corpus_path
    environment = _root_environment(request.repo_root)
    environment["DCI_RUNTIME"] = "claude-code"
    environment["ASTERION_RUNTIME_CWD"] = str(corpus)
    native_root = request.output_root / "native-claude"
    native_root.mkdir(mode=0o700)
    environment["ASTERION_CLAUDE_OUTPUT_ROOT"] = str(native_root)
    environment["DCI_MAX_TURNS"] = str(request.profile.max_turns)
    environment["DCI_MODEL"] = (
        "" if request.profile.model is None else str(request.profile.model)
    )
    environment["DCI_TOOLS"] = str(request.profile.tools)
    environment["DCI_PI_THINKING_LEVEL"] = (
        "" if request.profile.reasoning is None else str(request.profile.reasoning)
    )
    environment["DCI_RUNTIME_CONTEXT_LEVEL"] = (
        ""
        if request.profile.context_profile is None
        else str(request.profile.context_profile)
    )
    if request.profile.provider is None:
        environment["DCI_PROVIDER"] = ""
        for name in (
            "MINIMAX_API_KEY", "MINIMAX_CN_API_KEY", "ANTHROPIC_API_KEY",
            "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_BASE_URL",
        ):
            environment.pop(name, None)
    else:
        environment["DCI_PROVIDER"] = str(request.profile.provider)
        environment["DCI_MODEL"] = str(request.profile.model)
    judge_identity = request.profile.judge
    judge_key = str(judge_identity["key_source"])
    judge_config = JudgeConfig(
        base_url=str(judge_identity["base_url"]),
        api=str(judge_identity["api"]),
        model=str(judge_identity["model"]),
        api_key_env=judge_key,
        api_key=environment[judge_key],
        json_mode=bool(judge_identity["json_object"]),
        strict_json_schema=(
            judge_identity["output_shape_identity"] == "json-schema/strict/v1"
        ),
        responses_store=False,
        thinking="enabled" if judge_identity["thinking"] else "disabled",
    )
    analysis_rows: list[dict[str, object]] = []
    for row in rows:
        query_id = row.get("query_id")
        query = row.get("query")
        if not isinstance(query_id, str) or not isinstance(query, str):
            raise ValueError("AF-340 Claude dataset row is invalid")
        run_id = "af340-" + hashlib.sha256(
            f"{request.scope_id}\0{query_id}".encode()
        ).hexdigest()
        prompt = (
            build_ir_prompt(query, corpus)
            if benchmark.mode == "ir"
            else build_qa_prompt(query, corpus)
        )
        command = (
            "uv", "run", "--project", "asterion", "asterion", "run",
            "--provider", "dci-agent-lite",
            "--application", "dci.research-capability@1.0.0",
            "--runtime", "claude-code.reference",
            "--run-id", run_id,
            "--input", prompt,
        )
        completed = process_executor(
            command,
            cwd=request.repo_root,
            env=environment,
            umask=0o077,
            check=False,
            capture_output=True,
            text=True,
        )
        native = native_root / hashlib.sha256(run_id.encode()).hexdigest()
        events = _read_jsonl(native / "events.jsonl")
        if (
            completed.returncode != 0
            or not events
            or events[0].get("type") != "run.started"
            or events[-1].get("type") != "run.completed"
        ):
            raise ValueError("AF-340 Claude installed application execution failed")
        final_path = native / "final.txt"
        if final_path.is_symlink() or not final_path.is_file():
            raise ValueError("AF-340 Claude native answer evidence is missing")
        final_text = final_path.read_text(encoding="utf-8").rstrip("\n")
        if not final_text:
            raise ValueError("AF-340 Claude native answer evidence is invalid")
        runtime_policy = _read_native_json(native / "runtime-policy.json")
        if (
            not isinstance(runtime_policy, Mapping)
            or runtime_policy.get("agent_model") != request.profile.model
            or runtime_policy.get("reasoning") != request.profile.reasoning
            or runtime_policy.get("tools")
            != [part.title() for part in str(request.profile.tools).split(",")]
            or runtime_policy.get("context_profile") != request.profile.context_profile
            or runtime_policy.get("max_turns") != request.profile.max_turns
        ):
            raise ValueError("AF-340 Claude native runtime policy drifted")
        input_tokens = 0
        output_tokens = 0
        usage_events = 0
        for event in events:
            if event.get("type") != "usage.reported":
                continue
            payload = event.get("payload")
            if not isinstance(payload, Mapping):
                raise ValueError("AF-340 Claude native usage evidence is invalid")
            input_tokens += _count(payload.get("input_tokens"))
            output_tokens += _count(payload.get("output_tokens"))
            usage_events += 1
        if usage_events != 1:
            raise ValueError("AF-340 Claude native usage evidence is invalid")
        verdict: dict[str, object] | None = None
        ndcg: float | None = None
        if benchmark.mode == "ir":
            ndcg = compute_ir_ndcg(final_text, row, corpus)
        else:
            gold = row.get("answer")
            if not isinstance(gold, str) or not gold:
                raise ValueError("AF-340 Claude Judge input evidence is invalid")
            verdict = judge_answer_sync(
                config=judge_config,
                question=query,
                gold_answer=gold,
                predicted_answer=final_text,
            )
            if type(verdict.get("is_correct")) is not bool:
                raise ValueError("AF-340 Claude Judge evidence is invalid")
            _write_report(native / "eval_result.json", verdict)
        judge_usage = {} if verdict is None else verdict.get("usage", {})
        judge_cost = {} if verdict is None else verdict.get("cost_estimate_usd", {})
        if not isinstance(judge_usage, Mapping) or not isinstance(judge_cost, Mapping):
            raise ValueError("AF-340 Claude Judge usage evidence is invalid")
        _write_report(
            native / "application-process.json",
            {
                "returncode": completed.returncode,
                "command_sha256": _command_sha256(command),
                "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
                "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
            },
        )
        analysis_rows.append(
            {
                "query_id": query_id,
                "run_status": "completed",
                "request_count": 1,
                "is_correct": None if verdict is None else verdict["is_correct"],
                "ndcg_at_10": ndcg,
                "agent_usage": {
                    "input_tokens": input_tokens,
                    "cache_read_tokens": 0,
                    "cache_write_tokens": 0,
                    "output_tokens": output_tokens,
                    "cost_total": 0.0,
                },
                "judge_usage": dict(judge_usage),
                "judge_cost_estimate_usd": dict(judge_cost),
                "native_evidence_sha256": _canonical_sha256(
                    {
                        "events": hashlib.sha256((native / "events.jsonl").read_bytes()).hexdigest(),
                        "final": hashlib.sha256(final_path.read_bytes()).hexdigest(),
                    }
                ),
            }
        )
    config = {
        "schema": "dci.af340-claude-full-config/v1",
        "product": request.product,
        "application": "dci.research-capability@1.0.0",
        "runtime": "claude-code.reference",
        "profile_id": request.profile.profile_id,
        "provider": request.profile.provider,
        "model": request.profile.model,
        "authentication_mode": request.profile.authentication_mode,
        "reasoning": request.profile.reasoning,
        "tools": request.profile.tools,
        "max_turns": request.profile.max_turns,
        "context_profile": request.profile.context_profile,
        "judge": dict(judge_identity),
        "scope_id": request.scope_id,
    }
    _write_report(request.output_root / "config.json", config)
    analysis_path = request.output_root / "analysis.jsonl"
    analysis_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in analysis_rows),
        encoding="utf-8",
    )
    analysis_path.chmod(0o600)
    _write_report(
        request.output_root / "summary.json",
        {
            "counts": {
                "total": len(analysis_rows),
                "judged": sum(type(row["is_correct"]) is bool for row in analysis_rows),
                "failed_runs": 0,
            }
        },
    )


def _execute_production_full_scope(
    request: FullScopeRequest,
    dataset: Path,
    benchmark: object,
    *,
    process_executor: Callable[..., object],
    asterion_runner: Callable[..., object] | None,
) -> FullScopeResult:
    if request.product == "original-dci":
        source = str(request.repo_root / "asterion/src")
        if source not in sys.path:
            sys.path.insert(0, source)
        from asterion.dci.paper_benchmarks import require_af320_executable_scope  # noqa: PLC0415

        require_af320_executable_scope(request.scope_id, request.authorization)
        command = [
            "uv", "run", "python", "scripts/bcplus_eval/run_bcplus_eval.py",
            "--dataset", str(dataset),
            "--output-root", str(request.output_root),
            "--corpus-dir", str(request.repo_root / benchmark.corpus_path),
            "--runtime", "pi",
            "--provider", str(request.profile.provider),
            "--model", str(request.profile.model),
            "--tools", str(request.profile.tools),
            "--max-turns", str(request.profile.max_turns),
            "--runtime-context-level", str(request.profile.context_profile),
            "--max-concurrency", "1",
            "--judge-base-url", str(request.profile.judge["base_url"]),
            "--judge-api", str(request.profile.judge["api"]),
            "--judge-model", str(request.profile.judge["model"]),
            "--judge-api-key-env", str(request.profile.judge["key_source"]),
        ]
        if request.profile.reasoning is not None:
            command.extend(("--pi-thinking-level", str(request.profile.reasoning)))
        if benchmark.mode == "ir":
            command.append("--enable-ir")
        process_environment = _root_environment(request.repo_root)
        process_environment["DCI_EVAL_JUDGE_THINKING"] = (
            "enabled" if request.profile.judge["thinking"] else "disabled"
        )
        process_environment["DCI_EVAL_JUDGE_JSON_MODE"] = (
            "true" if request.profile.judge["json_object"] else "false"
        )
        process_environment["DCI_EVAL_JUDGE_STRICT_JSON_SCHEMA"] = (
            "true"
            if request.profile.judge["output_shape_identity"]
            == "json-schema/strict/v1"
            else "false"
        )
        process_environment["DCI_EVAL_JUDGE_RESPONSES_STORE"] = "false"
        process_environment["DCI_MAX_TURNS"] = str(request.profile.max_turns)
        completed = process_executor(
            command,
            cwd=request.repo_root,
            env=process_environment,
            umask=0o077,
            check=False,
            capture_output=True,
            text=True,
        )
        _store_private_artifacts(
            request.output_root,
            "scope-process",
            {
                "process-evidence.json": json.dumps(
                    {
                        "returncode": completed.returncode,
                        "stdout_sha256": hashlib.sha256(completed.stdout.encode()).hexdigest(),
                        "stderr_sha256": hashlib.sha256(completed.stderr.encode()).hexdigest(),
                    },
                    sort_keys=True,
                ).encode() + b"\n",
            },
        )
        if completed.returncode != 0:
            raise ValueError("AF-340 original full scope execution failed")
    elif request.product == "asterion-dci":
        source = str(request.repo_root / "asterion/src")
        if source not in sys.path:
            sys.path.insert(0, source)
        if request.profile.runtime == "claude-code":
            _claude_full_scope_native_analysis(
                request,
                dataset,
                benchmark,
                process_executor=process_executor,
            )
            if process_executor is subprocess.run:
                _validate_private_tree(request.output_root)
            manifest = normalize_full_scope_manifest(request)
            agent = sum(row.operations.agent for row in manifest.queries)
            judge_count = sum(row.operations.judge for row in manifest.queries)
            return FullScopeResult(agent, judge_count, manifest)
        from dataclasses import replace  # noqa: PLC0415
        from asterion.dci.benchmark import BenchmarkRequest, run_benchmark  # noqa: PLC0415
        from asterion.dci.config import DciRuntimeOptions, resolve_dci_paths  # noqa: PLC0415
        from asterion.dci.judge import JudgeConfig  # noqa: PLC0415

        judge = request.profile.judge
        key_source = str(judge["key_source"])
        environment = _root_environment(request.repo_root)
        paths = replace(
            resolve_dci_paths(request.repo_root, environment=environment),
            output_root=request.output_root,
        )
        selected_runner = run_benchmark if asterion_runner is None else asterion_runner
        result = selected_runner(
            BenchmarkRequest(
                dataset=dataset,
                output_root=request.output_root,
                cwd=request.repo_root / benchmark.corpus_path,
                corpus=request.repo_root / benchmark.corpus_path,
                judge_config=JudgeConfig(
                    base_url=str(judge["base_url"]),
                    api=str(judge["api"]),
                    model=str(judge["model"]),
                    api_key_env=key_source,
                    api_key=environment[key_source],
                    json_mode=bool(judge["json_object"]),
                    strict_json_schema=(
                        judge["output_shape_identity"] == "json-schema/strict/v1"
                    ),
                    responses_store=False,
                    thinking="enabled" if judge["thinking"] else "disabled",
                ),
                runtime_options=DciRuntimeOptions(
                    provider=request.profile.provider,
                    model=request.profile.model,
                    runtime=request.profile.runtime,
                    tools=request.profile.tools,
                    runtime_context_level=request.profile.context_profile,
                    thinking_level=request.profile.reasoning,
                    authentication_mode=request.profile.authentication_mode,
                ),
                mode=benchmark.mode,
                profile=benchmark.batch_profile,
                max_turns=request.profile.max_turns,
                max_concurrency=1,
                resume_policy="fresh",
                full_execution_authorization=request.authorization,
            ),
            paths=paths,
        )
        if result.output_root != request.output_root:
            raise ValueError("AF-340 Asterion full scope output drifted")
    else:
        raise ValueError("AF-340 full product is invalid")
    if (
        (request.product == "original-dci" and process_executor is subprocess.run)
        or (request.product == "asterion-dci" and asterion_runner is None)
    ):
        _validate_private_tree(request.output_root)
    manifest = normalize_full_scope_manifest(request)
    agent = sum(row.operations.agent for row in manifest.queries)
    judge_count = sum(row.operations.judge for row in manifest.queries)
    return FullScopeResult(agent, judge_count, manifest)


def _full_execution_preflight(args: argparse.Namespace, root: Path, profile: object) -> None:
    """Revalidate all scope inputs and secret presence before creating authority roots."""

    environment = _root_environment(root)
    judge_key = str(profile.judge["key_source"])
    if not environment.get(judge_key):
        raise ValueError("AF-340 full Judge credential preflight failed")
    if profile.runtime == "claude-code":
        claude_executable = shutil.which("claude")
        if claude_executable is None:
            raise ValueError("AF-340 full Claude runtime preflight failed")
        if profile.compatible_config_key is None:
            if not _claude_login_ready(claude_executable, environment):
                raise ValueError("AF-340 full Claude authentication preflight failed")
        else:
            competing = (
                "MINIMAX_CN_API_KEY"
                if profile.compatible_config_key == "MINIMAX_API_KEY"
                else "MINIMAX_API_KEY"
            )
            if not environment.get(profile.compatible_config_key) or environment.get(competing):
                raise ValueError("AF-340 full Claude credential preflight failed")
    else:
        from asterion.dci.config import resolve_dci_paths  # noqa: PLC0415

        paths = resolve_dci_paths(root, environment=environment)
        if (
            not paths.pi.package_dir.is_dir()
            or not paths.pi.agent_dir.is_dir()
            or not _pi_auth_ready(paths.pi.agent_dir, str(profile.provider), environment)
        ):
            raise ValueError("AF-340 full Pi authentication preflight failed")
    *_, resolve_benchmark, resolve_scope = _asterion_profile_api(root)
    for scope_id in profile.scope_ids:
        scope = resolve_scope(scope_id)
        benchmark = resolve_benchmark(scope.dataset_id)
        dataset = root / benchmark.dataset_path
        corpus = root / benchmark.corpus_path if benchmark.corpus_path else None
        if dataset.is_symlink() or not dataset.is_file():
            raise ValueError("AF-340 full dataset preflight failed")
        if corpus is not None and (corpus.is_symlink() or not corpus.exists()):
            raise ValueError("AF-340 full corpus preflight failed")
        selected = _scope_selection(root, scope, benchmark)
        if len(selected) != scope.selection_count:
            raise ValueError("AF-340 full selection preflight failed")


def _write_full_execution_report(
    parent_root: Path,
    profile: object,
    plan: Mapping[str, object],
    result: FullRunResult,
    authorizations: Mapping[str, Mapping[str, object]],
) -> Path:
    source = str(Path(__file__).resolve().parents[1] / "asterion/src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from asterion.dci.experiment_profiles import (  # noqa: PLC0415
        consumed_full_execution_authorization_snapshot,
    )
    from asterion.dci.reproduction import (  # noqa: PLC0415
        load_comparison_report,
        load_run_manifest,
    )

    comparison_root = parent_root / "comparisons"
    _validate_private_tree(parent_root)
    _validate_private_tree(comparison_root)
    paths = tuple(sorted(comparison_root.glob("*.json")))
    if len(paths) != len(profile.scope_ids):
        raise ValueError("AF-340 full comparison evidence incomplete [scope-count]")
    comparisons: list[dict[str, object]] = []
    for path in paths:
        report = load_comparison_report(path)
        if report.profile_id != profile.profile_id or report.selection_id not in profile.scope_ids:
            raise ValueError("AF-340 full comparison evidence drifted [profile-or-scope]")
        comparisons.append(
            {
                "selection_id": report.selection_id,
                "ref": path.relative_to(parent_root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "accepted": report.accepted,
            }
        )
    if {item["selection_id"] for item in comparisons} != set(profile.scope_ids):
        raise ValueError("AF-340 full comparison evidence incomplete [selection-set]")
    scope_evidence: list[dict[str, object]] = []
    for product, by_scope in sorted(authorizations.items()):
        for scope_id, authorization in sorted(by_scope.items()):
            output_root = authorization.output_root
            expected_root = (parent_root / product / _safe_slug(scope_id)).resolve()
            if output_root != expected_root:
                raise ValueError("AF-340 full native root drifted [product-or-scope]")
            receipt = consumed_full_execution_authorization_snapshot(authorization)
            receipt_path = output_root / "authorization-receipt.json"
            _write_report(receipt_path, receipt)
            manifest_path = output_root / "af340-run-manifest.json"
            manifest = load_run_manifest(manifest_path)
            if (
                manifest.product != product
                or manifest.selection_id != scope_id
                or manifest.profile_id != profile.profile_id
            ):
                raise ValueError("AF-340 full native manifest drifted [product-or-scope]")
            tree_sha256 = _private_tree_sha256(output_root)
            scope_evidence.append(
                {
                    "product": product,
                    "selection_id": scope_id,
                    "root_ref": output_root.relative_to(parent_root).as_posix(),
                    "tree_sha256": tree_sha256,
                    "authorization_ref": receipt_path.relative_to(parent_root).as_posix(),
                    "authorization_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                    "manifest_ref": manifest_path.relative_to(parent_root).as_posix(),
                    "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                    "manifest_identity_sha256": manifest.identity_sha256,
                }
            )
    values: dict[str, object] = {
        "schema": FULL_REPORT_SCHEMA,
        "mode": "full",
        "status": "passed",
        "profile_id": profile.profile_id,
        "profile_sha256": plan["profile_sha256"],
        "profile_provider": profile.provider,
        "profile_model": profile.model,
        "agent_operations": result.agent_operations,
        "judge_operations": result.judge_operations,
        "agent_maximum": plan["agent_maximum"],
        "judge_maximum": plan["judge_maximum"],
        "comparisons": comparisons,
        "scope_evidence": scope_evidence,
    }
    values["report_sha256"] = _canonical_sha256(values)
    target = parent_root / "af340-full-report.json"
    _write_report(target, values)
    _validate_private_tree(parent_root)
    return target


def _run_full(
    args: argparse.Namespace,
    root: Path,
    executor: Callable[..., object],
    full_runner: FullRunner,
    full_comparator: Callable[[object | None, object, object], object],
    full_preflight: Callable[[argparse.Namespace, Path, object], None],
    stdout: TextIO,
) -> int:
    profile, plan = _full_preflight(args, root)
    _print_full_plan(args, profile, plan, stdout)
    if args.dry_run:
        stdout.write("Full authorization issued: no\nFull dataset ran: no\n")
        return 0
    if not args.authorize_full:
        stdout.write("Full authorization issued: no\nFull dataset ran: no\n")
        return 2
    full_preflight(args, root, profile)
    parent_root = _private_root(args.output_root)
    authorize, *_ = _asterion_profile_api(root)
    products = ("original-dci", "asterion-dci") if profile.runtime == "pi" else ("asterion-dci",)
    authorizations: dict[str, dict[str, object]] = {}
    for product in products:
        product_root = parent_root / product
        if product_root.is_symlink() or product_root.exists():
            raise ValueError("AF-340 full product root must be fresh")
        product_root.mkdir(mode=0o700)
        product_root.chmod(0o700)
        authorizations[product] = {}
        for index, scope_id in enumerate(profile.scope_ids):
            authorization = authorize(
                args.profile,
                parent_root / product / _safe_slug(scope_id),
                args.estimated_budget_usd,
                True,
                preflight_profile_sha256=plan["profile_sha256"],
                preflight_dataset_inventory_sha256=profile.dataset_inventory_sha256,
                preflight_experiment_scopes_sha256=profile.experiment_scopes_sha256,
                preflight_scope_ids=(scope_id,),
                preflight_selected_ids_sha256=(profile.selected_ids_sha256[index],),
                invocation_provider=args.provider,
                invocation_model=args.model,
            )
            authorizations[product][scope_id] = authorization
    stdout.write("Full authorization issued: yes\n")
    scope_executor = (
        production_full_scope_executor if executor is subprocess.run else executor
    )
    result = full_runner(authorizations, profile, root, scope_executor, full_comparator)
    if (
        isinstance(result.agent_operations, bool)
        or isinstance(result.judge_operations, bool)
        or result.agent_operations < 0
        or result.judge_operations < 0
        or result.agent_operations > plan["agent_maximum"]
        or result.judge_operations > plan["judge_maximum"]
        or result.full_dataset_ran is not True
    ):
        raise ValueError("AF-340 full execution result invalid [count-or-full-state]")
    if executor is subprocess.run and full_runner is _default_full_runner and (
        result.agent_operations != plan["agent_maximum"]
        or result.judge_operations != plan["judge_maximum"]
    ):
        raise ValueError("AF-340 full execution incomplete [actual-vs-maximum-counts]")
    if (
        full_runner is _default_full_runner
        and executor is subprocess.run
        and full_comparator is _default_full_comparator
    ):
        report_path = _write_full_execution_report(
            parent_root, profile, plan, result, authorizations
        )
        # The same coordinator invocation still holds the consumed Task 6
        # capabilities here.  Do not publish retained evidence until the exact
        # persistent inspection path also accepts the completed native trees.
        _run_inspect_full(
            argparse.Namespace(report=report_path), root, StringIO()
        )
        stdout.write(
            "Full evidence report SHA-256: "
            + hashlib.sha256(report_path.read_bytes()).hexdigest()
            + "\n"
        )
    stdout.write(f"Agent operations: {result.agent_operations}\n")
    stdout.write(f"Judge operations: {result.judge_operations}\n")
    stdout.write("Full dataset ran: " + ("yes\n" if result.full_dataset_ran else "no\n"))
    return 0


def _validate_report(path: Path, root: Path) -> tuple[str, set[str]]:
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("AF-340 retained report permissions are invalid")
    if stat.S_IMODE(path.parent.stat().st_mode) != 0o700:
        raise ValueError("AF-340 retained report root permissions are invalid")
    _validate_private_tree(path.parent / "private")
    report = json.loads(path.read_text(encoding="utf-8"))
    required = {
        "schema",
        "mode",
        "status",
        "evidence_dimensions",
        "agent_operations",
        "judge_operations",
        "attempted_operations",
        "full_dataset_ran",
        "operations",
        "variant",
        "plan_sha256",
        "report_sha256",
    }
    if not isinstance(report, dict) or set(report) != required:
        raise ValueError("AF-340 retained report is invalid")
    if (
        report["schema"] != REPORT_SCHEMA
        or report["mode"] != "bounded"
        or report["status"] != "passed"
        or report["full_dataset_ran"] is not False
        or not isinstance(report["operations"], list)
    ):
        raise ValueError("AF-340 retained report is invalid")
    variant = report["variant"]
    if variant not in {"pi", "claude-subscription", "claude-minimax"}:
        raise ValueError("AF-340 retained report variant is invalid")
    expected_plan = bounded_operation_plan(
        root,
        variant,
        "minimax" if variant == "claude-minimax" else None,
        "retained-model" if variant == "claude-minimax" else None,
    )
    if report["plan_sha256"] != _plan_sha256(expected_plan):
        raise ValueError("AF-340 retained operation plan drifted")
    unsigned = dict(report)
    signature = unsigned.pop("report_sha256")
    if signature != _canonical_sha256(unsigned):
        raise ValueError("AF-340 retained report signature is invalid")
    forbidden_keys = {"command", "argv", "stdout", "stderr", "prompt", "answer", "body", "credential", "api_key"}
    if forbidden_keys.intersection(str(key).lower() for key in report if key != "operations"):
        raise ValueError("AF-340 retained report leaks private fields")
    counted_agent = 0
    counted_judge = 0
    if len(report["operations"]) != len(expected_plan):
        raise ValueError("AF-340 retained report operation set is invalid")
    for operation, expected in zip(report["operations"], expected_plan, strict=True):
        if not isinstance(operation, dict) or set(operation) != {
            "operation_id",
            "kind",
            "status",
            "command_sha256",
            "agent_operations",
            "judge_operations",
            "artifacts",
        }:
            raise ValueError("AF-340 retained report operation is invalid")
        if (
            operation["operation_id"] != expected.operation_id
            or operation["kind"] != expected.kind
            or operation["status"] != "completed"
            or _SHA256.fullmatch(operation["command_sha256"]) is None
        ):
            raise ValueError("AF-340 retained report operation is invalid")
        if forbidden_keys.intersection(str(key).lower() for key in operation):
            raise ValueError("AF-340 retained report leaks private fields")
        artifacts = operation["artifacts"]
        if not isinstance(artifacts, dict) or "effective-config.json" not in artifacts:
            raise ValueError("AF-340 retained artifacts are incomplete")
        effective_config_path: Path | None = None
        for artifact_name, artifact in artifacts.items():
            if not isinstance(artifact, dict) or set(artifact) != {"ref", "sha256"}:
                raise ValueError("AF-340 retained artifact identity is invalid")
            candidate = (path.parent / artifact["ref"]).resolve()
            try:
                candidate.relative_to(path.parent.resolve())
            except ValueError:
                raise ValueError("AF-340 retained artifact escaped its root") from None
            if (
                candidate.is_symlink()
                or not candidate.is_file()
                or stat.S_IMODE(candidate.stat().st_mode) != 0o600
                or hashlib.sha256(candidate.read_bytes()).hexdigest() != artifact["sha256"]
            ):
                raise ValueError("AF-340 retained artifact digest is invalid")
            if artifact_name == "effective-config.json":
                effective_config_path = candidate
        assert effective_config_path is not None
        try:
            config = json.loads(effective_config_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError):
            raise ValueError("AF-340 retained effective configuration is invalid") from None
        config_keys = {
            "schema", "operation_id", "kind", "variant", "runtime", "provider",
            "model", "command_template_sha256", "rendered_command_sha256",
            "native_artifacts", "actual_counts", "process",
        }
        expected_agent = int(expected.kind in {"agent", "agent-and-judge"})
        expected_judge = int(expected.kind in {"judge", "agent-and-judge"})
        if (
            not isinstance(config, dict)
            or set(config) != config_keys
            or config["schema"] != "dci.af340-effective-config/v1"
            or config["operation_id"] != expected.operation_id
            or config["kind"] != expected.kind
            or config["variant"] != variant
            or config["runtime"] != _bounded_runtime_identity(
                variant, config.get("provider") if isinstance(config.get("provider"), str) else None
            )
            or config["command_template_sha256"] != _command_sha256(expected.command)
            or operation["command_sha256"] != _command_sha256(expected.command)
            or _SHA256.fullmatch(str(config["rendered_command_sha256"])) is None
            or config["actual_counts"] != {
                "agent": expected_agent, "judge": expected_judge
            }
            or operation["agent_operations"] != expected_agent
            or operation["judge_operations"] != expected_judge
        ):
            raise ValueError("AF-340 retained effective configuration drifted")
        if variant in {"pi", "claude-subscription"} and (
            config["provider"] is not None or config["model"] is not None
        ):
            raise ValueError("AF-340 retained provider identity drifted")
        if variant == "claude-minimax" and (
            config["provider"] not in {"minimax", "minimax-cn"}
            or not isinstance(config["model"], str)
            or not config["model"]
        ):
            raise ValueError("AF-340 retained provider identity drifted")
        native_artifacts = config["native_artifacts"]
        if not isinstance(native_artifacts, list) or not native_artifacts:
            raise ValueError("AF-340 retained native artifact identity drifted")
        native_by_root: dict[str, dict[str, object]] = {}
        for item in native_artifacts:
            if (
                not isinstance(item, dict)
                or set(item) != {"artifact", "kind", "root_ref", "sha256"}
                or not isinstance(item["artifact"], str)
                or not isinstance(item["kind"], str)
                or not isinstance(item["root_ref"], str)
                or _SHA256.fullmatch(str(item["sha256"])) is None
                or item["artifact"] not in artifacts
                or item["artifact"] == "effective-config.json"
            ):
                raise ValueError("AF-340 retained native artifact identity drifted")
            root_ref = Path(item["root_ref"])
            if root_ref.is_absolute() or ".." in root_ref.parts:
                raise ValueError("AF-340 retained native root identity drifted")
            native_path = (path.parent / artifacts[item["artifact"]]["ref"]).resolve()
            if hashlib.sha256(native_path.read_bytes()).hexdigest() != item["sha256"]:
                raise ValueError("AF-340 retained native artifact digest drifted")
            root_facts = native_by_root.setdefault(
                item["root_ref"], {"pi_request": False, "pi_completed": False,
                                   "claude_request": False, "claude_completed": False,
                                   "judge": False},
            )
            document = _read_native_json(native_path) if native_path.suffix == ".json" else None
            if re.fullmatch(r"attempt-[0-9]{4}\.request\.json", item["kind"]):
                root_facts["pi_request"] = isinstance(document, dict)
            elif item["kind"] == "state.json":
                root_facts["pi_completed"] = (
                    isinstance(document, dict) and document.get("status") == "completed"
                )
            elif item["kind"] == "request.json":
                root_facts["claude_request"] = (
                    isinstance(document, dict) and isinstance(document.get("run_id"), str)
                )
            elif item["kind"] == "events.jsonl":
                root_facts["claude_completed"] = _completed_claude_events(native_path)
            elif item["kind"] == "eval_result.json":
                root_facts["judge"] = (
                    isinstance(document, dict)
                    and isinstance(document.get("is_correct"), bool)
                )
        measured_agent = sum(
            bool(facts["pi_request"] and facts["pi_completed"])
            or bool(facts["claude_request"] and facts["claude_completed"])
            for facts in native_by_root.values()
        )
        measured_judge = sum(bool(facts["judge"]) for facts in native_by_root.values())
        has_pi = any(
            facts["pi_request"] or facts["pi_completed"]
            for facts in native_by_root.values()
        )
        has_claude = any(
            facts["claude_request"] or facts["claude_completed"]
            for facts in native_by_root.values()
        )
        if (
            (measured_agent, measured_judge) != (expected_agent, expected_judge)
            or (variant == "pi" and (not has_pi or has_claude))
            or (variant != "pi" and (not has_claude or has_pi))
        ):
            raise ValueError("AF-340 retained native operation counts drifted")
        process = config["process"]
        if (
            not isinstance(process, dict)
            or process.get("status") != "completed"
            or set(process) - {
                "status", "returncode", "stdout_sha256", "stderr_sha256"
            }
            or any(
                _SHA256.fullmatch(str(process[name])) is None
                for name in ("stdout_sha256", "stderr_sha256")
                if name in process
            )
        ):
            raise ValueError("AF-340 retained process identity drifted")
        counted_agent += operation["agent_operations"]
        counted_judge += operation["judge_operations"]
    if (
        report["attempted_operations"] != len(report["operations"])
        or report["agent_operations"] != counted_agent
        or report["judge_operations"] != counted_judge
    ):
        raise ValueError("AF-340 retained report counts are invalid")
    expected_dimensions = _dimensions_for_variant(variant)
    dimensions = report["evidence_dimensions"]
    if dimensions != expected_dimensions:
        raise ValueError("AF-340 retained report dimensions are invalid")
    return variant, set(expected_dimensions)


def _run_inspect(args: argparse.Namespace, root: Path, stdout: TextIO) -> int:
    if len(args.report) != 3:
        raise ValueError("AF-340 retained evidence requires exactly three reports")
    dimensions: set[str] = set()
    variants: set[str] = set()
    for report in args.report:
        variant, retained = _validate_report(report, root)
        if variant in variants:
            raise ValueError("AF-340 retained evidence variant is duplicated")
        variants.add(variant)
        overlap = dimensions.intersection(retained)
        if overlap:
            raise ValueError("AF-340 retained evidence dimension is duplicated")
        dimensions.update(retained)
    if dimensions != RETAINED_DIMENSIONS:
        raise ValueError("AF-340 retained evidence is incomplete")
    stdout.write(
        "PASS\nRetained evidence dimensions: 4/4\n"
        + "".join(f"Retained dimension: {item}\n" for item in sorted(dimensions))
        + "Agent operations: 0\nJudge operations: 0\nFull dataset ran: no\n"
    )
    return 0


def _run_inspect_full(args: argparse.Namespace, root: Path, stdout: TextIO) -> int:
    path = args.report
    if (
        path.is_symlink()
        or not path.is_file()
        or stat.S_IMODE(path.stat().st_mode) != 0o600
        or stat.S_IMODE(path.parent.stat().st_mode) != 0o700
    ):
        raise ValueError("AF-340 full report invalid [permissions]")
    _validate_private_tree(path.parent)
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError):
        raise ValueError("AF-340 full report invalid [json]") from None
    keys = {
        "schema", "mode", "status", "profile_id", "profile_sha256",
        "profile_provider", "profile_model", "agent_operations", "judge_operations",
        "agent_maximum", "judge_maximum", "comparisons", "scope_evidence",
        "report_sha256",
    }
    if not isinstance(report, dict) or set(report) != keys:
        raise ValueError("AF-340 full report invalid [schema]")
    unsigned = dict(report)
    signature = unsigned.pop("report_sha256")
    if (
        report["schema"] != FULL_REPORT_SCHEMA
        or report["mode"] != "full"
        or report["status"] != "passed"
        or signature != _canonical_sha256(unsigned)
    ):
        raise ValueError("AF-340 full report invalid [identity-or-state]")
    args_for_profile = argparse.Namespace(
        profile=report["profile_id"],
        provider=report["profile_provider"],
        model=report["profile_model"],
        estimated_budget_usd=0.0,
        output_root=path.parent / f".inspect-{signature}",
    )
    profile, plan = _full_preflight(args_for_profile, root)
    if (
        report["profile_sha256"] != plan["profile_sha256"]
        or report["agent_maximum"] != plan["agent_maximum"]
        or report["judge_maximum"] != plan["judge_maximum"]
        or report["agent_operations"] > report["agent_maximum"]
        or report["judge_operations"] > report["judge_maximum"]
    ):
        raise ValueError("AF-340 full report invalid [profile-or-counts]")
    comparisons = report["comparisons"]
    if not isinstance(comparisons, list) or len(comparisons) != len(profile.scope_ids):
        raise ValueError("AF-340 full report invalid [comparison-count]")
    _validate_private_tree(path.parent / "comparisons")
    source = str(root / "asterion/src")
    if source not in sys.path:
        sys.path.insert(0, source)
    from asterion.dci.paper_benchmarks import (  # noqa: PLC0415
        resolve_paper_benchmark,
        resolve_paper_experiment_scope,
    )
    from asterion.dci.reproduction import (  # noqa: PLC0415
        load_comparison_report,
        load_run_manifest,
    )

    expected_products = (
        ("original-dci", "asterion-dci")
        if profile.runtime == "pi"
        else ("asterion-dci",)
    )
    evidence = report["scope_evidence"]
    if not isinstance(evidence, list) or len(evidence) != (
        len(expected_products) * len(profile.scope_ids)
    ):
        raise ValueError("AF-340 full report invalid [native-count]")
    manifests: dict[tuple[str, str], object] = {}
    selected_by_scope = dict(
        zip(profile.scope_ids, profile.selected_ids_sha256, strict=True)
    )
    receipt_keys = {
        "schema", "profile_id", "profile_sha256", "dataset_inventory_sha256",
        "experiment_scopes_sha256", "authorized_scope_ids", "selected_ids_sha256",
        "output_root_device", "output_root_inode", "estimated_budget_usd",
        "invocation_authorized", "issuance_token_sha256",
    }
    for item in evidence:
        item_keys = {
            "product", "selection_id", "root_ref", "tree_sha256",
            "authorization_ref", "authorization_sha256", "manifest_ref",
            "manifest_sha256", "manifest_identity_sha256",
        }
        if not isinstance(item, dict) or set(item) != item_keys:
            raise ValueError("AF-340 full report invalid [native-ref]")
        product = item["product"]
        scope_id = item["selection_id"]
        identity = (product, scope_id)
        if (
            product not in expected_products
            or scope_id not in profile.scope_ids
            or identity in manifests
            or item["root_ref"] != f"{product}/{_safe_slug(scope_id)}"
        ):
            raise ValueError("AF-340 full report invalid [native-identity]")
        native_root = (path.parent / item["root_ref"]).resolve()
        try:
            native_root.relative_to(path.parent.resolve())
        except ValueError:
            raise ValueError("AF-340 full report invalid [native-escape]") from None
        if _private_tree_sha256(native_root) != item["tree_sha256"]:
            raise ValueError("AF-340 full report invalid [native-tree]")
        receipt_path = (path.parent / item["authorization_ref"]).resolve()
        manifest_path = (path.parent / item["manifest_ref"]).resolve()
        if receipt_path.parent != native_root or manifest_path.parent != native_root:
            raise ValueError("AF-340 full report invalid [native-binding]")
        if (
            hashlib.sha256(receipt_path.read_bytes()).hexdigest()
            != item["authorization_sha256"]
            or hashlib.sha256(manifest_path.read_bytes()).hexdigest()
            != item["manifest_sha256"]
        ):
            raise ValueError("AF-340 full report invalid [native-digest]")
        receipt = _read_native_json(receipt_path)
        metadata = native_root.stat()
        if (
            not isinstance(receipt, dict)
            or set(receipt) != receipt_keys
            or receipt["schema"] != "dci.full-execution-authorization-receipt/v1"
            or receipt["profile_id"] != profile.profile_id
            or receipt["profile_sha256"] != report["profile_sha256"]
            or receipt["dataset_inventory_sha256"] != profile.dataset_inventory_sha256
            or receipt["experiment_scopes_sha256"] != profile.experiment_scopes_sha256
            or receipt["authorized_scope_ids"] != [scope_id]
            or receipt["selected_ids_sha256"] != [selected_by_scope[scope_id]]
            or receipt["output_root_device"] != metadata.st_dev
            or receipt["output_root_inode"] != metadata.st_ino
            or receipt["invocation_authorized"] is not True
            or _SHA256.fullmatch(str(receipt["issuance_token_sha256"])) is None
        ):
            raise ValueError("AF-340 full report invalid [authorization-receipt]")
        manifest = load_run_manifest(manifest_path)
        normalized = normalize_full_scope_manifest(
            FullScopeRequest(
                product, scope_id, None, native_root, profile, root
            ),
            write=False,
        )
        if (
            manifest.product != product
            or manifest.selection_id != scope_id
            or manifest.profile_id != profile.profile_id
            or manifest.profile_sha256 != report["profile_sha256"]
            or manifest.identity_sha256 != item["manifest_identity_sha256"]
            or normalized.identity_sha256 != manifest.identity_sha256
        ):
            raise ValueError("AF-340 full report invalid [native-manifest]")
        manifests[identity] = manifest

    seen: set[str] = set()
    counted_agent = sum(
        manifest.aggregates.agent_operations for manifest in manifests.values()
    )
    counted_judge = sum(
        manifest.aggregates.judge_operations for manifest in manifests.values()
    )
    for item in comparisons:
        if not isinstance(item, dict) or set(item) != {
            "selection_id", "ref", "sha256", "accepted"
        }:
            raise ValueError("AF-340 full report invalid [comparison-ref]")
        candidate = (path.parent / item["ref"]).resolve()
        try:
            candidate.relative_to(path.parent.resolve())
        except ValueError:
            raise ValueError("AF-340 full report invalid [comparison-escape]") from None
        comparison = load_comparison_report(candidate)
        scope = resolve_paper_experiment_scope(item["selection_id"])
        benchmark = resolve_paper_benchmark(scope.dataset_id)
        expected_judge = scope.selection_count if benchmark.mode == "qa" else 0
        if (
            item["selection_id"] in seen
            or item["selection_id"] not in profile.scope_ids
            or item["selection_id"] != comparison.selection_id
            or item["accepted"] != comparison.accepted
            or item["accepted"] is False
            or hashlib.sha256(candidate.read_bytes()).hexdigest() != item["sha256"]
            or comparison.profile_sha256 != report["profile_sha256"]
            or comparison.candidate_run_sha256
            != manifests[("asterion-dci", item["selection_id"])].identity_sha256
            or comparison.candidate.agent_operations != scope.selection_count
            or comparison.candidate.judge_operations != expected_judge
        ):
            raise ValueError("AF-340 full report invalid [comparison-evidence]")
        if "original-dci" in expected_products:
            if (
                comparison.baseline is None
                or comparison.baseline_run_sha256 is None
                or
                comparison.baseline_run_sha256
                != manifests[("original-dci", item["selection_id"])].identity_sha256
                or
                comparison.baseline.agent_operations != scope.selection_count
                or comparison.baseline.judge_operations != expected_judge
            ):
                raise ValueError("AF-340 full report invalid [baseline-counts]")
        elif comparison.baseline is not None or comparison.baseline_run_sha256 is not None:
            raise ValueError("AF-340 full report invalid [baseline-counts]")
        seen.add(item["selection_id"])
    if (
        seen != set(profile.scope_ids)
        or counted_agent != report["agent_operations"]
        or counted_judge != report["judge_operations"]
    ):
        raise ValueError("AF-340 full report invalid [aggregate-counts]")
    stdout.write(
        "PASS\nAuthorized full comparison evidence: yes\n"
        f"Full comparison scopes: {len(comparisons)}/{len(profile.scope_ids)}\n"
        f"Agent operations: {report['agent_operations']}\n"
        f"Judge operations: {report['judge_operations']}\nFull dataset ran: yes\n"
    )
    return 0


def _safe_reason_class(error: BaseException) -> str:
    message = str(error).lower()
    for reason, markers in (
        ("comparison", ("comparison", "not-accepted")),
        ("authorization", ("authorization", "authority")),
        ("preflight", ("preflight", "credential", "runtime unavailable")),
        ("configuration", ("configuration", "profile", "provider identity")),
        ("counts", ("count", "operations", "full-state")),
        ("evidence", ("evidence", "artifact", "report", "summary")),
        ("execution", ("execution", "operation failed", "timed_out", "cancelled")),
    ):
        if any(marker in message for marker in markers):
            return reason
    if isinstance(error, (json.JSONDecodeError, UnicodeError)):
        return "evidence"
    if isinstance(error, OSError):
        return "io"
    return "invalid-input"


def verify_af340_reproduction_main(
    argv: Sequence[str] | None = None,
    *,
    repo_root: Path | None = None,
    executor: Callable[..., object] = subprocess.run,
    bounded_preflight: Callable[..., BoundedPreflight] = _default_bounded_preflight,
    full_runner: FullRunner = _default_full_runner,
    full_comparator: Callable[[object | None, object, object], object] = _default_full_comparator,
    full_preflight: Callable[[argparse.Namespace, Path, object], None] = _full_execution_preflight,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    raise_errors: bool = False,
) -> int:
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    root = Path(__file__).resolve().parents[1] if repo_root is None else Path(repo_root).resolve()
    try:
        args = _parser().parse_args(argv)
        if args.mode == "local":
            return _run_local(root, executor, stdout)
        if args.mode == "bounded":
            return _run_bounded(args, root, executor, bounded_preflight, stdout)
        if args.mode == "full":
            return _run_full(
                args, root, executor, full_runner, full_comparator, full_preflight, stdout
            )
        if args.mode == "inspect-full":
            return _run_inspect_full(args, root, stdout)
        return _run_inspect(args, root, stdout)
    except (OSError, RuntimeError, TypeError, ValueError, json.JSONDecodeError) as error:
        if raise_errors:
            raise
        stderr.write(
            "AF-340 reproduction verification failed "
            f"[reason_class={_safe_reason_class(error)}]\n"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(verify_af340_reproduction_main())
