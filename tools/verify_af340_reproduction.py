#!/usr/bin/env python3
"""Coordinate AF-340 local, bounded, and authorized full reproduction gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence, TextIO


@dataclass(frozen=True, slots=True)
class CommandSpec:
    check_id: str
    argv: tuple[str, ...]


LOCAL_MATRIX = (
    CommandSpec("scope-preflight", ("python3", "tools/project_scope_check.py")),
    CommandSpec(
        "original-readme",
        ("uv", "run", "python", "tools/verify_original_readme.py", "--level", "local"),
    ),
    CommandSpec(
        "configuration-profiles",
        (
            "uv",
            "run",
            "python",
            "-m",
            "unittest",
            "-v",
            "tests.test_config",
            "tests.test_effective_config",
            "tests.test_asterion_dci_config",
            "tests.test_asterion_dci_experiment_profiles",
        ),
    ),
    CommandSpec(
        "launchers-context",
        (
            "uv",
            "run",
            "python",
            "-m",
            "unittest",
            "-v",
            "tests.test_original_readme_acceptance",
            "tests.test_asterion_dci_batch_launchers",
            "tests.test_asterion_dci_context_profiles",
        ),
    ),
    CommandSpec(
        "artifacts-comparison",
        (
            "uv",
            "run",
            "python",
            "-m",
            "unittest",
            "-v",
            "tests.test_asterion_dci_artifacts",
            "tests.test_asterion_dci_reproduction",
            "tests.test_asterion_dci_paper_resolution_analysis",
        ),
    ),
    CommandSpec(
        "product-source-wheel",
        (
            "uv",
            "run",
            "python",
            "-m",
            "unittest",
            "-v",
            "tests.test_asterion_dci_paper_product",
            "tests.test_asterion_dci_product_parity",
            "tests.test_distribution_boundaries",
        ),
    ),
)

Executor = Callable[..., subprocess.CompletedProcess[str]]


def _default_executor(
    argv: tuple[str, ...], *, cwd: Path
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=False,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()


def _prepare_private_root(path: Path) -> Path:
    output = Path(os.path.abspath(os.path.normpath(path)))
    parent = output.parent
    try:
        metadata = parent.lstat()
    except OSError as error:
        raise ValueError("AF-340 output parent is invalid") from error
    if parent.is_symlink() or not stat.S_ISDIR(metadata.st_mode) or output.exists():
        raise ValueError("AF-340 output root must be fresh below a real directory")
    output.mkdir(mode=0o700)
    output.chmod(0o700)
    return output


def _write_private_evidence(output_root: Path, evidence: dict[str, object]) -> Path:
    path = output_root / "local-evidence.json"
    raw = _canonical_bytes(evidence)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
    return path


@dataclass(frozen=True, slots=True)
class LocalVerificationResult:
    passed: bool
    checks: tuple[tuple[str, str], ...]
    evidence_path: Path
    evidence_sha256: str

    def public_report(self) -> dict[str, object]:
        return {
            "schema": "dci.af340-reproduction-public/v1",
            "mode": "local",
            "status": "passed" if self.passed else "failed",
            "checks": [
                {"check_id": check_id, "status": status}
                for check_id, status in self.checks
            ],
            "agent_operations": 0,
            "judge_operations": 0,
            "full_dataset_ran": False,
            "evidence_sha256": self.evidence_sha256,
        }


def verify_local(
    *,
    repo_root: Path,
    output_root: Path,
    executor: Executor = _default_executor,
) -> LocalVerificationResult:
    """Execute the fixed provider-free matrix and retain only body-free evidence."""

    root = Path(os.path.abspath(os.path.normpath(repo_root)))
    try:
        root_metadata = root.lstat()
    except OSError as error:
        raise ValueError("AF-340 repository root is invalid") from error
    if root.is_symlink() or not stat.S_ISDIR(root_metadata.st_mode):
        raise ValueError("AF-340 repository root is invalid")
    private_root = _prepare_private_root(output_root)
    records: list[dict[str, object]] = []
    checks: list[tuple[str, str]] = []
    for spec in LOCAL_MATRIX:
        completed = executor(spec.argv, cwd=root)
        status = "passed" if completed.returncode == 0 else "failed"
        checks.append((spec.check_id, status))
        records.append(
            {
                "check_id": spec.check_id,
                "argv": list(spec.argv),
                "returncode": completed.returncode,
                "stdout_sha256": _sha256_text(completed.stdout or ""),
                "stdout_bytes": len((completed.stdout or "").encode()),
                "stderr_sha256": _sha256_text(completed.stderr or ""),
                "stderr_bytes": len((completed.stderr or "").encode()),
            }
        )
        if completed.returncode != 0:
            break
    passed = len(records) == len(LOCAL_MATRIX) and all(
        status == "passed" for _check_id, status in checks
    )
    evidence = {
        "schema": "dci.af340-reproduction-private/v1",
        "mode": "local",
        "status": "passed" if passed else "failed",
        "checks": records,
        "agent_operations": 0,
        "judge_operations": 0,
        "full_dataset_ran": False,
    }
    evidence_path = _write_private_evidence(private_root, evidence)
    evidence_sha256 = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
    return LocalVerificationResult(
        passed=passed,
        checks=tuple(checks),
        evidence_path=evidence_path,
        evidence_sha256=evidence_sha256,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="mode", required=True)
    local = commands.add_parser("local")
    local.add_argument("--repo-root", type=Path, default=Path.cwd())
    local.add_argument("--output-root", type=Path, required=True)
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    executor: Executor = _default_executor,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    try:
        args = _parser().parse_args(argv)
        result = verify_local(
            repo_root=args.repo_root,
            output_root=args.output_root,
            executor=executor,
        )
    except (OSError, TypeError, ValueError):
        stderr.write("AF-340 reproduction verification failed\n")
        return 2
    stdout.write(json.dumps(result.public_report(), sort_keys=True) + "\n")
    stdout.write("PASS\n" if result.passed else "FAIL\n")
    stdout.write("Agent operations: 0\n")
    stdout.write("Judge operations: 0\n")
    stdout.write("Full dataset ran: no\n")
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
