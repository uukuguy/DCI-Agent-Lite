"""Explicit first-party runtime factories for the Asterion CLI."""

from __future__ import annotations

import math
import os
import shutil
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv

from asterion.runtime.factory import (
    RuntimeFactoryBinding,
    RuntimeFactoryContext,
    RuntimeFactoryError,
    RuntimeFactoryRegistry,
)
from asterion.runtimes.claude_code import ClaudeCodeRuntimeClient
from asterion.runtimes.pi import PiRuntimeClient


PI_CAPABILITIES = ("filesystem.read", "shell")
CLAUDE_CAPABILITIES = ("claude.tool.glob", "claude.tool.grep", "filesystem.read")
_CLAUDE_PROVIDER_CONFIG = {
    "anthropic": ("https://api.anthropic.com", "ANTHROPIC_API_KEY"),
    "minimax": ("https://api.minimax.io/anthropic", "MINIMAX_API_KEY"),
    "minimax-cn": ("https://api.minimaxi.com/anthropic", "MINIMAX_CN_API_KEY"),
}
_CLAUDE_MODEL_ENVIRONMENT_NAMES = (
    "ANTHROPIC_MODEL",
    "ANTHROPIC_DEFAULT_OPUS_MODEL",
    "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "ANTHROPIC_SMALL_FAST_MODEL",
)


def default_runtime_factory_registry() -> RuntimeFactoryRegistry:
    """Return the host-owned runtime bindings shipped with Asterion."""

    load_dotenv(Path.cwd() / ".env", override=False)
    return RuntimeFactoryRegistry(
        (
            RuntimeFactoryBinding(
                runtime_id="pi.reference",
                capabilities=PI_CAPABILITIES,
                factory=_create_pi_runtime,
            ),
            RuntimeFactoryBinding(
                runtime_id="claude-code.reference",
                capabilities=CLAUDE_CAPABILITIES,
                factory=_create_claude_code_runtime,
            ),
        )
    )


def _create_pi_runtime(context: RuntimeFactoryContext) -> PiRuntimeClient:
    if context.runtime_id != "pi.reference":
        raise RuntimeFactoryError("runtime factory context is invalid")
    working_root = Path.cwd()
    pi_dir = _configured_path("DCI_PI_DIR", working_root / "pi", root=working_root)
    package_dir = _configured_path(
        "DCI_PI_PACKAGE_DIR", pi_dir / "packages/coding-agent", root=working_root
    )
    agent_dir = _configured_path("DCI_PI_AGENT_DIR", pi_dir / ".pi/agent", root=working_root)
    runtime_cwd = _configured_path("ASTERION_RUNTIME_CWD", working_root, root=working_root)
    cli = package_dir / "dist/cli.js"
    node = shutil.which("node")
    if node is None or not cli.is_file() or not agent_dir.is_dir() or not runtime_cwd.is_dir():
        raise RuntimeFactoryError("Pi reference runtime is unavailable")

    command = [node, str(cli), "--mode", "rpc"]
    for option, environment_name in (
        ("--provider", "DCI_PROVIDER"),
        ("--model", "DCI_MODEL"),
        ("--tools", "DCI_TOOLS"),
    ):
        value = os.environ.get(environment_name, "").strip()
        if value:
            command.extend((option, value))
    environment = os.environ.copy()
    environment["PI_CODING_AGENT_DIR"] = str(agent_dir)
    return PiRuntimeClient(
        command=command,
        cwd=runtime_cwd,
        capabilities=PI_CAPABILITIES,
        env=environment,
    )


def _create_claude_code_runtime(
    context: RuntimeFactoryContext,
) -> ClaudeCodeRuntimeClient:
    if context.runtime_id != "claude-code.reference":
        raise RuntimeFactoryError("runtime factory context is invalid")
    executable = _configured_executable("ASTERION_CLAUDE_EXECUTABLE", "claude")
    runtime_cwd = _configured_path("ASTERION_RUNTIME_CWD", Path.cwd(), root=Path.cwd())
    evidence_root = _configured_path(
        "ASTERION_CLAUDE_OUTPUT_ROOT",
        Path.cwd() / "outputs/asterion-claude-runs",
        root=Path.cwd(),
    )
    if executable is None or not runtime_cwd.is_dir():
        raise RuntimeFactoryError("Claude Code runtime is unavailable")
    environment = _claude_provider_environment(os.environ)
    default_timeout_seconds = _configured_timeout_seconds(os.environ)
    return ClaudeCodeRuntimeClient(
        executable=executable,
        cwd=runtime_cwd,
        environment=environment,
        default_timeout_seconds=default_timeout_seconds,
        evidence_root=evidence_root,
    )


def _claude_provider_environment(environment: Mapping[str, str]) -> dict[str, str]:
    provider = environment.get("DCI_PROVIDER", "").strip()
    model = environment.get("DCI_MODEL", "").strip()
    provider_config = _CLAUDE_PROVIDER_CONFIG.get(provider)
    if provider_config is None or not model:
        raise RuntimeFactoryError("Claude Code provider configuration is unavailable")

    base_url, key_name = provider_config
    api_key = environment.get(key_name, "").strip()
    if not api_key:
        raise RuntimeFactoryError("Claude Code provider configuration is unavailable")

    native_environment = dict(environment)
    native_environment["ANTHROPIC_BASE_URL"] = base_url
    if provider == "anthropic":
        native_environment["ANTHROPIC_API_KEY"] = api_key
        native_environment.pop("ANTHROPIC_AUTH_TOKEN", None)
    else:
        native_environment["ANTHROPIC_AUTH_TOKEN"] = api_key
        native_environment.pop("ANTHROPIC_API_KEY", None)
    for name in _CLAUDE_MODEL_ENVIRONMENT_NAMES:
        native_environment[name] = model
    for name in (
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_FOUNDRY",
        "CLAUDE_CODE_USE_VERTEX",
    ):
        native_environment.pop(name, None)
    native_environment["API_TIMEOUT_MS"] = "3000000"
    native_environment["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] = "1"
    return native_environment


def _configured_timeout_seconds(environment: Mapping[str, str]) -> float | None:
    value = environment.get("DCI_RPC_TIMEOUT_SECONDS", "3600").strip()
    try:
        timeout_seconds = float(value)
    except ValueError:
        raise RuntimeFactoryError("Claude Code timeout configuration is invalid") from None
    if not math.isfinite(timeout_seconds) or timeout_seconds < 0:
        raise RuntimeFactoryError("Claude Code timeout configuration is invalid")
    return timeout_seconds or None


def _configured_path(name: str, default: Path, *, root: Path) -> Path:
    value = os.environ.get(name, "").strip()
    path = Path(value).expanduser() if value else default
    if not path.is_absolute():
        path = root / path
    return path.resolve()


def _configured_executable(name: str, default: str) -> str | None:
    value = os.environ.get(name, default).strip()
    if not value:
        return None
    candidate = Path(value).expanduser()
    if candidate.is_absolute() or candidate.parent != Path("."):
        return str(candidate) if candidate.is_file() else None
    return shutil.which(value)
