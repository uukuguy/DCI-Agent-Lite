from __future__ import annotations

import json
import unittest
from collections.abc import AsyncIterator
from pathlib import Path

from asterion.assembly.protocol import AssemblyPlan, resolve_assembly
from asterion.packages.catalog import discover_packages
from asterion.runner.application import (
    ApplicationRunResult,
    run_application,
)
from asterion.runtime.host import RunEvent, RunRequest, RuntimeManifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ROOTS = (ROOT / "capabilities/dci-research/manifests",)
ASSEMBLY = ROOT / "applications/dci-agent-lite/assemblies/dci-local-research.json"


class FixtureRuntimeClient:
    def __init__(self, runtime_id: str = "pi.reference") -> None:
        self.manifest = RuntimeManifest(
            runtime_id=runtime_id,
            capabilities=("filesystem.read", "shell"),
        )
        self.requests: list[RunRequest] = []
        self.signals: list[object | None] = []

    async def run(
        self,
        request: RunRequest,
        *,
        signal: object | None = None,
    ) -> AsyncIterator[RunEvent]:
        self.requests.append(request)
        self.signals.append(signal)
        yield RunEvent(
            run_id=request.run_id,
            sequence=1,
            type="run.started",
            payload={"capabilities": list(request.requested_capabilities)},
        )
        yield RunEvent(
            run_id=request.run_id,
            sequence=2,
            type="artifact.created",
            payload={
                "artifact": {
                    "artifact_id": "answer",
                    "kind": "answer",
                    "media_type": "text/plain",
                    "uri": "final.txt",
                }
            },
        )
        yield RunEvent(
            run_id=request.run_id,
            sequence=3,
            type="run.completed",
            payload={"status": "completed"},
        )


def resolve_dci_plan(runtime_id: str = "pi.reference") -> AssemblyPlan:
    assembly = json.loads(ASSEMBLY.read_text())
    assembly["runtime_id"] = runtime_id
    return resolve_assembly(
        assembly,
        catalog=discover_packages(MANIFEST_ROOTS),
        runtime_manifest={
            "protocol": "dci.agent-runtime/v1",
            "runtime_id": runtime_id,
            "capabilities": ["filesystem.read", "shell"],
        },
    )


class ApplicationRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_dci_plan_runs_through_one_explicit_runtime_request(self) -> None:
        runtime = FixtureRuntimeClient()

        result = await run_application(
            resolve_dci_plan(),
            runtime=runtime,
            run_id="application-run-1",
            input_text="Investigate the local corpus",
            host_services={},
        )

        self.assertIsInstance(result, ApplicationRunResult)
        self.assertEqual(result.application_id, "dci.local-research")
        self.assertEqual(result.runtime_id, "pi.reference")
        self.assertEqual(result.run_id, "application-run-1")
        self.assertEqual(len(runtime.requests), 1)
        self.assertEqual(runtime.requests[0].input_text, "Investigate the local corpus")
        self.assertEqual(
            runtime.requests[0].requested_capabilities,
            ("filesystem.read", "shell"),
        )
        self.assertEqual([event["type"] for event in result.events], [
            "run.started",
            "artifact.created",
            "run.completed",
        ])
        self.assertEqual(result.artifacts[0]["artifact_id"], "answer")

    async def test_plan_runtime_capabilities_become_portable_request(self) -> None:
        runtime = FixtureRuntimeClient()

        await run_application(
            resolve_dci_plan(),
            runtime=runtime,
            run_id="request-run",
            input_text="Read the corpus",
            host_services={},
        )

        self.assertEqual(runtime.requests[0].run_id, "request-run")
        self.assertEqual(
            runtime.requests[0].requested_capabilities,
            ("filesystem.read", "shell"),
        )

    async def test_explicit_runtime_is_invoked_once(self) -> None:
        runtime = FixtureRuntimeClient()

        await run_application(
            resolve_dci_plan(),
            runtime=runtime,
            run_id="single-run",
            input_text="Read the corpus",
            host_services={},
        )

        self.assertEqual(len(runtime.requests), 1)

    async def test_successful_result_is_deeply_immutable(self) -> None:
        result = await run_application(
            resolve_dci_plan(),
            runtime=FixtureRuntimeClient(),
            run_id="immutable-run",
            input_text="Read the corpus",
            host_services={},
        )

        with self.assertRaises(TypeError):
            result.events[0]["type"] = "changed"
        capabilities = result.events[0]["payload"]["capabilities"]
        self.assertIsInstance(capabilities, tuple)
        with self.assertRaises(TypeError):
            result.artifacts[0]["artifact_id"] = "changed"

    async def test_artifact_events_are_projected_without_provider_output(self) -> None:
        result = await run_application(
            resolve_dci_plan(),
            runtime=FixtureRuntimeClient(),
            run_id="artifact-run",
            input_text="Read the corpus",
            host_services={},
        )

        self.assertEqual(
            dict(result.artifacts[0]),
            {
                "artifact_id": "answer",
                "kind": "answer",
                "media_type": "text/plain",
                "uri": "final.txt",
            },
        )

    def test_runner_has_no_adapter_or_process_imports(self) -> None:
        source = (ROOT / "src/asterion/runner/application.py").read_text()

        self.assertNotIn("asterion.adapters", source)
        self.assertNotIn("asterion.runtimes", source)
        self.assertNotIn("subprocess", source)


if __name__ == "__main__":
    unittest.main()
