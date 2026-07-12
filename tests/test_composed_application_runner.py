from __future__ import annotations

import json
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
MANIFEST_ROOT = ROOT / "capabilities/dci-research/manifests"
ASSEMBLY = ROOT / "applications/dci-agent-lite/assemblies/dci-local-research.json"


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
