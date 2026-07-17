from __future__ import annotations

import json
import tempfile
import unittest
from collections.abc import AsyncIterator
from pathlib import Path

from asterion.assembly.protocol import resolve_assembly
from asterion.applications.dci_agent_lite.provider import create_provider
from asterion.capabilities.dci_research.complete import (
    DciCompleteAnalysisImplementation,
    DciCompleteAttemptStore,
    DciCompleteBenchmarkImplementation,
    DciCompleteEvaluationImplementation,
    DciCompleteExportImplementation,
    DciCompleteResearchImplementation,
    INPUT_PROTOCOL,
    complete_application_identity,
)
from asterion.dci.run import DciRunResult
from asterion.packages.catalog import PackageRef
from asterion.packages.catalog import discover_packages
from asterion.runner.composed import run_composed_application
from asterion.runtime.host import RunEvent, RunRequest, RuntimeManifest


PROJECT = Path(__file__).resolve().parents[1]
SOURCE = PROJECT / "src/asterion"
MANIFESTS = SOURCE / "capabilities/dci_research/manifests"
ASSEMBLIES = SOURCE / "applications/dci_agent_lite/assemblies"

STAGES = (
    "dci.research",
    "dci.evaluation",
    "dci.benchmark",
    "dci.analysis",
    "dci.export",
)
ORDER = (
    "policy.local-corpus",
    *STAGES,
)
EVENTS = (
    "research.completed",
    "evaluation.completed",
    "benchmark.completed",
    "analysis.completed",
    "export.completed",
)
ARTIFACTS = (
    "application/vnd.dci.research+json",
    "application/vnd.dci.verdict+json",
    "application/vnd.dci.benchmark+json",
    "application/vnd.dci.analysis+json",
    "application/vnd.dci.export+json",
)


def plan(runtime_id: str):
    suffix = "claude" if runtime_id == "claude-code.reference" else "pi"
    assembly = json.loads(
        (ASSEMBLIES / f"dci-complete-application-{suffix}.json").read_text()
    )
    return resolve_assembly(
        assembly,
        catalog=discover_packages((MANIFESTS,)),
        runtime_manifest=RuntimeManifest(
            runtime_id=runtime_id,
            capabilities=("filesystem.read",),
        ).to_mapping(),
    )


class DciCompleteApplicationContractTests(unittest.TestCase):
    def test_pi_and_claude_share_the_exact_five_stage_graph(self) -> None:
        pi = plan("pi.reference")
        claude = plan("claude-code.reference")

        self.assertEqual(pi.application_id, "dci.complete-application")
        self.assertEqual(claude.application_id, pi.application_id)
        self.assertEqual(pi.composition.package_ids, ORDER)
        self.assertEqual(claude.composition.package_ids, ORDER)
        self.assertEqual(
            tuple(
                manifest["package_id"]
                for manifest in pi.package_manifests
                if manifest["kind"] != "policy"
            ),
            STAGES,
        )
        self.assertEqual(pi.package_refs, claude.package_refs)

    def test_every_stage_declares_one_exact_event_and_artifact_edge(self) -> None:
        manifests = {
            manifest["package_id"]: manifest
            for manifest in plan("pi.reference").package_manifests
        }

        for index, package_id in enumerate(STAGES):
            with self.subTest(package_id=package_id):
                manifest = manifests[package_id]
                self.assertEqual(manifest["emits_events"], (EVENTS[index],))
                self.assertEqual(manifest["produces_artifacts"], (ARTIFACTS[index],))
                if index:
                    self.assertEqual(
                        manifest["consumes_events"], (EVENTS[index - 1],)
                    )
                    self.assertEqual(
                        manifest["consumes_artifacts"], (ARTIFACTS[index - 1],)
                    )

    def test_complete_graph_does_not_require_shell_web_or_subagents(self) -> None:
        for runtime_id in ("pi.reference", "claude-code.reference"):
            with self.subTest(runtime_id=runtime_id):
                resolved = plan(runtime_id)
                self.assertEqual(resolved.runtime_capabilities, ("filesystem.read",))
                required = {
                    capability
                    for manifest in resolved.package_manifests
                    for capability in manifest["requires_capabilities"]
                }
                self.assertNotIn("shell", required)
                self.assertFalse(
                    required
                    & {"network", "web.fetch", "web.search", "agent.subagent"}
                )


class DciCompleteApplicationBindingTests(unittest.TestCase):
    def test_installed_provider_binds_every_executable_stage_exactly_once(self) -> None:
        application = next(
            application
            for application in create_provider().applications
            if application.application_id == "dci.complete-application"
        )
        self.assertEqual(application.runtime_ids, ("claude-code.reference", "pi.reference"))
        self.assertEqual(
            tuple(binding[0].package_id for binding in application.implementations),
            STAGES,
        )
        self.assertEqual(
            {path.name for path in application.assembly_paths},
            {
                "dci-complete-application-claude.json",
                "dci-complete-application-pi.json",
            },
        )

    def test_implementation_identity_is_stable_and_digest_shaped(self) -> None:
        identity = complete_application_identity()
        self.assertEqual(len(identity), 64)
        self.assertEqual(identity, complete_application_identity())


class _UnusedPiRuntime:
    manifest = RuntimeManifest("pi.reference", ("filesystem.read",))

    async def run(
        self, request: RunRequest, *, signal: object | None = None
    ) -> AsyncIterator[RunEvent]:
        del request, signal
        raise AssertionError("native Pi binding must not call the generic runtime")
        yield


class _NativeExecutor:
    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.questions: list[str] = []

    def run(self, request) -> DciRunResult:
        self.questions.append(request.question)
        return DciRunResult(
            output_dir=self.output_dir,
            final_text="PRIVATE ANSWER",
            events=(
                RunEvent(request.run_id, 1, "run.started", {"capabilities": []}),
                RunEvent(
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
                ),
                RunEvent(request.run_id, 3, "run.completed", {"status": "completed"}),
            ),
            status="completed",
        )


class DciCompleteApplicationExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_run_evaluates_aggregates_and_exports_without_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = DciCompleteAttemptStore()
            native = _NativeExecutor(Path(directory))
            evaluator_calls = []

            async def evaluator(output_dir, **kwargs):
                evaluator_calls.append((output_dir, kwargs["gold_answer"]))
                return {
                    "is_correct": True,
                    "judge_request_fingerprint": "a" * 64,
                }

            bindings = (
                (PackageRef("dci.research", "1.0.0"), DciCompleteResearchImplementation(store=store, native_executor=native)),
                (PackageRef("dci.evaluation", "1.0.0"), DciCompleteEvaluationImplementation(store=store, evaluator=evaluator, judge_config=lambda: object())),
                (PackageRef("dci.benchmark", "1.0.0"), DciCompleteBenchmarkImplementation()),
                (PackageRef("dci.analysis", "1.0.0"), DciCompleteAnalysisImplementation()),
                (PackageRef("dci.export", "1.0.0"), DciCompleteExportImplementation(store=store)),
            )
            result = await run_composed_application(
                plan("pi.reference"),
                implementations=bindings,
                runtime=_UnusedPiRuntime(),
                run_id="complete-run",
                input_text=json.dumps(
                    {
                        "protocol": INPUT_PROTOCOL,
                        "question": "PRIVATE QUESTION",
                        "gold_answer": "PRIVATE GOLD",
                    }
                ),
                host_services={},
            )

        self.assertEqual(native.questions, ["PRIVATE QUESTION"])
        self.assertEqual(evaluator_calls, [(Path(directory), "PRIVATE GOLD")])
        self.assertEqual(tuple(event["type"] for event in result.events), EVENTS)
        self.assertEqual(tuple(item["media_type"] for item in result.artifacts), ARTIFACTS)
        self.assertEqual(
            {
                item["value"].get("implementation_sha256")
                for item in result.artifacts
            },
            {complete_application_identity()},
        )
        self.assertEqual(result.artifacts[-1]["value"]["total"], 1)
        self.assertNotIn("PRIVATE", repr(result))

if __name__ == "__main__":
    unittest.main()
