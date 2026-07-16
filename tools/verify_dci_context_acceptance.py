#!/usr/bin/env python3
"""Verify model-free and bounded provider-backed DCI context policies."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from asterion.dci.config import (
    DciPaths,
    DciRuntimeOptions,
    load_asterion_dci_env,
    resolve_dci_paths,
    resolve_dci_runtime_options,
)
from asterion.dci.context_extension import resolve_context_extension
from asterion.dci.context_profiles import (
    context_policy_identity,
    resolve_context_profile,
)
from asterion.dci.provenance import collect_pi_provenance
from asterion.dci.run import DciRunRequest, run_pi_research


REPORT_SCHEMA = "asterion.dci.context-acceptance/v1"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40,64}")
_PUBLIC_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/+-]*")
_ARTIFACT_NAMES = {"context-policy.json", "events.jsonl", "state.json"}
_PRESSURE_LINE_CHARACTERS = 25_000
_PRESSURE_LINES = 13


@dataclass(frozen=True)
class ContextAcceptanceReadiness:
    """Safe provider readiness facts plus the private output authority."""

    output_root: Path
    provider: str
    model: str
    pi_revision: str
    extension_version: str
    extension_sha256: str
    paths: DciPaths | None = None
    runtime_options: DciRuntimeOptions | None = None
    corpus_dir: Path | None = None
    corpus_sha256: str = "0" * 64


@dataclass(frozen=True)
class ContextAcceptanceCase:
    """Body-free semantic evidence from one bounded Pi process."""

    profile: str
    compactions: int
    summary_attempts: int
    summary_successes: int
    summary_suppressed: bool
    retained_turns: int
    artifact_digests: tuple[tuple[str, str], ...]

    def validate(self) -> None:
        if self.profile not in {"level3", "level4"}:
            raise ValueError("DCI context acceptance case is invalid")
        for value in (
            self.compactions,
            self.summary_attempts,
            self.summary_successes,
            self.retained_turns,
        ):
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("DCI context acceptance case is invalid")
        if type(self.summary_suppressed) is not bool or self.retained_turns != 12:
            raise ValueError("DCI context acceptance case is invalid")
        if self.compactions < 1:
            raise ValueError("DCI context acceptance case is invalid")
        if self.profile == "level3" and (
            self.summary_attempts != 0 or self.summary_successes != 0
        ):
            raise ValueError("DCI context acceptance case is invalid")
        if self.profile == "level4" and (
            self.summary_attempts < 1
            or self.summary_successes < 1
            or self.summary_suppressed
        ):
            raise ValueError("DCI context acceptance case is invalid")
        names = [name for name, _digest in self.artifact_digests]
        if (
            not self.artifact_digests
            or len(names) != len(set(names))
            or any(name not in _ARTIFACT_NAMES for name in names)
            or any(_SHA256.fullmatch(digest) is None for _name, digest in self.artifact_digests)
        ):
            raise ValueError("DCI context acceptance case is invalid")


ReadinessChecker = Callable[[argparse.Namespace, Path], ContextAcceptanceReadiness]
ProviderRunner = Callable[
    [ContextAcceptanceReadiness, str], ContextAcceptanceCase | None
]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verify_dci_context_acceptance.py",
        exit_on_error=False,
    )
    parser.add_argument("--provider-backed", action="store_true")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output-root", type=Path)
    return parser


def _model_free_contract() -> None:
    with resolve_context_extension() as extension:
        for name in ("level0", "level1", "level2", "level3", "level4"):
            profile = resolve_context_profile(name)
            if profile is None:
                raise ValueError("DCI context acceptance contract is invalid")
            context_policy_identity(profile, extension)


def _provider_key_name(provider: str) -> str | None:
    normalized = provider.lower()
    if normalized.startswith("openai"):
        return "OPENAI_API_KEY"
    if normalized.startswith("anthropic"):
        return "ANTHROPIC_API_KEY"
    if normalized.startswith("google") or normalized.startswith("gemini"):
        return "GEMINI_API_KEY"
    if normalized.startswith("deepseek"):
        return "DEEPSEEK_API_KEY"
    return None


def _regular_private_input(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return (
        not path.is_symlink()
        and stat.S_ISREG(metadata.st_mode)
        and not metadata.st_mode & stat.S_IWOTH
    )


def _reject_symlink_components(path: Path) -> None:
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError("DCI context acceptance output is invalid")


def _prepare_output_root(path: Path) -> Path:
    output_root = Path(os.path.abspath(os.path.normpath(path)))
    _reject_symlink_components(output_root)
    if output_root.exists():
        if not output_root.is_dir() or any(output_root.iterdir()):
            raise ValueError("DCI context acceptance output is invalid")
    else:
        output_root.mkdir(parents=True, mode=0o700)
    output_root.chmod(0o700)
    return output_root


def _write_pressure_fixture(output_root: Path) -> tuple[Path, str]:
    corpus_dir = output_root / "corpus-fixture"
    corpus_dir.mkdir(mode=0o700)
    payload = "".join(
        f"{index:02d}:" + (chr(65 + index % 26) * (_PRESSURE_LINE_CHARACTERS - 4)) + "\n"
        for index in range(_PRESSURE_LINES)
    ).encode()
    path = corpus_dir / "pressure.txt"
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
    return corpus_dir, hashlib.sha256(payload).hexdigest()


def _default_readiness(
    args: argparse.Namespace, repo_root: Path
) -> ContextAcceptanceReadiness:
    if args.env_file is None or args.output_root is None:
        raise ValueError("DCI context acceptance preflight failed")
    env_file = Path(args.env_file).expanduser().resolve()
    if not _regular_private_input(env_file):
        raise ValueError("DCI context acceptance preflight failed")
    if load_asterion_dci_env(repo_root, env_file=env_file) is None:
        raise ValueError("DCI context acceptance preflight failed")
    paths = resolve_dci_paths(repo_root)
    options = resolve_dci_runtime_options()
    if (
        not isinstance(options.provider, str)
        or _PUBLIC_NAME.fullmatch(options.provider) is None
        or not isinstance(options.model, str)
        or _PUBLIC_NAME.fullmatch(options.model) is None
    ):
        raise ValueError("DCI context acceptance preflight failed")
    credential_name = _provider_key_name(options.provider)
    pi_auth = paths.pi.agent_dir / "auth.json"
    if not (
        credential_name
        and os.environ.get(credential_name, "").strip()
        or _regular_private_input(pi_auth)
    ):
        raise ValueError("DCI context acceptance preflight failed")
    if not (paths.pi.package_dir / "package.json").is_file():
        raise ValueError("DCI context acceptance preflight failed")
    provenance = collect_pi_provenance(
        paths.pi.package_dir,
        repo_root / "pi-revision.txt",
        os.environ.get("DCI_PI_REVISION"),
    )
    revision = provenance.get("commit")
    if not isinstance(revision, str) or _REVISION.fullmatch(revision) is None:
        raise ValueError("DCI context acceptance preflight failed")
    with resolve_context_extension() as extension:
        extension_version = extension.version
        extension_sha256 = extension.sha256
    output_root = _prepare_output_root(args.output_root)
    corpus_dir, corpus_sha256 = _write_pressure_fixture(output_root)
    return ContextAcceptanceReadiness(
        output_root=output_root,
        provider=options.provider,
        model=options.model,
        pi_revision=revision,
        extension_version=extension_version,
        extension_sha256=extension_sha256,
        paths=paths,
        runtime_options=options,
        corpus_dir=corpus_dir,
        corpus_sha256=corpus_sha256,
    )


def _artifact_digests(output_dir: Path) -> tuple[tuple[str, str], ...]:
    values = []
    for name in sorted(_ARTIFACT_NAMES):
        path = output_dir / name
        if not _regular_private_input(path):
            raise ValueError("DCI context acceptance evidence is invalid")
        values.append((name, hashlib.sha256(path.read_bytes()).hexdigest()))
    return tuple(values)


def _default_provider_runner(
    readiness: ContextAcceptanceReadiness, profile_name: str
) -> ContextAcceptanceCase:
    if (
        readiness.paths is None
        or readiness.runtime_options is None
        or readiness.corpus_dir is None
    ):
        raise ValueError("DCI context acceptance preflight failed")
    profile = resolve_context_profile(profile_name)
    if profile is None or profile.retained_turns != 12:
        raise ValueError("DCI context acceptance contract is invalid")
    output_dir = readiness.output_root / profile_name
    commands = tuple(
        f"sed -n '{start},{start + 2}p' pressure.txt"
        for start in (1, 3, 5, 7, 9)
    )
    question = (
        "Run exactly these five bash commands as five separate tool calls in order. "
        "Do not combine, shorten, or skip a command. Wait for every tool result, then "
        "reply only with done:\n" + "\n".join(commands)
    )
    options = readiness.runtime_options
    request = DciRunRequest(
        run_id=f"context-acceptance-{profile_name}",
        question=question,
        cwd=readiness.corpus_dir,
        provider=options.provider,
        model=options.model,
        tools="read,bash",
        max_turns=8,
        timeout_seconds=options.timeout_seconds,
        runtime_context_level=profile_name,
        thinking_level=options.thinking_level,
        node_max_old_space_size_mb=options.node_max_old_space_size_mb,
        keep_session=True,
        extra_args=options.extra_args,
        stream_text=False,
    )
    result = run_pi_research(readiness.paths, request, output_dir=output_dir)
    if result.status != "completed":
        raise ValueError("DCI context acceptance evidence is invalid")
    try:
        state = json.loads((output_dir / "state.json").read_text(encoding="utf-8"))
        summary = state["context_policy"]["public_summary"]
    except (KeyError, OSError, TypeError, UnicodeError, json.JSONDecodeError):
        raise ValueError("DCI context acceptance evidence is invalid") from None
    if (
        not isinstance(summary, dict)
        or summary.get("profile") != profile_name
        or summary.get("contract_version") != profile.contract_version
        or summary.get("extension_version") != readiness.extension_version
        or summary.get("extension_sha256") != readiness.extension_sha256
    ):
        raise ValueError("DCI context acceptance evidence is invalid")
    case = ContextAcceptanceCase(
        profile=profile_name,
        compactions=summary.get("compactions"),
        summary_attempts=summary.get("summary_attempts"),
        summary_successes=summary.get("summary_successes"),
        summary_suppressed=summary.get("summary_suppressed"),
        retained_turns=profile.retained_turns,
        artifact_digests=_artifact_digests(output_dir),
    )
    case.validate()
    return case


def _report(
    readiness: ContextAcceptanceReadiness,
    cases: Sequence[ContextAcceptanceCase],
) -> dict[str, object]:
    if (
        _PUBLIC_NAME.fullmatch(readiness.provider) is None
        or _PUBLIC_NAME.fullmatch(readiness.model) is None
        or _REVISION.fullmatch(readiness.pi_revision) is None
        or not readiness.extension_version
        or _SHA256.fullmatch(readiness.extension_sha256) is None
        or _SHA256.fullmatch(readiness.corpus_sha256) is None
        or [case.profile for case in cases] != ["level3", "level4"]
    ):
        raise ValueError("DCI context acceptance evidence is invalid")
    for case in cases:
        case.validate()
    return {
        "schema": REPORT_SCHEMA,
        "mode": "bounded-provider-backed",
        "provider": readiness.provider,
        "model": readiness.model,
        "pi_revision": readiness.pi_revision,
        "extension_version": readiness.extension_version,
        "extension_sha256": readiness.extension_sha256,
        "corpus_fixture_sha256": readiness.corpus_sha256,
        "provider_operations": 2,
        "api_request_multiplicity": "externally ambiguous",
        "full_dataset_ran": False,
        "cases": [
            {
                "profile": case.profile,
                "compactions": case.compactions,
                "summary_attempts": case.summary_attempts,
                "summary_successes": case.summary_successes,
                "summary_suppressed": case.summary_suppressed,
                "retained_turns": case.retained_turns,
                "artifact_digests": dict(case.artifact_digests),
            }
            for case in cases
        ],
    }


def _write_report(output_root: Path, report: dict[str, object]) -> None:
    path = output_root / "context-acceptance.json"
    raw = (json.dumps(report, sort_keys=True, indent=2) + "\n").encode()
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)


def main(
    argv: Sequence[str] | None = None,
    *,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
    repo_root: Path | None = None,
    readiness_checker: ReadinessChecker | None = None,
    provider_runner: ProviderRunner | None = None,
) -> int:
    """Run model-free verification or exactly two authorized bounded cases."""

    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    try:
        args = _parser().parse_args(argv)
        _model_free_contract()
    except (argparse.ArgumentError, OSError, RuntimeError, TypeError, ValueError):
        stderr.write("DCI context acceptance verification failed\n")
        return 2
    if not args.provider_backed:
        stdout.write("PASS\n")
        stdout.write("Provider operations: 0\n")
        stdout.write("Planned provider operations: 2\n")
        stdout.write("API request multiplicity: externally ambiguous\n")
        stdout.write("Full dataset ran: no\n")
        return 0

    root = Path.cwd().resolve() if repo_root is None else Path(repo_root).resolve()
    checker = _default_readiness if readiness_checker is None else readiness_checker
    runner = _default_provider_runner if provider_runner is None else provider_runner
    try:
        readiness = checker(args, root)
        cases = []
        for profile in ("level3", "level4"):
            case = runner(readiness, profile)
            if not isinstance(case, ContextAcceptanceCase):
                raise ValueError("DCI context acceptance evidence is invalid")
            case.validate()
            cases.append(case)
        report = _report(readiness, cases)
        readiness.output_root.mkdir(parents=True, exist_ok=True)
        _write_report(readiness.output_root, report)
    except (OSError, RuntimeError, TypeError, ValueError):
        stderr.write("DCI context acceptance preflight failed\n")
        return 2
    stdout.write("PASS\n")
    stdout.write("Provider operations: 2\n")
    stdout.write("API request multiplicity: externally ambiguous\n")
    stdout.write("Full dataset ran: no\n")
    stdout.write("Report: context-acceptance.json\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
