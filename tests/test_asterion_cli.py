from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import patch

from asterion.cli import _parser, main
from asterion.applications.dci_agent_lite.provider import create_provider as create_dci_provider
from asterion.applications.provider import InstalledApplication, InstalledApplicationProvider
from asterion.runtime.factory import RuntimeFactoryBinding, RuntimeFactoryRegistry
from asterion.runtime.host import RunEvent, RunRequest, RuntimeManifest
from asterion.services.controlled_executor import ControlledExecutionResult
from tests.test_application_discovery import FakeEntryPoint
from tests.test_installed_application_provider import provider


class FixtureRuntime:
    manifest = RuntimeManifest(runtime_id="pi.reference", capabilities=())

    async def run(
        self,
        request: RunRequest,
        *,
        signal: object | None = None,
    ) -> AsyncIterator[RunEvent]:
        del request, signal
        if False:
            yield RunEvent("", 0, "", {})


class ClaudeFixtureRuntime(FixtureRuntime):
    manifest = RuntimeManifest(runtime_id="claude-code.reference", capabilities=())


class DciClaudeFixtureRuntime:
    manifest = RuntimeManifest(
        runtime_id="claude-code.reference",
        capabilities=("filesystem.read", "shell"),
    )

    async def run(
        self,
        request: RunRequest,
        *,
        signal: object | None = None,
    ) -> AsyncIterator[RunEvent]:
        del signal
        yield RunEvent(request.run_id, 1, "run.started", {"capabilities": []})
        yield RunEvent(
            request.run_id,
            2,
            "artifact.created",
            {
                "artifact": {
                    "artifact_id": "answer",
                    "kind": "answer",
                    "media_type": "text/plain",
                    "uri": "fixture-answer.txt",
                }
            },
        )
        yield RunEvent(request.run_id, 3, "run.completed", {"status": "completed"})


class ControlledFixtureRuntime(FixtureRuntime):
    manifest = RuntimeManifest(
        runtime_id="pi.reference", capabilities=("filesystem.read", "shell")
    )


class FixtureExecutor:
    async def execute(self, request, *, signal=None):
        del request, signal
        return ControlledExecutionResult(
            status="succeeded",
            exit_code=0,
            stdout_bytes=0,
            stderr_bytes=0,
            stdout_truncated=False,
            stderr_truncated=False,
            duration_ms=0,
            failure_class=None,
        )


class FixtureManager:
    def __init__(self) -> None:
        self.config = None
        self.entered = False

    async def __aenter__(self):
        self.entered = True
        return FixtureExecutor()

    async def __aexit__(self, exc_type, exc, traceback):
        del exc_type, exc, traceback


def configure_manager(manager, config):
    manager.config = config
    return manager


class AsterionCliTests(unittest.TestCase):
    def test_list_reports_metadata_without_loading_provider(self) -> None:
        entry = FakeEntryPoint(name="example-app", factory=lambda: None)
        stdout = io.StringIO()

        code = main(
            ["list"],
            entry_points=(entry,),
            runtime_factories=RuntimeFactoryRegistry(()),
            stdout=stdout,
            stderr=io.StringIO(),
        )

        self.assertEqual(code, 0)
        self.assertEqual(entry.loads, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload[0]["provider_id"], "example-app")
        self.assertNotIn("SECRET-MODULE-PATH", stdout.getvalue())

    def test_list_selected_provider_reports_exact_applications(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            value = provider(Path(temp_dir))
            entry = FakeEntryPoint(name="example-app", factory=lambda: value)
            stdout = io.StringIO()
            code = main(
                ["list", "--provider", "example-app"],
                entry_points=(entry,),
                stdout=stdout,
                stderr=io.StringIO(),
            )

        self.assertEqual(code, 0)
        self.assertEqual(entry.loads, 1)
        self.assertEqual(
            json.loads(stdout.getvalue()),
            {
                "applications": [
                    {
                        "application_id": "example.research",
                        "runtime_ids": ["pi.reference"],
                        "selector": "example.research@1.0.0",
                        "version": "1.0.0",
                    }
                ],
                "provider_id": "example-app",
            },
        )

    def test_run_preflights_then_constructs_runtime_and_outputs_one_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            value = provider(Path(temp_dir))
            entry = FakeEntryPoint(name="example-app", factory=lambda: value)
            factory_calls = []

            def create_runtime(context):
                factory_calls.append(context)
                return FixtureRuntime()

            registry = RuntimeFactoryRegistry(
                (
                    RuntimeFactoryBinding(
                        runtime_id="pi.reference",
                        capabilities=(),
                        factory=create_runtime,
                    ),
                )
            )
            stdout = io.StringIO()
            code = main(
                [
                    "run",
                    "--provider",
                    "example-app",
                    "--runtime",
                    "pi.reference",
                    "--run-id",
                    "cli-run",
                    "--input",
                    "SECRET-INPUT",
                    "--assembly",
                    str(value.applications[0].assembly_paths[0]),
                ],
                entry_points=(entry,),
                runtime_factories=registry,
                stdout=stdout,
                stderr=io.StringIO(),
            )

        self.assertEqual(code, 0)
        self.assertEqual(len(factory_calls), 1)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["application_id"], "example.research")
        self.assertEqual(payload["runtime_id"], "pi.reference")
        self.assertEqual(payload["run_id"], "cli-run")
        self.assertNotIn("SECRET-INPUT", stdout.getvalue())

    def test_run_selects_application_without_an_assembly_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            value = provider(Path(temp_dir))
            entry = FakeEntryPoint(name="example-app", factory=lambda: value)
            registry = RuntimeFactoryRegistry(
                (
                    RuntimeFactoryBinding(
                        runtime_id="pi.reference",
                        capabilities=(),
                        factory=lambda context: FixtureRuntime(),
                    ),
                )
            )
            stdout = io.StringIO()
            code = main(
                [
                    "run",
                    "--provider",
                    "example-app",
                    "--runtime",
                    "pi.reference",
                    "--application",
                    "example.research@1.0.0",
                    "--input",
                    "research",
                ],
                entry_points=(entry,),
                runtime_factories=registry,
                stdout=stdout,
                stderr=io.StringIO(),
            )

        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["application_id"], "example.research")

    def test_run_selects_matching_runtime_assembly(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            value = provider(root)
            application = value.applications[0]
            pi_assembly = application.assembly_paths[0]
            claude_assembly = pi_assembly.with_name("claude.json")
            claude_manifest = json.loads(pi_assembly.read_text())
            claude_manifest["runtime_id"] = "claude-code.reference"
            claude_assembly.write_text(json.dumps(claude_manifest))
            compatible = InstalledApplicationProvider(
                protocol=value.protocol,
                provider_id=value.provider_id,
                resource_root=value.resource_root,
                applications=(
                    InstalledApplication(
                        application_id=application.application_id,
                        version=application.version,
                        assembly_paths=(pi_assembly, claude_assembly),
                        catalog_roots=application.catalog_roots,
                        implementations=application.implementations,
                        runtime_ids=("claude-code.reference", "pi.reference"),
                    ),
                ),
            )
            entry = FakeEntryPoint(name="example-app", factory=lambda: compatible)
            contexts = []
            registry = RuntimeFactoryRegistry(
                (
                    RuntimeFactoryBinding(
                        runtime_id="claude-code.reference",
                        capabilities=(),
                        factory=lambda context: contexts.append(context)
                        or ClaudeFixtureRuntime(),
                    ),
                )
            )

            code = main(
                [
                    "run",
                    "--provider",
                    "example-app",
                    "--runtime",
                    "claude-code.reference",
                    "--application",
                    "example.research@1.0.0",
                    "--input",
                    "SECRET-INPUT",
                ],
                entry_points=(entry,),
                runtime_factories=registry,
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )

        self.assertEqual(code, 0)
        self.assertEqual(len(contexts), 1)
        self.assertEqual(contexts[0].assembly_path.name, "claude.json")

    def test_run_rejects_ambiguous_runtime_assemblies_before_factory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            value = provider(root)
            application = value.applications[0]
            pi_assembly = application.assembly_paths[0]
            claude_manifest = json.loads(pi_assembly.read_text())
            claude_manifest["runtime_id"] = "claude-code.reference"
            first_claude = pi_assembly.with_name("claude-first.json")
            second_claude = pi_assembly.with_name("claude-second.json")
            first_claude.write_text(json.dumps(claude_manifest))
            second_claude.write_text(json.dumps(claude_manifest))
            ambiguous = InstalledApplicationProvider(
                protocol=value.protocol,
                provider_id=value.provider_id,
                resource_root=value.resource_root,
                applications=(
                    InstalledApplication(
                        application_id=application.application_id,
                        version=application.version,
                        assembly_paths=(first_claude, second_claude, pi_assembly),
                        catalog_roots=application.catalog_roots,
                        implementations=application.implementations,
                        runtime_ids=("claude-code.reference", "pi.reference"),
                    ),
                ),
            )
            entry = FakeEntryPoint(name="example-app", factory=lambda: ambiguous)
            contexts = []
            registry = RuntimeFactoryRegistry(
                (
                    RuntimeFactoryBinding(
                        runtime_id="claude-code.reference",
                        capabilities=(),
                        factory=lambda context: contexts.append(context)
                        or ClaudeFixtureRuntime(),
                    ),
                )
            )

            code = main(
                [
                    "run",
                    "--provider",
                    "example-app",
                    "--runtime",
                    "claude-code.reference",
                    "--application",
                    "example.research@1.0.0",
                    "--input",
                    "SECRET-INPUT",
                ],
                entry_points=(entry,),
                runtime_factories=registry,
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )

        self.assertEqual(code, 2)
        self.assertEqual(contexts, [])

    def test_bundled_dci_runs_with_claude_fixture(self) -> None:
        contexts = []
        registry = RuntimeFactoryRegistry(
            (
                RuntimeFactoryBinding(
                    runtime_id="claude-code.reference",
                    capabilities=("filesystem.read", "shell"),
                    factory=lambda context: contexts.append(context)
                    or DciClaudeFixtureRuntime(),
                ),
            )
        )
        stdout = io.StringIO()
        stderr = io.StringIO()

        code = main(
            [
                "run",
                "--provider",
                "dci-agent-lite",
                "--runtime",
                "claude-code.reference",
                "--application",
                "dci.research-capability@1.0.0",
                "--input",
                "SECRET-INPUT",
            ],
            entry_points=(
                FakeEntryPoint(name="dci-agent-lite", factory=create_dci_provider),
            ),
            runtime_factories=registry,
            stdout=stdout,
            stderr=stderr,
        )

        self.assertEqual(code, 0, stderr.getvalue())
        self.assertEqual(len(contexts), 1)
        self.assertEqual(
            contexts[0].assembly_path.name,
            "dci-research-capability-claude.json",
        )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["application_id"], "dci.research-capability")
        self.assertEqual(payload["runtime_id"], "claude-code.reference")
        self.assertNotIn("SECRET-INPUT", stdout.getvalue())
        self.assertNotIn("SECRET-INPUT", stderr.getvalue())

    def test_conflicting_or_missing_selection_fails_before_provider_load(self) -> None:
        entry = FakeEntryPoint(name="example-app", factory=lambda: None)
        for selection in (
            [],
            ["--application", "example.research@1.0.0", "--assembly", "/tmp/a"],
        ):
            with self.subTest(selection=selection):
                code = main(
                    [
                        "run",
                        "--provider",
                        "example-app",
                        "--runtime",
                        "pi.reference",
                        *selection,
                    ],
                    entry_points=(entry,),
                    runtime_factories=RuntimeFactoryRegistry(()),
                    stdout=io.StringIO(),
                    stderr=io.StringIO(),
                )
                self.assertEqual(code, 2)
        self.assertEqual(entry.loads, 0)

    def test_controlled_code_requires_complete_operator_config_before_runtime(self) -> None:
        calls = []
        registry = RuntimeFactoryRegistry(
            (
                RuntimeFactoryBinding(
                    runtime_id="pi.reference",
                    capabilities=("filesystem.read", "shell"),
                    factory=lambda context: calls.append(context),
                ),
            )
        )
        code = main(
            [
                "run",
                "--provider",
                "controlled-code",
                "--application",
                "code.quality@1.0.0",
                "--runtime",
                "pi.reference",
            ],
            runtime_factories=registry,
            stdout=io.StringIO(),
            stderr=io.StringIO(),
        )
        self.assertEqual(code, 2)
        self.assertEqual(calls, [])

    def test_dci_rejects_executor_lifecycle_options_before_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            value = provider(Path(temp_dir))
            entry = FakeEntryPoint(name="example-app", factory=lambda: value)
            calls = []
            registry = RuntimeFactoryRegistry(
                (
                    RuntimeFactoryBinding(
                        runtime_id="pi.reference",
                        capabilities=(),
                        factory=lambda context: calls.append(context),
                    ),
                )
            )
            code = main(
                [
                    "run",
                    "--provider",
                    "example-app",
                    "--runtime",
                    "pi.reference",
                    "--application",
                    "example.research@1.0.0",
                    "--executor-binary",
                    "/SECRET-binary",
                ],
                entry_points=(entry,),
                runtime_factories=registry,
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )
        self.assertEqual(code, 2)
        self.assertEqual(calls, [])

    def test_executor_environment_configuration_is_used_when_flags_are_absent(self) -> None:
        with patch.dict(
            os.environ,
            {
                "ASTERION_EXECUTOR_BINARY": "/binary",
                "ASTERION_EXECUTOR_POLICY": "/policy",
                "ASTERION_EXECUTOR_VALIDATION_CONFIG": "/validation",
            },
            clear=False,
        ):
            args = _parser().parse_args(
                [
                    "run",
                    "--provider",
                    "controlled-code",
                    "--runtime",
                    "pi.reference",
                    "--application",
                    "code.quality@1.0.0",
                ]
            )
        self.assertEqual(args.executor_binary, "/binary")
        self.assertEqual(args.executor_policy, "/policy")
        self.assertEqual(args.executor_validation_config, "/validation")

    def test_controlled_code_injects_one_explicit_managed_service(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            binary = root / "executor"
            policy = root / "policy.json"
            validation = root / "validation.json"
            binary.write_text("fixture")
            policy.write_text("{}")
            validation.write_text(
                json.dumps(
                    {
                        "program_id": "check",
                        "argument_prefix": [],
                        "cwd": "workspace",
                        "deadline_ms": 1000,
                        "max_output_bytes": 1024,
                    }
                )
            )
            manager = FixtureManager()
            stderr = io.StringIO()
            registry = RuntimeFactoryRegistry(
                (
                    RuntimeFactoryBinding(
                        runtime_id="pi.reference",
                        capabilities=("filesystem.read", "shell"),
                        factory=lambda context: ControlledFixtureRuntime(),
                    ),
                )
            )
            stdout = io.StringIO()
            code = main(
                [
                    "run",
                    "--provider",
                    "controlled-code",
                    "--application",
                    "code.quality@1.0.0",
                    "--runtime",
                    "pi.reference",
                    "--executor-binary",
                    str(binary),
                    "--executor-policy",
                    str(policy),
                    "--executor-validation-config",
                    str(validation),
                    "--input",
                    "src/example.py",
                ],
                runtime_factories=registry,
                managed_executor_factory=lambda config: configure_manager(manager, config),
                stdout=stdout,
                stderr=stderr,
            )
        self.assertEqual(code, 0, stderr.getvalue())
        self.assertTrue(manager.entered)
        self.assertIsNotNone(manager.config)
        self.assertEqual(json.loads(stdout.getvalue())["application_id"], "code.quality")

    def test_invalid_provider_fails_before_runtime_factory_and_redacts_input(self) -> None:
        calls = []
        registry = RuntimeFactoryRegistry(
            (
                RuntimeFactoryBinding(
                    runtime_id="pi.reference",
                    capabilities=(),
                    factory=lambda context: calls.append(context),
                ),
            )
        )
        stderr = io.StringIO()

        code = main(
            [
                "run",
                "--provider",
                "missing-app",
                "--runtime",
                "pi.reference",
                "--input",
                "SECRET-INPUT",
                "/missing/assembly.json",
            ],
            entry_points=(),
            runtime_factories=registry,
            stdout=io.StringIO(),
            stderr=stderr,
        )

        self.assertEqual(code, 2)
        self.assertEqual(calls, [])
        self.assertNotIn("SECRET-INPUT", stderr.getvalue())

    def test_incomplete_binding_fails_before_runtime_factory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            valid = provider(Path(temp_dir))
            application = valid.applications[0]
            incomplete = InstalledApplicationProvider(
                protocol=valid.protocol,
                provider_id=valid.provider_id,
                resource_root=valid.resource_root,
                applications=(
                    InstalledApplication(
                        application_id=application.application_id,
                        version=application.version,
                        assembly_paths=application.assembly_paths,
                        catalog_roots=application.catalog_roots,
                        implementations=(),
                        runtime_ids=application.runtime_ids,
                    ),
                ),
            )
            entry = FakeEntryPoint(name="example-app", factory=lambda: incomplete)
            calls = []
            registry = RuntimeFactoryRegistry(
                (
                    RuntimeFactoryBinding(
                        runtime_id="pi.reference",
                        capabilities=(),
                        factory=lambda context: calls.append(context),
                    ),
                )
            )
            code = main(
                [
                    "run",
                    "--provider",
                    "example-app",
                    "--runtime",
                    "pi.reference",
                    str(application.assembly_paths[0]),
                ],
                entry_points=(entry,),
                runtime_factories=registry,
                stdin=io.StringIO("input"),
                stdout=io.StringIO(),
                stderr=io.StringIO(),
            )

        self.assertEqual(code, 2)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
