from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from collections.abc import AsyncIterator, Mapping
from pathlib import Path

from asterion.assembly.protocol import resolve_assembly
from asterion.packages.catalog import PackageRef, discover_packages
from asterion.packages.execution import PackageExecutionResult, PackageInvocation
from asterion.runner.application import ApplicationRunError
from asterion.runner.composed import run_composed_application
from asterion.runtime.host import RunEvent, RunRequest, RuntimeManifest


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_ROOT = ROOT / "asterion/src/asterion/capabilities/dci_research/manifests"
ASSEMBLY = ROOT / "asterion/src/asterion/applications/dci_agent_lite/assemblies/dci-local-research.json"
EXECUTABLE_ASSEMBLY = (
    ROOT / "asterion/src/asterion/applications/dci_agent_lite/assemblies/dci-research-capability.json"
)
HOST_MODULE = ROOT / "asterion/examples/applications/dci_research.py"
GUIDE = ROOT / "asterion/docs/architecture/capability-execution.md"


class FixtureRuntime:
    def __init__(self, runtime_id: str = "pi.reference") -> None:
        self.manifest = RuntimeManifest(
            runtime_id=runtime_id,
            capabilities=("filesystem.read", "shell"),
        )
        self.requests: list[RunRequest] = []

    async def run(
        self,
        request: RunRequest,
        *,
        signal: object | None = None,
    ) -> AsyncIterator[RunEvent]:
        del signal
        self.requests.append(request)
        if False:
            yield RunEvent("", 0, "", {})


class ResearchFixtureRuntime(FixtureRuntime):
    async def run(
        self,
        request: RunRequest,
        *,
        signal: object | None = None,
    ) -> AsyncIterator[RunEvent]:
        del signal
        self.requests.append(request)
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
                    "uri": "final.txt",
                }
            },
        )
        yield RunEvent(request.run_id, 3, "run.completed", {"status": "completed"})


class MutableSignal:
    def __init__(self, cancelled: bool = False) -> None:
        self.cancelled = cancelled


class RecordingImplementation:
    def __init__(
        self,
        package_id: str,
        *,
        event_type: str,
        artifact_media_type: str | None = None,
        fail: bool = False,
        cancel: MutableSignal | None = None,
    ) -> None:
        self.package_id = package_id
        self.event_type = event_type
        self.artifact_media_type = artifact_media_type
        self.fail = fail
        self.cancel = cancel
        self.calls: list[PackageInvocation] = []

    async def execute(
        self, invocation: PackageInvocation
    ) -> PackageExecutionResult:
        self.calls.append(invocation)
        if self.fail:
            raise RuntimeError("SECRET-IMPLEMENTATION-PAYLOAD")
        if self.cancel is not None:
            self.cancel.cancelled = True
        artifacts: tuple[Mapping[str, object], ...] = ()
        if self.artifact_media_type is not None:
            artifacts = ({
                "artifact_id": f"{self.package_id}-result",
                "media_type": self.artifact_media_type,
                "value": {"package_id": self.package_id},
            },)
        return PackageExecutionResult(
            events=({"type": self.event_type, "payload": {"status": "completed"}},),
            artifacts=artifacts,
        )


def resolve_plan(runtime_id: str = "pi.reference"):
    assembly = json.loads(ASSEMBLY.read_text())
    assembly["runtime_id"] = runtime_id
    runtime = FixtureRuntime(runtime_id)
    plan = resolve_assembly(
        assembly,
        catalog=discover_packages((MANIFEST_ROOT,)),
        runtime_manifest=runtime.manifest.to_mapping(),
    )
    return plan, runtime


def implementations(*, signal: MutableSignal | None = None):
    research = RecordingImplementation(
        "dci.research",
        event_type="research.completed",
        artifact_media_type="application/vnd.dci.research+json",
        cancel=signal,
    )
    evaluation = RecordingImplementation(
        "dci.evaluation",
        event_type="evaluation.completed",
        artifact_media_type="application/vnd.dci.verdict+json",
    )
    observability = RecordingImplementation(
        "protocol.observability",
        event_type="audit.package-observed",
    )
    return (
        (
            (PackageRef("dci.research", "1.0.0"), research),
            (PackageRef("dci.evaluation", "1.0.0"), evaluation),
            (PackageRef("protocol.observability", "1.0.0"), observability),
        ),
        (research, evaluation, observability),
    )


class ComposedApplicationRunnerTests(unittest.IsolatedAsyncioTestCase):
    async def test_executes_implementations_in_resolved_order(self) -> None:
        plan, runtime = resolve_plan()
        bindings, (research, evaluation, observability) = implementations()

        result = await run_composed_application(
            plan,
            implementations=bindings,
            runtime=runtime,
            run_id="composed-run",
            input_text="Read the corpus",
            host_services={},
        )

        self.assertEqual(result.application_id, "dci.local-research")
        self.assertEqual(
            tuple(event["type"] for event in result.events),
            ("research.completed", "evaluation.completed", "audit.package-observed"),
        )
        self.assertEqual(len(research.calls), 1)
        self.assertEqual(len(evaluation.calls), 1)
        self.assertEqual(len(observability.calls), 1)
        self.assertEqual(
            tuple(
                artifact["media_type"]
                for artifact in evaluation.calls[0].upstream_artifacts
            ),
            ("application/vnd.dci.research+json",),
        )

    async def test_binding_preflight_fails_before_any_implementation_call(self) -> None:
        plan, runtime = resolve_plan()
        bindings, (research, evaluation, observability) = implementations()

        with self.assertRaises(ApplicationRunError):
            await run_composed_application(
                plan,
                implementations=bindings[:-1],
                runtime=runtime,
                run_id="missing-binding",
                input_text="SECRET-APPLICATION-INPUT",
                host_services={},
            )

        self.assertEqual(research.calls, [])
        self.assertEqual(evaluation.calls, [])
        self.assertEqual(observability.calls, [])


class ExplicitDciApplicationHostTests(unittest.IsolatedAsyncioTestCase):
    def load_host(self):
        spec = importlib.util.spec_from_file_location("dci_research_host", HOST_MODULE)
        if spec is None or spec.loader is None:
            raise RuntimeError("unable to load DCI research host")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    async def test_checked_in_host_binds_the_independent_dci_implementation(self) -> None:
        host = self.load_host()
        runtime = ResearchFixtureRuntime()

        result = await host.run_dci_research_application(
            assembly_path=EXECUTABLE_ASSEMBLY,
            catalog_roots=(MANIFEST_ROOT,),
            runtime=runtime,
            run_id="host-run",
            input_text="Read the corpus",
        )

        self.assertEqual(result.application_id, "dci.research-capability")
        self.assertEqual(len(runtime.requests), 1)
        self.assertEqual(
            result.artifacts[0]["media_type"],
            "application/vnd.dci.research+json",
        )

    async def test_same_dci_implementation_is_reusable_with_extra_policy(self) -> None:
        host = self.load_host()
        assembly = json.loads(EXECUTABLE_ASSEMBLY.read_text())
        assembly["application_id"] = "dci.research-with-extra-policy"
        assembly["packages"].append(
            {"package_id": "policy.extra-audit", "version": "1.0.0"}
        )
        assembly["packages"] = sorted(
            assembly["packages"], key=lambda item: (item["package_id"], item["version"])
        )
        extra_policy = {
            "protocol": "dci.package/v1",
            "package_id": "policy.extra-audit",
            "version": "1.0.0",
            "kind": "policy",
            "provides_capabilities": [],
            "requires_capabilities": [],
            "requires_policies": [],
            "emits_events": [],
            "consumes_events": [],
            "produces_artifacts": [],
            "consumes_artifacts": [],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            assembly_path = root / "assembly.json"
            policy_root = root / "manifests"
            policy_root.mkdir()
            assembly_path.write_text(json.dumps(assembly))
            (policy_root / "extra-policy.json").write_text(json.dumps(extra_policy))
            result = await host.run_dci_research_application(
                assembly_path=assembly_path,
                catalog_roots=(MANIFEST_ROOT, policy_root),
                runtime=ResearchFixtureRuntime(),
                run_id="reused-host-run",
                input_text="Read the corpus",
            )

        self.assertEqual(result.application_id, "dci.research-with-extra-policy")


class ComposedApplicationRunnerFailureTests(unittest.IsolatedAsyncioTestCase):

    async def test_failure_stops_later_packages_and_redacts_content(self) -> None:
        plan, runtime = resolve_plan()
        bindings, (_, evaluation, observability) = implementations()
        failing = RecordingImplementation(
            "dci.research",
            event_type="research.completed",
            fail=True,
        )
        bindings = ((bindings[0][0], failing), *bindings[1:])

        with self.assertRaises(ApplicationRunError) as raised:
            await run_composed_application(
                plan,
                implementations=bindings,
                runtime=runtime,
                run_id="failed-package",
                input_text="SECRET-APPLICATION-INPUT",
                host_services={},
            )

        self.assertEqual(len(failing.calls), 1)
        self.assertEqual(evaluation.calls, [])
        self.assertEqual(observability.calls, [])
        self.assertNotIn("SECRET", str(raised.exception))


class CapabilityExecutionDocumentationTests(unittest.TestCase):
    def guide(self) -> str:
        return GUIDE.read_text()

    def test_guide_defines_package_and_application_ownership(self) -> None:
        guide = self.guide()
        self.assertIn("reusable executable unit", guide)
        self.assertIn("executable composition boundary", guide)
        self.assertIn("PackageRef", guide)
        self.assertIn("run_composed_application", guide)

    def test_guide_documents_security_baseline_and_af120_boundary(self) -> None:
        guide = self.guide()
        self.assertIn("src/dci/benchmark/", guide)
        self.assertIn("exact implementation", guide)
        self.assertIn("sequential", guide)
        self.assertIn("AF-120", guide)
        self.assertIn("asterion run", guide)


class ComposedApplicationRunnerCancellationTests(unittest.IsolatedAsyncioTestCase):

    async def test_cancellation_stops_later_packages(self) -> None:
        plan, runtime = resolve_plan()
        signal = MutableSignal()
        bindings, (research, evaluation, observability) = implementations(signal=signal)

        with self.assertRaises(ApplicationRunError):
            await run_composed_application(
                plan,
                implementations=bindings,
                runtime=runtime,
                run_id="cancelled-package",
                input_text="Read the corpus",
                host_services={},
                signal=signal,
            )

        self.assertEqual(len(research.calls), 1)
        self.assertEqual(evaluation.calls, [])
        self.assertEqual(observability.calls, [])

    async def test_runtime_mismatch_fails_before_binding_or_execution(self) -> None:
        plan, _ = resolve_plan()
        bindings, (research, evaluation, observability) = implementations()

        with self.assertRaises(ApplicationRunError):
            await run_composed_application(
                plan,
                implementations=bindings,
                runtime=FixtureRuntime("other.runtime"),
                run_id="runtime-mismatch",
                input_text="Read the corpus",
                host_services={},
            )

        self.assertEqual(research.calls, [])
        self.assertEqual(evaluation.calls, [])
        self.assertEqual(observability.calls, [])


if __name__ == "__main__":
    unittest.main()
