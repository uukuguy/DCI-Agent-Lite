"""Project-level configuration helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dci.effective_config import ConfigLayers


def load_project_env(repo_root: Path) -> Path:
    """Load ``.env`` from *repo_root* without overriding the process environment."""

    env_path = repo_root / ".env"
    layers = ConfigLayers.from_repo(repo_root)
    layers.materialize(os.environ)
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
