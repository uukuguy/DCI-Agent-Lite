from __future__ import annotations

import json
import unittest
from pathlib import Path

from dci.framework.package_protocol import PackageProtocolError, validate_package_manifest
from dci.framework.packages import PackageCompositionError, compose_packages
from dci.framework.adapters.claude_code import map_claude_capabilities
from dci.framework.adapters.pi import map_pi_capabilities


REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests/fixtures/packages/v1"
MANIFEST_DIRS = (
    REPO_ROOT / "packages/python/asterion-core/src/asterion/capabilities/dci_research/manifests",
    REPO_ROOT / "capabilities/controlled-code/manifests",
)


def manifest_path(name: str) -> Path:
    return next(path / name for path in MANIFEST_DIRS if (path / name).is_file())
PACKAGE_GUIDE = REPO_ROOT / "docs/architecture/composable-packages.md"
CONTROLLED_CODE_GUIDE = (
    REPO_ROOT / "docs/architecture/controlled-code-validation-packages.md"
)


class PackageManifestTests(unittest.TestCase):
    def load(self, name: str) -> dict[str, object]:
        return json.loads((FIXTURE_DIR / name).read_text())

    def test_valid_shared_manifest_fixture_conforms(self) -> None:
        validate_package_manifest(self.load("valid-capability.json"))

    def test_all_package_kinds_are_portable(self) -> None:
        manifest = self.load("valid-capability.json")

        for kind in (
            "capability",
            "workflow",
            "policy",
            "memory",
            "observability",
            "evaluation",
        ):
            with self.subTest(kind=kind):
                validate_package_manifest({**manifest, "kind": kind})

    def test_invalid_shared_manifest_fixtures_are_rejected(self) -> None:
        names = (
            "invalid-unknown-field.json",
            "invalid-duplicate-edge.json",
            "invalid-package-id.json",
            "invalid-forbidden-command.json",
        )

        for name in names:
            with self.subTest(name=name), self.assertRaises(PackageProtocolError):
                validate_package_manifest(self.load(name))

    def test_edge_arrays_must_be_sorted_and_unique(self) -> None:
        manifest = self.load("valid-capability.json")

        with self.assertRaises(PackageProtocolError):
            validate_package_manifest(
                {**manifest, "provides_capabilities": ["z.last", "a.first"]}
            )


class PackageCompositionTests(unittest.TestCase):
    def package(
        self,
        package_id: str,
        *,
        kind: str = "capability",
        provides: tuple[str, ...] = (),
        requires: tuple[str, ...] = (),
        policies: tuple[str, ...] = (),
        emits: tuple[str, ...] = (),
        consumes_events: tuple[str, ...] = (),
        produces: tuple[str, ...] = (),
        consumes_artifacts: tuple[str, ...] = (),
    ) -> dict[str, object]:
        return {
            "protocol": "dci.package/v1",
            "package_id": package_id,
            "version": "1.0.0",
            "kind": kind,
            "provides_capabilities": sorted(provides),
            "requires_capabilities": sorted(requires),
            "requires_policies": sorted(policies),
            "emits_events": sorted(emits),
            "consumes_events": sorted(consumes_events),
            "produces_artifacts": sorted(produces),
            "consumes_artifacts": sorted(consumes_artifacts),
        }

    def test_composition_order_is_stable_under_permuted_input(self) -> None:
        source = self.package("source", provides=("data.read",))
        consumer = self.package("consumer", requires=("data.read",))

        first = compose_packages([consumer, source])
        second = compose_packages([source, consumer])

        self.assertEqual(first.package_ids, ("source", "consumer"))
        self.assertEqual(first, second)
        self.assertEqual(first.provided_capabilities, ("data.read",))

    def test_duplicate_ids_and_ambiguous_capability_providers_are_rejected(self) -> None:
        one = self.package("one", provides=("data.read",))
        duplicate = self.package("one")
        two = self.package("two", provides=("data.read",))

        with self.assertRaises(PackageCompositionError):
            compose_packages([one, duplicate])
        with self.assertRaises(PackageCompositionError):
            compose_packages([one, two])

    def test_missing_capability_policy_event_and_artifact_edges_are_rejected(self) -> None:
        consumers = (
            self.package("capability-consumer", requires=("missing.capability",)),
            self.package("policy-consumer", policies=("policy.missing",)),
            self.package("event-consumer", consumes_events=("event.missing",)),
            self.package(
                "artifact-consumer",
                consumes_artifacts=("application/missing",),
            ),
        )

        for consumer in consumers:
            with self.subTest(package=consumer["package_id"]), self.assertRaises(
                PackageCompositionError
            ):
                compose_packages([consumer])

    def test_host_edges_satisfy_external_requirements(self) -> None:
        consumer = self.package(
            "consumer",
            requires=("filesystem.read",),
            policies=("policy.local",),
            consumes_events=("run.started",),
            consumes_artifacts=("text/plain",),
        )

        composition = compose_packages(
            [consumer],
            host_capabilities={"filesystem.read"},
            host_policies={"policy.local"},
            host_events={"run.started"},
            host_artifacts={"text/plain"},
        )

        self.assertEqual(composition.package_ids, ("consumer",))

    def test_dependency_cycles_are_rejected(self) -> None:
        first = self.package(
            "first", provides=("first.output",), requires=("second.output",)
        )
        second = self.package(
            "second", provides=("second.output",), requires=("first.output",)
        )

        with self.assertRaises(PackageCompositionError):
            compose_packages([first, second])


class DciReferencePackageTests(unittest.TestCase):
    def manifests(self) -> list[dict[str, object]]:
        names = (
            "dci-research.json",
            "local-corpus-policy.json",
            "protocol-observability.json",
            "dci-evaluation.json",
        )
        return [json.loads(manifest_path(name).read_text()) for name in names]

    def compose_for(self, capabilities: set[str]):
        return compose_packages(
            self.manifests(),
            host_capabilities=capabilities,
            host_events={
                "artifact.created",
                "run.completed",
                "run.started",
                "tool.result",
            },
            host_artifacts={"text/plain"},
        )

    def test_reference_manifests_are_portable_and_closed(self) -> None:
        for manifest in self.manifests():
            with self.subTest(package=manifest["package_id"]):
                validate_package_manifest(manifest)
                self.assertNotIn("runtime_id", manifest)
                self.assertNotIn("provider", manifest)
                self.assertNotIn("prompt", manifest)
                self.assertNotIn("command", manifest)

    def test_pi_and_claude_compose_the_same_reference_graph(self) -> None:
        pi = self.compose_for(set(map_pi_capabilities("read,bash")))
        claude = self.compose_for(set(map_claude_capabilities(["Read", "Bash"])))

        self.assertEqual(pi, claude)
        self.assertEqual(
            pi.package_ids,
            (
                "policy.local-corpus",
                "dci.research",
                "dci.evaluation",
                "protocol.observability",
            ),
        )

    def test_reference_graph_exposes_research_and_audit_edges(self) -> None:
        composition = self.compose_for({"filesystem.read", "shell"})

        self.assertEqual(
            composition.provided_capabilities, ("research.local-corpus",)
        )
        self.assertIn("application/vnd.dci.research+json", composition.produced_artifacts)
        self.assertIn("application/vnd.dci.verdict+json", composition.produced_artifacts)
        self.assertIn("audit.package-observed", composition.emitted_events)

    def test_reference_graph_rejects_a_runtime_without_required_capabilities(self) -> None:
        with self.assertRaises(PackageCompositionError):
            self.compose_for({"filesystem.read"})


class ControlledCodePackageTests(unittest.TestCase):
    manifest_names = (
        "controlled-code-policy.json",
        "code-quality-workflow.json",
        "code-quality-evaluation.json",
        "execution-audit-observability.json",
    )

    def manifests(self) -> list[dict[str, object]]:
        return [
            json.loads(manifest_path(name).read_text())
            for name in self.manifest_names
        ]

    def composition(self):
        return self.compose_for({"executor.controlled", "filesystem.read"})

    def compose_for(
        self,
        capabilities: set[str],
        *,
        manifests: list[dict[str, object]] | None = None,
        events: set[str] | None = None,
        artifacts: set[str] | None = None,
    ):
        return compose_packages(
            self.manifests() if manifests is None else manifests,
            host_capabilities=capabilities,
            host_events={"run.started", "tool.result"} if events is None else events,
            host_artifacts={"text/x-source"} if artifacts is None else artifacts,
        )

    def replace_manifest(
        self, package_id: str, **changes: object
    ) -> list[dict[str, object]]:
        return [
            {**manifest, **changes}
            if manifest["package_id"] == package_id
            else manifest
            for manifest in self.manifests()
        ]

    def test_controlled_code_manifests_are_portable(self) -> None:
        for manifest in self.manifests():
            with self.subTest(package=manifest["package_id"]):
                validate_package_manifest(manifest)

    def test_controlled_code_graph_uses_workflow_kind(self) -> None:
        kinds = {
            manifest["package_id"]: manifest["kind"]
            for manifest in self.manifests()
        }

        self.assertEqual(kinds["workflow.code-quality"], "workflow")

    def test_controlled_code_graph_has_stable_order(self) -> None:
        self.assertEqual(
            self.composition().package_ids,
            (
                "policy.controlled-code-check",
                "workflow.code-quality",
                "evaluation.code-quality",
                "observability.execution-audit",
            ),
        )

    def test_controlled_code_manifests_exclude_runtime_fields(self) -> None:
        forbidden = {
            "arguments",
            "command",
            "credentials",
            "environment",
            "executable_path",
            "prompt",
            "provider",
            "runtime_id",
            "workspace",
        }

        for manifest in self.manifests():
            with self.subTest(package=manifest["package_id"]):
                self.assertTrue(forbidden.isdisjoint(manifest))

    def test_pi_and_claude_compose_the_same_controlled_code_graph(self) -> None:
        pi = self.compose_for(
            set(map_pi_capabilities("read")) | {"executor.controlled"}
        )
        claude = self.compose_for(
            set(map_claude_capabilities(["Read"])) | {"executor.controlled"}
        )

        self.assertEqual(pi, claude)

    def test_controlled_code_graph_is_stable_under_permutation(self) -> None:
        first = self.compose_for(
            {"executor.controlled", "filesystem.read"},
            manifests=self.manifests(),
        )
        second = self.compose_for(
            {"executor.controlled", "filesystem.read"},
            manifests=list(reversed(self.manifests())),
        )

        self.assertEqual(first, second)

    def test_controlled_code_graph_exposes_portable_outputs(self) -> None:
        composition = self.compose_for({"executor.controlled", "filesystem.read"})

        self.assertIn("workflow.code-quality", composition.provided_capabilities)
        self.assertIn("workflow.code-quality.completed", composition.emitted_events)
        self.assertEqual(
            set(composition.produced_artifacts),
            {
                "application/vnd.dci.code-quality+json",
                "application/vnd.dci.code-quality-verdict+json",
                "application/vnd.dci.execution-audit+json",
            },
        )

    def test_controlled_code_graph_rejects_every_missing_boundary(self) -> None:
        cases = (
            ({"filesystem.read"}, None, {"run.started", "tool.result"}, {"text/x-source"}),
            ({"executor.controlled"}, None, {"run.started", "tool.result"}, {"text/x-source"}),
            ({"executor.controlled", "filesystem.read"}, None, {"run.started"}, {"text/x-source"}),
            ({"executor.controlled", "filesystem.read"}, None, {"run.started", "tool.result"}, set()),
            (
                {"executor.controlled", "filesystem.read"},
                [
                    manifest
                    for manifest in self.manifests()
                    if manifest["package_id"] != "policy.controlled-code-check"
                ],
                {"run.started", "tool.result"},
                {"text/x-source"},
            ),
            (
                {"executor.controlled", "filesystem.read"},
                self.replace_manifest(
                    "workflow.code-quality", emits_events=[]
                ),
                {"run.started", "tool.result"},
                {"text/x-source"},
            ),
            (
                {"executor.controlled", "filesystem.read"},
                self.replace_manifest(
                    "workflow.code-quality", produces_artifacts=[]
                ),
                {"run.started", "tool.result"},
                {"text/x-source"},
            ),
        )

        for capabilities, manifests, events, artifacts in cases:
            with self.subTest(
                capabilities=capabilities,
                manifests=manifests,
                events=events,
                artifacts=artifacts,
            ), self.assertRaises(PackageCompositionError):
                self.compose_for(
                    capabilities,
                    manifests=manifests,
                    events=events,
                    artifacts=artifacts,
                )


class PackageDocumentationTests(unittest.TestCase):
    def guide(self) -> str:
        return PACKAGE_GUIDE.read_text()

    def test_guide_defines_static_composition_not_execution(self) -> None:
        guide = self.guide()

        self.assertIn("Static composition, not execution", guide)
        self.assertIn("does not execute", guide)
        self.assertIn("does not implement a second composer", guide)

    def test_guide_contains_a_portable_manifest_example(self) -> None:
        guide = self.guide()

        self.assertIn('"protocol": "dci.package/v1"', guide)
        self.assertIn('"requires_policies": ["policy.local-corpus"]', guide)
        self.assertIn('"requires_capabilities": ["filesystem.read", "shell"]', guide)

    def test_guide_contains_a_reference_composer_example(self) -> None:
        guide = self.guide()

        self.assertIn("compose_packages(", guide)
        self.assertIn("host_capabilities=", guide)
        self.assertIn("composition.package_ids", guide)

    def test_guide_defines_extension_and_security_boundaries(self) -> None:
        guide = self.guide()

        self.assertIn("Adding a package", guide)
        self.assertIn("adapter-specific variants", guide)
        for forbidden in ("prompts", "credentials", "executable paths", "commands"):
            with self.subTest(forbidden=forbidden):
                self.assertIn(forbidden, guide)


class ControlledCodeDocumentationTests(unittest.TestCase):
    def guide(self) -> str:
        return CONTROLLED_CODE_GUIDE.read_text()

    def test_guide_documents_the_second_graph_and_workflow_example(self) -> None:
        guide = self.guide()

        self.assertIn("Second independent graph", guide)
        self.assertIn('"package_id": "workflow.code-quality"', guide)
        self.assertIn("compose_packages(", guide)
        self.assertIn('{"executor.controlled"}', guide)

    def test_guide_defines_static_composition_not_code_execution(self) -> None:
        guide = self.guide()

        self.assertIn("Static composition, not code execution", guide)
        self.assertIn("does not execute commands", guide)

    def test_guide_defines_the_shared_host_service_boundary(self) -> None:
        guide = self.guide()

        self.assertIn("executor.controlled", guide)
        self.assertIn("shared host service", guide)
        self.assertIn("does not make Pi or Claude Code a sandbox", guide)

    def test_guide_records_that_the_graph_does_not_trigger_execution(self) -> None:
        guide = self.guide()

        self.assertIn("does not trigger a workflow engine", guide)


if __name__ == "__main__":
    unittest.main()
