"""Explicit first-party runtime factories for the Asterion CLI."""

from __future__ import annotations

import os
import shutil
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
    return ClaudeCodeRuntimeClient(
        executable=executable,
        cwd=runtime_cwd,
        environment=os.environ.copy(),
        evidence_root=evidence_root,
    )


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
