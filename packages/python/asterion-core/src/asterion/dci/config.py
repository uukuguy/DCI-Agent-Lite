"""Configuration boundary for the independent Asterion DCI product."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


@dataclass(frozen=True)
class DciPiPaths:
    """Resolved external Pi checkout paths owned by an Asterion DCI run."""

    repo_dir: Path
    package_dir: Path
    agent_dir: Path


@dataclass(frozen=True)
class DciPaths:
    """Resolved paths for one independent Asterion DCI installation."""

    repo_root: Path
    pi: DciPiPaths
    output_root: Path


@dataclass(frozen=True)
class DciRuntimeOptions:
    """Resolved shared DCI Pi runtime settings."""

    provider: str | None
    model: str | None
    tools: str = "read,bash"
    timeout_seconds: float | None = 3600.0
    runtime_context_level: str | None = None
    thinking_level: str | None = None
    node_max_old_space_size_mb: int | None = None
    keep_session: bool = False
    extra_args: tuple[str, ...] = ()


def load_asterion_dci_env(repo_root: Path) -> Path:
    """Load the product .env without overriding inherited process values."""

    env_path = Path(repo_root).resolve() / ".env"
    load_dotenv(env_path, override=False)
    return env_path


def resolve_dci_paths(repo_root: Path) -> DciPaths:
    """Resolve shared DCI Pi paths and Asterion-compatible aliases."""

    root = Path(repo_root).resolve()
    pi_dir = _configured_path_shared(
        "DCI_PI_DIR", "ASTERION_DCI_PI_DIR", root / "pi", root=root
    )
    package_dir = _configured_path_shared(
        "DCI_PI_PACKAGE_DIR",
        "ASTERION_DCI_PI_PACKAGE_DIR",
        pi_dir / "packages" / "coding-agent",
        root=root,
    )
    agent_dir = _configured_path_shared(
        "DCI_PI_AGENT_DIR",
        "ASTERION_DCI_PI_AGENT_DIR",
        pi_dir / ".pi" / "agent",
        root=root,
    )
    output_root = _configured_path(
        "ASTERION_DCI_OUTPUT_ROOT", root / "outputs" / "asterion-dci-runs", root=root
    )
    return DciPaths(
        repo_root=root,
        pi=DciPiPaths(
            repo_dir=pi_dir,
            package_dir=package_dir,
            agent_dir=agent_dir,
        ),
        output_root=output_root,
    )


def resolve_dci_runtime_options(
    overrides: Mapping[str, object] | None = None,
) -> DciRuntimeOptions:
    """Resolve shared DCI runtime defaults with explicit values taking priority."""

    values = {} if overrides is None else dict(overrides)
    return DciRuntimeOptions(
        provider=_override_or_env(values, "provider", "DCI_PROVIDER"),
        model=_override_or_env(values, "model", "DCI_MODEL"),
        tools=str(_override_or_env(values, "tools", "DCI_TOOLS", "read,bash")),
        timeout_seconds=_timeout_value(
            _override_or_env(values, "timeout_seconds", "DCI_RPC_TIMEOUT_SECONDS", "3600")
        ),
        runtime_context_level=_override_or_env(
            values, "runtime_context_level", "DCI_RUNTIME_CONTEXT_LEVEL"
        ),
        thinking_level=_override_or_env(values, "thinking_level", "DCI_PI_THINKING_LEVEL"),
        node_max_old_space_size_mb=_optional_positive_int(
            _override_or_env(
                values, "node_max_old_space_size_mb", "DCI_NODE_MAX_OLD_SPACE_SIZE_MB"
            )
        ),
        keep_session=bool(values.get("keep_session", False)),
        extra_args=tuple(values.get("extra_args", ())),
    )


def _override_or_env(
    values: Mapping[str, object], key: str, environment_name: str, default: object = None
) -> object:
    if key in values:
        return values[key]
    return os.environ.get(environment_name, default)


def _timeout_value(value: object) -> float | None:
    if value is None:
        return None
    try:
        timeout_seconds = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("DCI RPC timeout must be a non-negative number") from error
    if timeout_seconds < 0:
        raise ValueError("DCI RPC timeout must be a non-negative number")
    return timeout_seconds


def _optional_positive_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        raise ValueError("DCI Node heap size must be a positive integer")
    try:
        parsed = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError("DCI Node heap size must be a positive integer") from error
    if parsed <= 0 or str(parsed) != str(value).strip():
        raise ValueError("DCI Node heap size must be a positive integer")
    return parsed


def _configured_path(name: str, default: Path, *, root: Path) -> Path:
    value = os.environ.get(name, "").strip()
    path = Path(value).expanduser() if value else default
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _configured_path_shared(
    shared_name: str, alias_name: str, default: Path, *, root: Path
) -> Path:
    value = os.environ.get(shared_name, "").strip() or os.environ.get(alias_name, "").strip()
    path = Path(value).expanduser() if value else default
    if not path.is_absolute():
        path = root / path
    return path.resolve()
