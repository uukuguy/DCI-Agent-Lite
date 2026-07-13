"""Provider-owned native executor for one Asterion DCI application run."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from asterion.dci.config import DciPaths, load_asterion_dci_env, resolve_dci_paths
from asterion.dci.run import DciRunRequest, DciRunResult, run_pi_research


class EnvironmentDciRunExecutor:
    """Resolve application configuration before invoking the native Pi workflow."""

    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        run_native: Callable[[DciPaths, DciRunRequest], DciRunResult] = run_pi_research,
    ) -> None:
        self._repo_root = Path.cwd() if repo_root is None else Path(repo_root)
        self._run_native = run_native

    def run(self, request: DciRunRequest) -> DciRunResult:
        root = self._repo_root.resolve()
        load_asterion_dci_env(root)
        cwd = Path(os.environ.get("ASTERION_RUNTIME_CWD", root)).resolve()
        return self._run_native(
            resolve_dci_paths(root),
            replace(request, cwd=cwd),
        )
