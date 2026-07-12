from __future__ import annotations

import io
import json
import tempfile
import unittest
from collections.abc import AsyncIterator
from pathlib import Path

from asterion.cli import main
from asterion.applications.provider import InstalledApplication, InstalledApplicationProvider
from asterion.runtime.factory import RuntimeFactoryBinding, RuntimeFactoryRegistry
from asterion.runtime.host import RunEvent, RunRequest, RuntimeManifest
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
