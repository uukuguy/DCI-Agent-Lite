from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.dci.application_executor import EnvironmentDciRunExecutor
from asterion.dci.run import DciRunRequest


class AsterionDciApplicationExecutorTests(unittest.TestCase):
    def test_maps_runtime_cwd_and_native_paths_to_one_pi_run(self) -> None:
        calls: list[tuple[object, DciRunRequest]] = []
        expected = object()

        def run_native(paths: object, request: DciRunRequest) -> object:
            calls.append((paths, request))
            return expected

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            runtime_cwd = root / "corpus"
            request = DciRunRequest(
                run_id="application-run",
                question="SECRET-QUESTION",
                cwd=Path("ignored"),
            )
            executor = EnvironmentDciRunExecutor(
                repo_root=root,
                run_native=run_native,
            )
            with patch.dict(
                os.environ,
                {
                    "ASTERION_RUNTIME_CWD": str(runtime_cwd),
                    "ASTERION_DCI_PI_DIR": "external-pi",
                    "ASTERION_DCI_OUTPUT_ROOT": "native-runs",
                },
                clear=True,
            ):
                result = executor.run(request)

        self.assertIs(result, expected)
        self.assertEqual(len(calls), 1)
        paths, mapped = calls[0]
        self.assertEqual(mapped.cwd, runtime_cwd.resolve())
        self.assertEqual(mapped.run_id, "application-run")
        self.assertEqual(mapped.question, "SECRET-QUESTION")
        self.assertEqual(paths.pi.repo_dir, (root / "external-pi").resolve())
        self.assertEqual(paths.output_root, (root / "native-runs").resolve())


if __name__ == "__main__":
    unittest.main()
