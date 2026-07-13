"""Operator-validated lifecycle for one controlled-executor sidecar."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from asterion.services.controlled_executor import ControlledExecutorError
from asterion.services.controlled_executor_jsonl import TrustedValidationConfig


@dataclass(frozen=True)
class OperatorExecutorConfig:
    binary_path: Path
    policy_path: Path
    validation_config: TrustedValidationConfig


def load_operator_executor_config(
    binary: str | Path, policy: str | Path, validation: str | Path
) -> OperatorExecutorConfig:
    """Load the closed explicit operator configuration without echoing values."""

    binary_path = _regular_file(binary)
    policy_path = _regular_file(policy)
    validation_path = _regular_file(validation)
    try:
        policy_value = json.loads(policy_path.read_text())
        validation_value = json.loads(validation_path.read_text())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise ControlledExecutorError("controlled executor configuration is invalid") from None
    if not isinstance(policy_value, Mapping) or not isinstance(validation_value, Mapping):
        raise ControlledExecutorError("controlled executor configuration is invalid")
    required = {
        "program_id",
        "argument_prefix",
        "cwd",
        "deadline_ms",
        "max_output_bytes",
    }
    if set(validation_value) != required or not isinstance(
        validation_value["argument_prefix"], list
    ):
        raise ControlledExecutorError("controlled executor configuration is invalid")
    try:
        validation_config = TrustedValidationConfig(
            program_id=validation_value["program_id"],
            argument_prefix=tuple(validation_value["argument_prefix"]),
            cwd=validation_value["cwd"],
            deadline_ms=validation_value["deadline_ms"],
            max_output_bytes=validation_value["max_output_bytes"],
        )
    except (ControlledExecutorError, TypeError):
        raise ControlledExecutorError("controlled executor configuration is invalid") from None
    return OperatorExecutorConfig(
        binary_path=binary_path,
        policy_path=policy_path,
        validation_config=validation_config,
    )


def _regular_file(value: str | Path) -> Path:
    path = Path(value)
    if path.is_symlink():
        raise ControlledExecutorError("controlled executor configuration is unsafe")
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        raise ControlledExecutorError("controlled executor configuration is unavailable") from None
    if not resolved.is_file():
        raise ControlledExecutorError("controlled executor configuration is invalid")
    return resolved
