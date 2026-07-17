#!/usr/bin/env python3
"""Bind one validated body-free provider report to a terminal Climb result."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path


SHA256 = re.compile(r"[0-9a-f]{64}")
REPORT_KEYS = {
    "schema", "mode", "provider", "model", "pi_revision",
    "extension_version", "contract_version", "extension_sha256",
    "corpus_fixture_sha256", "provider_operations",
    "api_request_multiplicity", "full_dataset_ran", "user_turns_per_case",
    "cases",
}
CASE_KEYS = {
    "profile", "compactions", "preserved_turns", "summary_attempts",
    "summary_successes", "summary_suppressed", "artifact_digests",
}
ARTIFACT_NAMES = ("context-policy.json", "events.jsonl", "state.json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--hypothesis-id", default="AF-310-H-005")
    parser.add_argument("--state-dir", type=Path, default=Path("docs/status/climb"))
    parser.add_argument("--pi-dir", type=Path)
    return parser


def _reject_symlink_components(path: Path) -> None:
    # Reject the caller-controlled leaf and containing artifact directory. System
    # temporary roots may themselves traverse an OS-managed compatibility link.
    if path.is_symlink() or path.parent.is_symlink():
        raise ValueError("provider evidence path is invalid")


def _read_private_regular(path: Path) -> bytes:
    _reject_symlink_components(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_mode & 0o077:
            raise ValueError("provider evidence file is invalid")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            return stream.read()
    finally:
        os.close(descriptor)


def _pi_identity(pi_dir: Path) -> tuple[str, str]:
    revision = subprocess.run(
        ["git", "-C", str(pi_dir), "rev-parse", "HEAD"],
        text=True, capture_output=True, check=True,
    ).stdout.strip()
    tracked_status = subprocess.run(
        ["git", "-C", str(pi_dir), "status", "--porcelain=v1", "--untracked-files=normal"],
        text=True, capture_output=True, check=True,
    ).stdout.encode()
    if tracked_status:
        raise ValueError("Pi worktree must be clean")
    return revision, hashlib.sha256(tracked_status).hexdigest()


def _load_report(
    path: Path, root: Path, *, pi_dir: Path
) -> tuple[dict[str, object], str, str]:
    raw = _read_private_regular(path)
    report = json.loads(raw)
    manifest = json.loads(
        (root / "asterion/src/asterion/dci/resources/pi/context-extension-manifest.json").read_text()
    )
    locked_pi = (root / "pi-revision.txt").read_text().strip()
    current_pi, pi_status_sha256 = _pi_identity(pi_dir)
    if (
        not isinstance(report, dict)
        or set(report) != REPORT_KEYS
        or report.get("schema") != "asterion.dci.context-acceptance/v1"
        or report.get("mode") != "bounded-provider-backed"
        or report.get("contract_version") != manifest.get("contract_version")
        or report.get("extension_version") != manifest.get("extension_version")
        or report.get("extension_sha256") != manifest.get("sha256")
        or report.get("pi_revision") != locked_pi
        or report.get("pi_revision") != current_pi
        or report.get("provider_operations") != 2
        or report.get("user_turns_per_case") != 13
        or report.get("api_request_multiplicity") != "externally ambiguous"
        or report.get("full_dataset_ran") is not False
        or SHA256.fullmatch(str(report.get("corpus_fixture_sha256"))) is None
    ):
        raise ValueError("provider evidence report is invalid")
    cases = report.get("cases")
    if not isinstance(cases, list) or len(cases) != 2:
        raise ValueError("provider evidence report is invalid")
    for index, case in enumerate(cases):
        profile = ("level3", "level4")[index]
        preserved = case.get("preserved_turns") if isinstance(case, dict) else False
        if (
            not isinstance(case, dict)
            or set(case) != CASE_KEYS
            or case.get("profile") != profile
            or not isinstance(case.get("compactions"), int)
            or case["compactions"] < 1
            or not (preserved is None or (type(preserved) is int and preserved >= 0))
            or not isinstance(case.get("summary_attempts"), int)
            or not isinstance(case.get("summary_successes"), int)
            or type(case.get("summary_suppressed")) is not bool
            or not isinstance(case.get("artifact_digests"), dict)
            or set(case["artifact_digests"]) != set(ARTIFACT_NAMES)
        ):
            raise ValueError("provider evidence report is invalid")
        for name in ARTIFACT_NAMES:
            artifact = path.parent / profile / name
            actual = hashlib.sha256(_read_private_regular(artifact)).hexdigest()
            if case["artifact_digests"].get(name) != actual:
                raise ValueError("provider evidence artifact digest is invalid")
    level3, level4 = cases
    if (
        level3["preserved_turns"] != 12
        or level3["summary_attempts"] != 0
        or level3["summary_successes"] != 0
        or level4["summary_attempts"] < 1
        or level4["summary_successes"] < 1
        or level4["summary_suppressed"] is not False
    ):
        raise ValueError("provider evidence report is invalid")
    return report, hashlib.sha256(raw).hexdigest(), pi_status_sha256


def _atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
        os.replace(temporary, path)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _binding(section: str) -> tuple[str, str, str] | None:
    match = re.search(
        r"    provider_evidence:\n      path: (\S+)\n"
        r"      sha256: ([0-9a-f]{64})\n      report_sha256: ([0-9a-f]{64})",
        section,
    )
    return match.groups() if match else None


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    root = Path(__file__).resolve().parents[2]
    report, report_sha256, pi_status_sha256 = _load_report(
        args.report, root, pi_dir=(root / "pi" if args.pi_dir is None else args.pi_dir)
    )
    record = {
        "schema": "dci.climb.provider-evidence/v2",
        "hypothesis_id": args.hypothesis_id,
        "report_sha256": report_sha256,
        "contract_version": report["contract_version"],
        "extension_version": report["extension_version"],
        "extension_sha256": report["extension_sha256"],
        "pi_revision": report["pi_revision"],
        "pi_worktree_clean": True,
        "pi_tracked_status_sha256": pi_status_sha256,
        "provider_operations": report["provider_operations"],
        "user_turns_per_case": report["user_turns_per_case"],
        "api_request_multiplicity": report["api_request_multiplicity"],
        "full_dataset_ran": report["full_dataset_ran"],
        "cases": report["cases"],
    }
    record_raw = (json.dumps(record, indent=2, sort_keys=True) + "\n").encode()
    record_sha256 = hashlib.sha256(record_raw).hexdigest()
    relative = f"provider-evidence/{args.hypothesis_id.lower()}.json"
    evidence_path = args.state_dir / relative

    hypotheses = args.state_dir / "hypotheses.yaml"
    text = hypotheses.read_text()
    start = text.index(f"- id: {args.hypothesis_id}\n")
    end = text.find("\n- id: ", start + 1)
    end = len(text) if end < 0 else end
    section = text[start:end]
    existing = _binding(section)
    if existing is not None:
        if existing != (relative, record_sha256, report_sha256):
            raise ValueError("provider evidence is already bound to different evidence")
        if not evidence_path.is_file() or evidence_path.read_bytes() != record_raw:
            raise ValueError("bound provider evidence is invalid")
        print(json.dumps({"hypothesis": args.hypothesis_id, "evidence_sha256": record_sha256}))
        return 0

    needle = "    decision_reason: deterministic local package acceptance"
    if section.count(needle) != 1 or "    verdict: confirmed 4/4" not in section:
        raise ValueError("terminal Climb result is invalid")
    if evidence_path.exists():
        raise ValueError("unbound provider evidence path already exists")
    binding = (
        f"{needle}\n    provider_evidence:\n"
        f"      path: {relative}\n      sha256: {record_sha256}\n"
        f"      report_sha256: {report_sha256}"
    )
    updated = (text[:start] + section.replace(needle, binding) + text[end:]).encode()
    _atomic_write(evidence_path, record_raw)
    try:
        _atomic_write(hypotheses, updated)
    except BaseException:
        evidence_path.unlink(missing_ok=True)
        raise
    print(json.dumps({"hypothesis": args.hypothesis_id, "evidence_sha256": record_sha256}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
