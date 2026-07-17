from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from asterion.dci.application_executor import EnvironmentDciRunExecutor
from asterion.dci.artifacts import DciConversationFeatures
from asterion.dci.context_profiles import resolve_context_profile
from asterion.dci.run import DciRunRequest


class AsterionDciApplicationExecutorTests(unittest.TestCase):
    def test_application_executor_preserves_request_operator_semantics_without_streaming(
        self,
    ) -> None:
        calls: list[DciRunRequest] = []

        def run_native(_: object, request: DciRunRequest) -> object:
            calls.append(request)
            return object()

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            system_prompt = root / "system.txt"
            append_prompt = root / "append.txt"
            features = DciConversationFeatures(strip_usage=True)
            executor = EnvironmentDciRunExecutor(repo_root=root, run_native=run_native)
            with patch.dict(os.environ, {}, clear=True):
                executor.run(
                    DciRunRequest(
                        run_id="application-run",
                        question="question",
                        cwd=root,
                        max_turns=7,
                        show_tools=True,
                        system_prompt_file=system_prompt,
                        append_system_prompt_file=append_prompt,
                        conversation_features=features,
                    )
                )

        mapped = calls[0]
        self.assertEqual(mapped.max_turns, 7)
        self.assertTrue(mapped.show_tools)
        self.assertEqual(mapped.system_prompt_file, system_prompt)
        self.assertEqual(mapped.append_system_prompt_file, append_prompt)
        self.assertEqual(mapped.conversation_features, features)
        self.assertFalse(mapped.stream_text)

    def test_application_executor_applies_shared_options(self) -> None:
        calls: list[tuple[object, DciRunRequest]] = []

        def run_native(paths: object, request: DciRunRequest) -> object:
            calls.append((paths, request))
            return object()

        with tempfile.TemporaryDirectory() as temporary_directory:
            executor = EnvironmentDciRunExecutor(
                repo_root=Path(temporary_directory),
                run_native=run_native,
            )
            with patch.dict(
                os.environ,
                {
                    "DCI_PROVIDER": "openai",
                    "DCI_MODEL": "gpt-test",
                    "DCI_TOOLS": "read,bash",
                    "DCI_RUNTIME_CONTEXT_LEVEL": "level3",
                    "DCI_PI_THINKING_LEVEL": "high",
                },
                clear=True,
            ):
                executor.run(
                    DciRunRequest(
                        run_id="application-run",
                        question="question",
                        cwd=Path("ignored"),
                    )
                )

        mapped = calls[0][1]
        self.assertEqual(
            (mapped.provider, mapped.model, mapped.tools),
            ("openai", "gpt-test", "read,bash"),
        )
        self.assertEqual(
            (mapped.runtime_context_level, mapped.thinking_level),
            ("level3", "high"),
        )
        self.assertFalse(mapped.stream_text)

    def test_restricted_executor_honors_closed_request_tool_surface(self) -> None:
        calls: list[DciRunRequest] = []
        with tempfile.TemporaryDirectory() as temporary_directory:
            executor = EnvironmentDciRunExecutor(
                repo_root=Path(temporary_directory),
                run_native=lambda _paths, request: calls.append(request),
                honor_request_tools=True,
            )
            with patch.dict(os.environ, {"DCI_TOOLS": "read,bash"}, clear=True):
                executor.run(
                    DciRunRequest(
                        run_id="restricted-run",
                        question="question",
                        cwd=Path("ignored"),
                        tools="read,grep",
                    )
                )

        self.assertEqual(calls[0].tools, "read,grep")

    def test_application_executor_maps_every_profile_to_the_canonical_identity(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for name in ("level0", "level1", "level2", "level3", "level4"):
                calls: list[DciRunRequest] = []
                executor = EnvironmentDciRunExecutor(
                    repo_root=root,
                    run_native=lambda _paths, request: calls.append(request),
                )
                with self.subTest(profile=name), patch.dict(
                    os.environ,
                    {"DCI_RUNTIME_CONTEXT_LEVEL": name},
                    clear=True,
                ):
                    executor.run(
                        DciRunRequest(
                            run_id=f"application-{name}",
                            question="SECRET-QUESTION",
                            cwd=Path("ignored"),
                        )
                    )
                    self.assertEqual(
                        calls[0].context_profile.identity_payload(),
                        resolve_context_profile(name).identity_payload(),
                    )

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
