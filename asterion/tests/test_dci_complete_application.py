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
from asterion.dci.dual_runtime_verification import (
    DciDualRuntimeVerificationError,
    audit_restricted_claude_application,
    audit_restricted_pi_application,
)
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
        self.requests = []

    def run(self, request) -> DciRunResult:
        self.requests.append(request)
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


class _ClaudeRuntime:
    manifest = RuntimeManifest(
        "claude-code.reference",
        ("claude.tool.glob", "claude.tool.grep", "filesystem.read"),
    )

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = output_dir
        self.requests = []

    async def run(self, request: RunRequest, *, signal=None):
        del signal
        self.requests.append(request)
        self.output_dir.mkdir(mode=0o700)
        final_path = self.output_dir / "final.txt"
        final_path.write_text("PRIVATE ANSWER\n")
        final_path.chmod(0o600)
        yield RunEvent(request.run_id, 1, "run.started", {"capabilities": list(request.requested_capabilities)})
        yield RunEvent(request.run_id, 2, "artifact.created", {"artifact": {"artifact_id": "answer", "kind": "answer", "media_type": "text/plain", "uri": "final.txt"}})
        yield RunEvent(request.run_id, 3, "run.completed", {"status": "completed"})

    def completed_run_dir(self, run_id: str) -> Path:
        del run_id
        return self.output_dir


class DciCompleteApplicationExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_claude_run_is_judged_and_exports_without_private_bodies(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = DciCompleteAttemptStore()
            runtime = _ClaudeRuntime(Path(directory) / "claude-run")
            judge_calls = []

            async def answer_evaluator(**kwargs):
                judge_calls.append(kwargs)
                return {"is_correct": True, "judge_request_fingerprint": "b" * 64}

            bindings = (
                (PackageRef("dci.research", "1.0.0"), DciCompleteResearchImplementation(store=store, native_executor=_NativeExecutor(Path(directory) / "unused"))),
                (PackageRef("dci.evaluation", "1.0.0"), DciCompleteEvaluationImplementation(store=store, answer_evaluator=answer_evaluator, judge_config=lambda: object())),
                (PackageRef("dci.benchmark", "1.0.0"), DciCompleteBenchmarkImplementation()),
                (PackageRef("dci.analysis", "1.0.0"), DciCompleteAnalysisImplementation()),
                (PackageRef("dci.export", "1.0.0"), DciCompleteExportImplementation(store=store)),
            )
            result = await run_composed_application(
                plan("claude-code.reference"),
                implementations=bindings,
                runtime=runtime,
                run_id="claude-complete",
                input_text=json.dumps({"protocol": INPUT_PROTOCOL, "question": "PRIVATE QUESTION", "gold_answer": "PRIVATE GOLD"}),
                host_services={},
            )

        self.assertEqual(runtime.requests[0].requested_capabilities, ("claude.tool.glob", "claude.tool.grep", "filesystem.read"))
        self.assertEqual(judge_calls[0]["predicted_answer"], "PRIVATE ANSWER")
        self.assertEqual(tuple(event["type"] for event in result.events), EVENTS)
        self.assertNotIn("PRIVATE", repr(result))

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
        self.assertEqual(native.requests[0].tools, "read,grep")
        self.assertEqual(native.requests[0].max_turns, 4)
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


class DciRestrictedPiEvidenceTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        run = root / "run"
        corpus = root / "corpus"
        (run / "protocol").mkdir(parents=True)
        corpus.mkdir()
        documents = {
            run / "state.json": {"status": "completed", "tools": "read,grep", "max_turns": 4},
            run / "protocol/attempt-0001.request.json": {"requested_capabilities": ["filesystem.read", "pi.tool.grep"]},
            run / "eval_result.json": {"is_correct": True, "judge_request_fingerprint": "a" * 64},
        }
        for path, value in documents.items():
            path.write_text(json.dumps(value))
            path.chmod(0o600)
        events = (
            {"type": "tool.call", "payload": {"name": "read", "arguments": {"path": "missing.txt"}}},
            {"type": "tool.call", "payload": {"name": "read", "arguments": {"path": "document.txt"}}},
            {"type": "tool.call", "payload": {"name": "grep", "arguments": {"path": "."}}},
            {"type": "tool.result", "payload": {"is_error": True}},
            {"type": "tool.result", "payload": {"is_error": True}},
        )
        event_path = run / "protocol/attempt-0001.events.jsonl"
        event_path.write_text("".join(json.dumps(event) + "\n" for event in events))
        event_path.chmod(0o600)
        return run, corpus

    def test_bounded_private_evidence_is_body_free_and_corpus_contained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run, corpus = self._fixture(Path(directory))
            report = audit_restricted_pi_application(run_dir=run, corpus_dir=corpus)

        self.assertEqual(report["tools"], {"read": 2, "grep": 1})
        self.assertEqual(report["tool_error_count"], 2)
        self.assertTrue(report["corpus_contained"])
        self.assertNotIn("cobalt lantern", repr(report))

    def test_absolute_outside_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run, corpus = self._fixture(Path(directory))
            path = run / "protocol/attempt-0001.events.jsonl"
            events = json.loads(path.read_text().splitlines()[0])
            events["payload"]["arguments"]["path"] = "/outside/answer.txt"
            path.write_text(json.dumps(events) + "\n")
            path.chmod(0o600)
            with self.assertRaises(DciDualRuntimeVerificationError):
                audit_restricted_pi_application(run_dir=run, corpus_dir=corpus)

    def test_tracked_pi_evidence_is_body_free_and_bounded(self) -> None:
        record = json.loads(
            (
                PROJECT.parent
                / "docs/status/climb/provider-evidence/af-330-h-003.json"
            ).read_text()
        )
        self.assertEqual(record["agent_operations"], 1)
        self.assertEqual(record["judge_operations"], 1)
        self.assertEqual(record["tools"], {"grep": 1, "read": 2})
        self.assertTrue(record["corpus_contained"])
        self.assertFalse(record["full_dataset"])
        self.assertNotIn("cobalt lantern", repr(record))


class DciRestrictedClaudeEvidenceTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        run = root / "run"
        corpus = root / "corpus"
        run.mkdir(mode=0o700)
        corpus.mkdir()
        documents = {
            "request.json": {"requested_capabilities": ["filesystem.read", "claude.tool.grep", "claude.tool.glob"]},
            "runtime-policy.json": {
                "tools": ["Read", "Grep", "Glob"], "allowed_tools": ["Read", "Grep", "Glob"],
                "max_turns": 4, "permission_mode": "dontAsk", "strict_mcp": True,
                "mcp_servers": {}, "safe_mode": True, "no_session_persistence": True,
                "settings": {"sandbox": {"enabled": True, "failIfUnavailable": True, "allowUnsandboxedCommands": False}},
            },
            "eval_result.json": {"is_correct": True, "judge_request_fingerprint": "c" * 64},
        }
        for name, value in documents.items():
            path = run / name
            path.write_text(json.dumps(value))
            path.chmod(0o600)
        events = (
            {"type": "run.started", "payload": {"capabilities": ["claude.tool.glob", "claude.tool.grep", "filesystem.read"]}},
            {"type": "tool.call", "payload": {"name": "Grep", "arguments": {"path": "."}}},
            {"type": "run.completed", "payload": {"status": "completed"}},
        )
        for name, value in {
            "events.jsonl": "".join(json.dumps(event) + "\n" for event in events),
            "raw-events.jsonl": "private raw stream\n",
            "final.txt": "cobalt lantern\n",
        }.items():
            path = run / name
            path.write_text(value)
            path.chmod(0o600)
        return run, corpus

    def test_private_evidence_is_body_free_and_corpus_contained(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run, corpus = self._fixture(Path(directory))
            report = audit_restricted_claude_application(run_dir=run, corpus_dir=corpus)
        self.assertEqual(report["tools"], {"Read": 0, "Grep": 1, "Glob": 0})
        self.assertNotIn("cobalt lantern", repr(report))

    def test_outside_path_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            run, corpus = self._fixture(Path(directory))
            path = run / "events.jsonl"
            events = [json.loads(line) for line in path.read_text().splitlines()]
            events[1]["payload"]["arguments"]["path"] = "/outside"
            path.write_text("".join(json.dumps(event) + "\n" for event in events))
            path.chmod(0o600)
            with self.assertRaises(DciDualRuntimeVerificationError):
                audit_restricted_claude_application(run_dir=run, corpus_dir=corpus)

    def test_tracked_claude_evidence_is_body_free_and_bounded(self) -> None:
        record = json.loads(
            (
                PROJECT.parent
                / "docs/status/climb/provider-evidence/af-330-h-004.json"
            ).read_text()
        )
        self.assertEqual(record["agent_operations"], 1)
        self.assertEqual(record["judge_operations"], 1)
        self.assertEqual(record["tools"], {"Glob": 0, "Grep": 1, "Read": 0})
        self.assertTrue(record["corpus_contained"])
        self.assertEqual(record["web_calls"], 0)
        self.assertEqual(record["subagent_calls"], 0)
        self.assertFalse(record["full_dataset"])
        self.assertNotIn("silver compass", repr(record))
        self.assertNotIn("8426", repr(record))

if __name__ == "__main__":
    unittest.main()
