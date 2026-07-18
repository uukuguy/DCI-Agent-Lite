"""Project-level configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Mapping, MutableMapping

from dotenv import dotenv_values


ValueSource = Literal["invocation", "environment", "runtime-default"]

PI_DEFAULT_PROVIDER = "openai-codex"
PI_DEFAULT_MODEL = "gpt-5.6-luna"
PI_DEFAULT_TOOLS = "read,bash"
PI_DEFAULT_MAX_TURNS = 100
PI_DEFAULT_TIMEOUT_SECONDS = 3600.0


@dataclass(frozen=True)
class ConfigLayers:
    """Immutable process and repository ``.env`` configuration snapshots."""

    process: Mapping[str, str]
    dotenv: Mapping[str, str]

    @classmethod
    def from_repo(
        cls, repo_root: Path, process_environment: Mapping[str, str] | None = None
    ) -> "ConfigLayers":
        process = dict(os.environ if process_environment is None else process_environment)
        loaded = dotenv_values(Path(repo_root) / ".env")
        dotenv = {key: value for key, value in loaded.items() if value is not None}
        return cls(
            process=MappingProxyType(process),
            dotenv=MappingProxyType(dotenv),
        )

    def resolve(
        self, name: str, invocation: object, default: object
    ) -> tuple[object, ValueSource]:
        if invocation is not None:
            return invocation, "invocation"
        if name in self.process:
            return self.process[name], "environment"
        if name in self.dotenv:
            return self.dotenv[name], "environment"
        return default, "runtime-default"

    def materialize(self, target: MutableMapping[str, str]) -> None:
        for name, value in self.dotenv.items():
            target.setdefault(name, value)


@dataclass(frozen=True)
class OriginalRuntimeConfig:
    runtime: str
    provider: str
    model: str
    tools: str
    max_turns: int
    timeout_seconds: float | None
    thinking_level: str | None
    context_profile: str | None
    sources: Mapping[str, ValueSource]


def _nonempty_invocation(invocation: Mapping[str, object], name: str) -> object:
    value = invocation.get(name)
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _required_text(value: object, *, name: str, default: str) -> str:
    normalized = str(value).strip()
    return normalized or default


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _positive_int(value: object, *, name: str, default: int) -> int:
    if isinstance(value, str) and not value.strip():
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if parsed <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return parsed


def _optional_timeout(value: object) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("DCI_RPC_TIMEOUT_SECONDS must be a number") from exc
    if parsed < 0:
        raise ValueError("DCI_RPC_TIMEOUT_SECONDS must be non-negative")
    return parsed or None


def resolve_original_runtime(
    invocation: Mapping[str, object], layers: ConfigLayers
) -> OriginalRuntimeConfig:
    """Resolve the original product's Pi-only runtime configuration."""

    values: dict[str, object] = {}
    sources: dict[str, ValueSource] = {}
    specs = (
        ("runtime", "DCI_RUNTIME", "pi", "runtime"),
        ("provider", "DCI_PROVIDER", PI_DEFAULT_PROVIDER, "agent.provider"),
        ("model", "DCI_MODEL", PI_DEFAULT_MODEL, "agent.model"),
        ("tools", "DCI_TOOLS", PI_DEFAULT_TOOLS, "agent.tools"),
        ("max_turns", "DCI_MAX_TURNS", PI_DEFAULT_MAX_TURNS, "agent.max_turns"),
        (
            "timeout_seconds",
            "DCI_RPC_TIMEOUT_SECONDS",
            PI_DEFAULT_TIMEOUT_SECONDS,
            "agent.timeout_seconds",
        ),
        (
            "thinking_level",
            "DCI_PI_THINKING_LEVEL",
            None,
            "agent.thinking_level",
        ),
        (
            "context_profile",
            "DCI_RUNTIME_CONTEXT_LEVEL",
            None,
            "context.profile",
        ),
    )
    for field_name, environment_name, default, source_name in specs:
        value, source = layers.resolve(
            environment_name,
            _nonempty_invocation(invocation, field_name),
            default,
        )
        values[field_name] = value
        sources[source_name] = source

    runtime = _required_text(values["runtime"], name="runtime", default="pi")
    if runtime != "pi":
        raise ValueError(f"Original DCI runtime is unsupported: {runtime!r}")
    return OriginalRuntimeConfig(
        runtime=runtime,
        provider=_required_text(
            values["provider"], name="provider", default=PI_DEFAULT_PROVIDER
        ),
        model=_required_text(values["model"], name="model", default=PI_DEFAULT_MODEL),
        tools=_required_text(values["tools"], name="tools", default=PI_DEFAULT_TOOLS),
        max_turns=_positive_int(
            values["max_turns"], name="DCI_MAX_TURNS", default=PI_DEFAULT_MAX_TURNS
        ),
        timeout_seconds=_optional_timeout(values["timeout_seconds"]),
        thinking_level=_optional_text(values["thinking_level"]),
        context_profile=_optional_text(values["context_profile"]),
        sources=MappingProxyType(sources),
    )


def load_project_env(repo_root: Path) -> Path:
    """Load ``.env`` from *repo_root* without overriding the process environment."""

    env_path = repo_root / ".env"
    ConfigLayers.from_repo(repo_root).materialize(os.environ)
    return env_path


@dataclass(frozen=True)
class PiPaths:
    """Resolved paths for the external Pi checkout and its DCI integration."""

    repo_dir: Path
    package_dir: Path
    agent_dir: Path


def _project_path(repo_root: Path, value: str | Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def resolve_pi_paths(repo_root: Path) -> PiPaths:
    """Resolve Pi paths from `.env`, preferring the new `pi` checkout name.

    `DCI_PI_DIR` selects the checkout. Without it, an existing `pi` directory
    wins, followed by the legacy `pi-mono` path. Package and agent directories
    can be overridden independently for unusual layouts.
    """

    configured_pi_dir = os.environ.get("DCI_PI_DIR", "").strip()
    if configured_pi_dir:
        pi_dir = _project_path(repo_root, configured_pi_dir)
    else:
        candidates = (repo_root / "pi", repo_root / "pi-mono")
        pi_dir = next(
            (candidate.resolve() for candidate in candidates if candidate.exists()),
            candidates[0],
        )

    configured_package_dir = os.environ.get("DCI_PI_PACKAGE_DIR", "").strip()
    package_dir = (
        _project_path(repo_root, configured_package_dir)
        if configured_package_dir
        else pi_dir / "packages" / "coding-agent"
    )
    configured_agent_dir = os.environ.get("DCI_PI_AGENT_DIR", "").strip()
    agent_dir = (
        _project_path(repo_root, configured_agent_dir)
        if configured_agent_dir
        else pi_dir / ".pi" / "agent"
    )
    return PiPaths(repo_dir=pi_dir, package_dir=package_dir, agent_dir=agent_dir)
