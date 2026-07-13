"""Configuration boundary for the independent Asterion DCI product."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

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


def load_asterion_dci_env(repo_root: Path) -> Path:
    """Load the product .env without overriding inherited process values."""

    env_path = Path(repo_root).resolve() / ".env"
    load_dotenv(env_path, override=False)
    return env_path


def resolve_dci_paths(repo_root: Path) -> DciPaths:
    """Resolve only the ASTERION_DCI_* path configuration namespace."""

    root = Path(repo_root).resolve()
    pi_dir = _configured_path("ASTERION_DCI_PI_DIR", root / "pi", root=root)
    package_dir = _configured_path(
        "ASTERION_DCI_PI_PACKAGE_DIR",
        pi_dir / "packages" / "coding-agent",
        root=root,
    )
    agent_dir = _configured_path(
        "ASTERION_DCI_PI_AGENT_DIR", pi_dir / ".pi" / "agent", root=root
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


def _configured_path(name: str, default: Path, *, root: Path) -> Path:
    value = os.environ.get(name, "").strip()
    path = Path(value).expanduser() if value else default
    if not path.is_absolute():
        path = root / path
    return path.resolve()
