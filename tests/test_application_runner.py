from __future__ import annotations

import json
import unittest
from collections.abc import AsyncIterator
from pathlib import Path

from asterion.assembly.protocol import AssemblyPlan, resolve_assembly
from asterion.packages.catalog import discover_packages
from asterion.runner.application import (
    ApplicationRunError,
    ApplicationRunResult,
    run_application,
)
from asterion.runtime.host import RunEvent, RunRequest, RuntimeManifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ROOTS = (
    ROOT / "capabilities/dci-research/manifests",
    ROOT / "capabilities/controlled-code/manifests",
)
ASSEMBLY = ROOT / "applications/dci-agent-lite/assemblies/dci-local-research.json"
CONTROLLED_ASSEMBLY = (
    ROOT / "applications/dci-agent-lite/assemblies/controlled-code-validation.json"
)
GUIDE = ROOT / "docs/architecture/application-runner.md"


class FixtureRuntimeClient:
    def __init__(
        self,
        runtime_id: str = "pi.reference",
        capabilities: tuple[str, ...] = ("filesystem.read", "shell"),
    ) -> None:
        self.manifest = RuntimeManifest(
            runtime_id=runtime_id,
            capabilities=capabilities,
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


class MutableSignal:
    def __init__(self, cancelled: bool = False) -> None:
        self.cancelled = cancelled


class CancellingRuntimeClient(FixtureRuntimeClient):
    async def run(
        self,
        request: RunRequest,
        *,
        signal: object | None = None,
    ) -> AsyncIterator[RunEvent]:
        self.requests.append(request)
        self.signals.append(signal)
        assert isinstance(signal, MutableSignal)
        yield RunEvent(
            run_id=request.run_id,
            sequence=1,
            type="run.started",
            payload={"capabilities": list(request.requested_capabilities)},
        )
        signal.cancelled = True
        yield RunEvent(
            run_id=request.run_id,
            sequence=2,
            type="run.completed",
            payload={"status": "cancelled"},
        )


class FailingRuntimeClient(FixtureRuntimeClient):
    async def run(
        self,
        request: RunRequest,
        *,
        signal: object | None = None,
    ) -> AsyncIterator[RunEvent]:
        del request, signal
        if False:
            yield RunEvent("", 0, "", {})
        raise RuntimeError("SECRET-PROVIDER-PAYLOAD")


class IncompleteRuntimeClient(FixtureRuntimeClient):
    async def run(
        self,
        request: RunRequest,
        *,
        signal: object | None = None,
    ) -> AsyncIterator[RunEvent]:
        del signal
        yield RunEvent(
            run_id=request.run_id,
            sequence=1,
            type="run.started",
            payload={"capabilities": ["SECRET-RAW-TOOL-OUTPUT"]},
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


def resolve_controlled_plan() -> AssemblyPlan:
    assembly = json.loads(CONTROLLED_ASSEMBLY.read_text())
    return resolve_assembly(
        assembly,
        catalog=discover_packages(MANIFEST_ROOTS),
        runtime_manifest={
            "protocol": "dci.agent-runtime/v1",
            "runtime_id": "pi.reference",
            "capabilities": ["filesystem.read"],
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

    async def test_pi_and_claude_fixture_runtimes_are_protocol_equivalent(self) -> None:
        pi = await run_application(
            resolve_dci_plan("pi.reference"),
            runtime=FixtureRuntimeClient("pi.reference"),
            run_id="parity-run",
            input_text="Read the corpus",
            host_services={},
        )
        claude = await run_application(
            resolve_dci_plan("claude-code.reference"),
            runtime=FixtureRuntimeClient("claude-code.reference"),
            run_id="parity-run",
            input_text="Read the corpus",
            host_services={},
        )

        self.assertEqual(pi.events, claude.events)
        self.assertEqual(pi.artifacts, claude.artifacts)

    async def test_pre_run_and_in_run_cancellation_are_safe(self) -> None:
        pre_cancelled_runtime = FixtureRuntimeClient()
        with self.assertRaises(ApplicationRunError):
            await run_application(
                resolve_dci_plan(),
                runtime=pre_cancelled_runtime,
                run_id="pre-cancelled",
                input_text="Read the corpus",
                host_services={},
                signal=MutableSignal(cancelled=True),
            )
        self.assertEqual(pre_cancelled_runtime.requests, [])

        signal = MutableSignal()
        runtime = CancellingRuntimeClient()
        result = await run_application(
            resolve_dci_plan(),
            runtime=runtime,
            run_id="cancelled-during-run",
            input_text="Read the corpus",
            host_services={},
            signal=signal,
        )
        self.assertIs(runtime.signals[0], signal)
        self.assertTrue(signal.cancelled)
        self.assertEqual(result.events[-1]["payload"]["status"], "cancelled")

    async def test_runtime_and_service_mismatches_fail_before_invocation(self) -> None:
        mismatch = FixtureRuntimeClient("other.runtime")
        with self.assertRaises(ApplicationRunError):
            await run_application(
                resolve_dci_plan(),
                runtime=mismatch,
                run_id="runtime-mismatch",
                input_text="Read the corpus",
                host_services={},
            )
        self.assertEqual(mismatch.requests, [])

        missing_capability = FixtureRuntimeClient(capabilities=("filesystem.read",))
        with self.assertRaises(ApplicationRunError):
            await run_application(
                resolve_dci_plan(),
                runtime=missing_capability,
                run_id="capability-mismatch",
                input_text="Read the corpus",
                host_services={},
            )
        self.assertEqual(missing_capability.requests, [])

        missing_service = FixtureRuntimeClient(capabilities=("filesystem.read",))
        with self.assertRaises(ApplicationRunError):
            await run_application(
                resolve_controlled_plan(),
                runtime=missing_service,
                run_id="service-mismatch",
                input_text="Check the source",
                host_services={},
            )
        self.assertEqual(missing_service.requests, [])

    async def test_malformed_streams_and_runtime_errors_are_redacted(self) -> None:
        for runtime in (FailingRuntimeClient(), IncompleteRuntimeClient()):
            with self.subTest(runtime=type(runtime).__name__), self.assertRaises(
                ApplicationRunError
            ) as raised:
                await run_application(
                    resolve_dci_plan(),
                    runtime=runtime,
                    run_id="safe-error",
                    input_text="SECRET-APPLICATION-INPUT",
                    host_services={},
                )
            message = str(raised.exception)
            self.assertNotIn("SECRET-APPLICATION-INPUT", message)
            self.assertNotIn("SECRET-PROVIDER-PAYLOAD", message)
            self.assertNotIn("SECRET-RAW-TOOL-OUTPUT", message)


class ApplicationRunnerDocumentationTests(unittest.TestCase):
    def guide(self) -> str:
        return GUIDE.read_text()

    def test_guide_documents_the_explicit_plan_runtime_and_service_boundary(self) -> None:
        guide = self.guide()
        self.assertIn("AssemblyPlan", guide)
        self.assertIn("AgentRuntimeClient", guide)
        self.assertIn("explicit host services", guide)
        self.assertIn("CancellationSignal", guide)

    def test_guide_documents_immutable_results_and_safe_failures(self) -> None:
        guide = self.guide()
        self.assertIn("immutable normalized events and artifacts", guide)
        self.assertIn("fail closed", guide)
        self.assertIn("does not authorize", guide)

    def test_runner_boundary_excludes_control_plane_and_process_ownership(self) -> None:
        source = (ROOT / "src/asterion/runner/application.py").read_text()
        typescript_sources = "\n".join(
            path.read_text()
            for path in (ROOT / "packages/typescript/asterion-runtime/src").glob("*.ts")
        )

        self.assertNotIn("subprocess", source)
        self.assertNotIn("scheduler", source)
        self.assertNotIn("service registry", source)
        self.assertNotIn("runApplication", typescript_sources)

    def test_runner_is_python_owned_without_dci_or_typescript_duplicate(self) -> None:
        self.assertTrue((ROOT / "src/asterion/runner/application.py").is_file())
        self.assertFalse((ROOT / "src/dci/framework/runner.py").exists())
        typescript_sources = "\n".join(
            path.read_text()
            for path in (ROOT / "packages/typescript/asterion-runtime/src").glob("*.ts")
        )
        self.assertNotIn("runApplication", typescript_sources)


if __name__ == "__main__":
    unittest.main()
