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
MANIFEST_DIR = REPO_ROOT / "packages/manifests"


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
        return [json.loads((MANIFEST_DIR / name).read_text()) for name in names]

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


if __name__ == "__main__":
    unittest.main()
