#!/usr/bin/env python3
"""Validate that autonomous project work has one recoverable parent package."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

import yaml


PACKAGE_HEADER = re.compile(r"^## (?P<id>[A-Z][A-Z0-9]*-\d+) — (?P<title>.+)$")
H2_HEADER = re.compile(r"^[ ]{0,3}##(?:[ \t]+|$)")
FENCE_LINE = re.compile(r"^[ ]{0,3}(?P<fence>`{3,}|~{3,})(?P<rest>.*)$")
FIELD_LINE = re.compile(r"^- (?P<field>[A-Za-z ]+): (?P<value>.*)$")
LIFECYCLE_MARKER = re.compile(
    r"^> Project lifecycle: (?P<value>[a-z]+)$", re.MULTILINE
)
VALID_LIFECYCLES = {"active", "complete"}
RESUME_MARKER = re.compile(
    r"^Active work package: (?P<id>[A-Z][A-Z0-9]*-\d+|none)\s*$",
    re.MULTILINE,
)
REQUIRED_FIELDS = ("Scope", "Dependencies", "Acceptance", "Design", "Plan")
INACTIVE_CLIMB_PHASES = {"completed", "hard-pause", "retired"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root to validate",
    )
    parser.add_argument(
        "--climb-hypothesis",
        help="hypothesis that a climb cycle is about to dispatch",
    )
    return parser.parse_args()


def read_text(path: Path, errors: list[str], label: str) -> str:
    try:
        return path.read_text()
    except FileNotFoundError:
        errors.append(f"missing {label}: {path.relative_to(path.parents[2])}")
        return ""


def parse_worklist(
    path: Path, errors: list[str]
) -> tuple[list[dict[str, str]], str | None]:
    text = read_text(path, errors, "worklist")
    packages: list[dict[str, str]] = []
    package_ids: set[str] = set()
    lifecycle_markers: list[str] = []
    current: dict[str, str] | None = None
    fence_character: str | None = None
    fence_length = 0
    for line in text.splitlines():
        fence = FENCE_LINE.match(line)
        if fence_character is not None:
            if (
                fence is not None
                and fence.group("fence")[0] == fence_character
                and len(fence.group("fence")) >= fence_length
                and not fence.group("rest").strip()
            ):
                fence_character = None
                fence_length = 0
            continue
        if fence is not None:
            fence_character = fence.group("fence")[0]
            fence_length = len(fence.group("fence"))
            continue

        lifecycle = LIFECYCLE_MARKER.fullmatch(line)
        if lifecycle is not None:
            lifecycle_markers.append(lifecycle.group("value"))

        if H2_HEADER.match(line):
            current = None
            header = PACKAGE_HEADER.fullmatch(line)
            if header is None:
                continue
            package_id = header.group("id")
            if package_id in package_ids:
                errors.append(f"worklist contains duplicate package ID {package_id}")
            package_ids.add(package_id)
            current = {"ID": header.group("id"), "Title": header.group("title")}
            packages.append(current)
            continue
        field = FIELD_LINE.match(line)
        if field and current is not None:
            field_name = field.group("field")
            if field_name in current:
                errors.append(
                    f"{current['ID']} contains duplicate field {field_name}"
                )
            else:
                current[field_name] = field.group("value")
    if not packages:
        errors.append("worklist contains no packages")
    if len(lifecycle_markers) != 1:
        errors.append("worklist must contain exactly one project lifecycle marker")
        lifecycle = None
    else:
        lifecycle = lifecycle_markers[0]
    if lifecycle not in VALID_LIFECYCLES:
        if lifecycle is not None:
            errors.append(f"unknown project lifecycle {lifecycle}")
    return packages, lifecycle


def validate_required_fields(active: list[dict[str, str]], errors: list[str]) -> None:
    for package in active:
        package_id = package["ID"]
        for field in REQUIRED_FIELDS:
            value = package.get(field, "").strip()
            if not value or value == "not yet planned":
                errors.append(f"{package_id} missing required field {field}")


def validate_markers(
    root: Path,
    lifecycle: str | None,
    active_id: str | None,
    errors: list[str],
) -> None:
    architecture = root / "asterion/docs/architecture/agent-framework.md"
    if not architecture.is_file():
        errors.append("missing framework north-star architecture document")

    current = read_text(
        root / "docs/status/CURRENT-STATE.md", errors, "CURRENT-STATE"
    )
    required_marker = "Framework north star: `asterion/docs/architecture/agent-framework.md`"
    if required_marker not in current:
        errors.append("CURRENT-STATE missing framework north-star marker")

    resume = read_text(
        root / "docs/status/RESUME-NEXT-SESSION.md", errors, "RESUME"
    )
    marker = RESUME_MARKER.search(resume)
    if marker is None:
        errors.append("RESUME missing active work package marker")
    elif active_id is not None and marker.group("id") != active_id:
        errors.append(f"resume names {marker.group('id')} but active package is {active_id}")
    elif lifecycle == "complete" and marker.group("id") != "none":
        errors.append("complete lifecycle requires RESUME active work package none")


def load_hypotheses(root: Path, errors: list[str]) -> dict[str, dict[str, Any]]:
    path = root / "docs/status/climb/hypotheses.yaml"
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except FileNotFoundError:
        errors.append("missing climb hypotheses state")
        return {}
    hypotheses = data.get("hypotheses")
    if not isinstance(hypotheses, list):
        errors.append("climb hypotheses state is malformed")
        return {}
    return {
        item["id"]: item
        for item in hypotheses
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def validate_hypothesis(
    hypothesis_id: str,
    hypotheses: dict[str, dict[str, Any]],
    active_id: str | None,
    errors: list[str],
) -> None:
    hypothesis = hypotheses.get(hypothesis_id)
    if hypothesis is None or hypothesis.get("work_package_id") is None:
        errors.append(f"unparented climb hypothesis {hypothesis_id}")
        return
    if active_id is None:
        errors.append(
            f"climb hypothesis {hypothesis_id} cannot dispatch without an active package"
        )
    elif hypothesis["work_package_id"] != active_id:
        errors.append(
            f"climb hypothesis {hypothesis_id} belongs to {hypothesis['work_package_id']}, not {active_id}"
        )


def validate_active_climb(
    root: Path,
    lifecycle: str | None,
    active_id: str | None,
    requested_hypothesis: str | None,
    errors: list[str],
) -> None:
    state_path = root / "docs/status/climb/session-state.json"
    try:
        state = json.loads(state_path.read_text())
    except FileNotFoundError:
        errors.append("missing climb session state")
        state = {}
    except json.JSONDecodeError:
        errors.append("climb session state is malformed")
        state = {}

    hypotheses: dict[str, dict[str, Any]] | None = None
    phase = state.get("phase")
    if phase not in INACTIVE_CLIMB_PHASES:
        if lifecycle == "complete":
            errors.append("active climb session cannot run in complete lifecycle")
        work_package_id = state.get("work_package_id")
        if not isinstance(work_package_id, str):
            errors.append("active climb session lacks work_package_id")
        elif active_id is not None and work_package_id != active_id:
            errors.append(
                f"active climb session belongs to {work_package_id}, not {active_id}"
            )
        selected = state.get("next_hypothesis")
        if isinstance(selected, str):
            hypotheses = load_hypotheses(root, errors)
            validate_hypothesis(selected, hypotheses, active_id, errors)

    if requested_hypothesis is not None:
        if hypotheses is None:
            hypotheses = load_hypotheses(root, errors)
        validate_hypothesis(requested_hypothesis, hypotheses, active_id, errors)


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    errors: list[str] = []
    worklist_path = root / "docs/status/WORKLIST.md"
    packages, lifecycle = parse_worklist(worklist_path, errors)
    active = [item for item in packages if item.get("Status") == "in_progress"]
    if lifecycle == "active" and len(active) != 1:
        errors.append(
            f"active lifecycle requires exactly one in_progress package, found {len(active)}"
        )
    elif lifecycle == "complete":
        if active:
            errors.append(
                "complete lifecycle requires zero in_progress packages, "
                f"found {len(active)}"
            )
        incomplete = [
            f"{item['ID']}={item.get('Status', 'missing')}"
            for item in packages
            if item.get("Status") != "completed"
        ]
        if incomplete:
            errors.append(
                "complete lifecycle requires every package completed: "
                + ", ".join(incomplete)
            )
    validate_required_fields(active, errors)
    active_id = active[0]["ID"] if len(active) == 1 else None
    validate_markers(root, lifecycle, active_id, errors)
    validate_active_climb(
        root, lifecycle, active_id, args.climb_hypothesis, errors
    )
    payload = {
        "ok": not errors,
        "lifecycle": lifecycle,
        "active_package": active_id,
        "active_package_fields": dict(active[0]) if len(active) == 1 else None,
        "errors": errors,
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
