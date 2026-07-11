"""Project-level configuration helpers."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv


def load_project_env(repo_root: Path) -> Path:
    """Load ``.env`` from *repo_root* without overriding the process environment."""

    env_path = repo_root / ".env"
    load_dotenv(env_path, override=False)
    return env_path
